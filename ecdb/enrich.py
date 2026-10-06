# -*- coding: utf-8 -*-
"""ecdb enrich —— 数据质量补全与清理（2026-09-27 方案批准后执行的一次性工具）。

背景：audit/quality_audit*.py 全库审查发现的 8 类问题，处置方案经确认后在本模块
落地。所有步骤幂等、可单独重跑；改动主库时同步维护 papers_fts 与 quality_flags；
统计写入 audit/enrich_log.jsonl，明细 CSV 落 audit/。

步骤（python -m ecdb enrich <step>）：
  placeholder     P3a  205 条 "No abstract available" 占位摘要置 NULL + 打标
  fix-doi         P2a  修正坏 DOI 10.1016./j.cor.2003.11.016（Crossref 核验标题）
  writeback-doi   P2b  paper_cit_meta 中 title_match 找回的 DOI 回写 papers.doi
                       （975 条 Crossref 匹配 + match-doi-s2 新增，撞车跳过）
  fill-abstract   P3b  Crossref + S2 按DOI补摘要（>=80 字符才收），同步 FTS
  fill-authors    P4   3 篇无作者实质研究论文按 DOI 从 Crossref 回填作者/机构
  fix-year        P5   2 条 pub_year 冲突以 Crossref 正式出版年核实修正
  clean-terms     P6   删除单字符垃圾关键词行（paper_terms）
  fix-affil       P7   清理悬挂机构编号（保守：能核实才补，否则摘除悬空引用）
  publisher       P8a  按 venue_tag 众数回填缺失 publisher
  flag-affil      P8b  全库重算 quality_flags（含新增 no_affiliations 标签）
  delete-review   D    导出 18 条删除候选 -> audit/deletion_review.csv
  delete          D    执行删除（--confirm；papers + 4 关联表 + FTS，引文孤儿由
                       eccite reconcile 清理）
  scope-review    S    范围裁剪预检：导出删除清单 -> audit/scope_deleted.csv
  scope           S    执行范围裁剪（--confirm）：pub_year 出界 [2000,2025] +
                       范围内摘要/DOI/作者缺失（方案 A，2026-09-27 用户确认）

引文表（paper_cit_*）本模块一律不写——DOI 变更后用 `eccite sync-doi` 同步、
`eccite fetch-* / load` 补抓。
"""
import csv
import html as _html
import json
import re
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPException
from pathlib import Path

from . import _paths
from .cleaning import normalize_title, quality_flags as calc_flags

AUDIT_DIR = Path(__file__).resolve().parent.parent / "audit"

CR_URL = "https://api.crossref.org"
S2_URL = "https://api.semanticscholar.org/graph/v1"
MAILTO = "ec-audit@example.org"  # 与 eccite 保持一致的礼貌池联系邮箱
UA_CR = {"User-Agent": "EC_MAP_2026-enrich/1.0 (mailto:%s)" % MAILTO}
UA_S2 = {"User-Agent": "EC_MAP_2026-enrich/1.0"}

PLACEHOLDER_ABSTRACTS = {
    "no abstract available", "abstract not available", "no abstract",
    "abstract unavailable", "no abstract is available",
}


# ---------------------------------------------------------------------------
# 基础设施：限流 HTTP（移植自 eccite._rate，实战验证过的实现）
# ---------------------------------------------------------------------------

class RateLimiter:
    """线程安全的最小请求间隔限速器，支持 429 自适应降速。"""

    def __init__(self, min_interval, floor=0.05):
        self.min_interval = min_interval
        self.floor = floor
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self):
        with self._lock:
            now = time.time()
            t = max(self._next, now)
            self._next = t + self.min_interval
            sleep = t - now
        if sleep > 0:
            time.sleep(sleep)

    def slowdown(self, factor=1.5, cap=10.0):
        with self._lock:
            self.min_interval = min(self.min_interval * factor, cap)

    def speedup(self, factor=0.97):
        with self._lock:
            self.min_interval = max(self.min_interval * factor, self.floor)


def http_json(url, headers, limiter=None, max_tries=6, method="GET", body=None,
              timeout=90):
    """GET/POST JSON，带 429/5xx 退避重试。返回 (status, obj)。"""
    delay = 2.0
    last_err = None
    for _attempt in range(max_tries):
        if limiter:
            limiter.wait()
        req = urllib.request.Request(url, headers=headers, data=body, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if limiter:
                    limiter.speedup()
                return resp.status, json.loads(raw)
        except urllib.error.HTTPError as e:
            last_err = "HTTP %d" % e.code
            if e.code == 404:
                return 404, None
            if e.code == 429 or e.code >= 500:
                if limiter:
                    limiter.slowdown()
                retry_after = e.headers.get("Retry-After") if e.headers else None
                sleep = float(retry_after) if retry_after and retry_after.isdigit() else delay
                time.sleep(min(sleep, 60))
                delay = min(delay * 2, 60)
                continue
            if e.code == 400:
                return 400, None
            raise
        except (OSError, TimeoutError, json.JSONDecodeError, HTTPException) as e:
            last_err = str(e)
            time.sleep(delay)
            delay = min(delay * 2, 60)
    raise RuntimeError("failed after %d tries: %s (%s)" % (max_tries, url, last_err))


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _rw():
    p = _paths.db_path()
    conn = sqlite3.connect(str(p), timeout=150)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=150000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _log(step, stats):
    AUDIT_DIR.mkdir(exist_ok=True)
    rec = {"step": step, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    rec.update(stats)
    with open(AUDIT_DIR / "enrich_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("[enrich:%s] %s" % (step, json.dumps(stats, ensure_ascii=False)))


def _csv_write(path, header, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return str(path)


# ---------------------------------------------------------------------------
# papers_fts 与 quality_flags 维护
# ---------------------------------------------------------------------------

_FTS_ROW_SQL = (
    "INSERT INTO papers_fts(rowid, title, abstract, authors, terms) "
    "SELECT p.rowid, COALESCE(p.title,''), COALESCE(p.abstract,''), "
    "COALESCE((SELECT GROUP_CONCAT(pa.name_display,'; ') FROM paper_authors pa "
    "         WHERE pa.accession_no=p.accession_no),''), "
    "COALESCE((SELECT GROUP_CONCAT(pt.term,'; ') FROM paper_terms pt "
    "         WHERE pt.accession_no=p.accession_no),'') "
    "FROM papers p WHERE p.rowid=?")


def fts_resync(rw, accs):
    """按 importer 的口径重建受影响论文的 FTS 行（title/abstract/authors/terms）。"""
    n = 0
    for chunk in _chunks(sorted(set(accs)), 500):
        ph = ",".join("?" * len(chunk))
        rowids = [r[0] for r in rw.execute(
            "SELECT rowid FROM papers WHERE accession_no IN (%s)" % ph, chunk)]
        for rid in rowids:
            rw.execute("DELETE FROM papers_fts WHERE rowid=?", (rid,))
            rw.execute(_FTS_ROW_SQL, (rid,))
        rw.commit()
        n += len(rowids)
    return n


def recompute_flags(rw, accs):
    """按 cleaning.quality_flags 口径全量重算 quality_flags，并追加 no_affiliations。"""
    accs = sorted(set(accs))
    if not accs:
        return 0
    n = 0
    for chunk in _chunks(accs, 500):
        ph = ",".join("?" * len(chunk))
        rows = rw.execute(
            "SELECT accession_no, doi, abstract, authors_raw, pages, article_number "
            "FROM papers WHERE accession_no IN (%s)" % ph, chunk).fetchall()
        has_terms = {r[0] for r in rw.execute(
            "SELECT DISTINCT accession_no FROM paper_terms WHERE accession_no IN (%s)" % ph,
            chunk)}
        has_affil = {r[0] for r in rw.execute(
            "SELECT DISTINCT accession_no FROM paper_affiliations WHERE accession_no IN (%s)" % ph,
            chunk)}
        updates = []
        for r in rows:
            rec = {"abstract": r[2], "doi": r[1], "authors_raw": r[3],
                   "pages": r[4], "article_number": r[5]}
            flags = calc_flags(rec, [1] if r[0] in has_terms else [])
            if r[0] not in has_affil:
                flags.append("no_affiliations")
            updates.append((json.dumps(flags, ensure_ascii=False), r[0]))
        rw.executemany("UPDATE papers SET quality_flags=? WHERE accession_no=?", updates)
        rw.commit()
        n += len(updates)
    return n


# ---------------------------------------------------------------------------
# 外部源客户端
# ---------------------------------------------------------------------------

def cr_get(doi, limiter, fields=None):
    """Crossref /works/{doi}；失败/无记录返回 None。

    fields 参数仅作兼容保留：Crossref 的 select 白名单不含 abstract，带 abstract
    的 select 会整请求 400，因此总是取完整记录。
    """
    url = "%s/works/%s" % (CR_URL, urllib.parse.quote(doi))
    try:
        status, obj = http_json(url, UA_CR, limiter, max_tries=5)
    except RuntimeError:
        return None
    return (obj or {}).get("message") if status == 200 else None


def s2_batch(dois, fields):
    """S2 paper/batch（100 DOI/请求）-> {doi: record 或 None}。

    未认证共享池限流严重：连续 2 块失败即熔断返回已有结果，由 OpenAlex/Crossref 兜底。
    """
    out = {}
    limiter = RateLimiter(3.0, floor=2.0)
    chunks = [c for c in _chunks(list(dois), 100)]
    state = {"consec_fail": 0, "stop": False}

    def worker(chunk):
        if state["stop"]:
            return
        ids = ["DOI:" + d for d in chunk]
        url = "%s/paper/batch?fields=%s" % (S2_URL, fields)
        body = json.dumps({"ids": ids}).encode()
        try:
            status, arr = http_json(url, {**UA_S2, "Content-Type": "application/json"},
                                    limiter, max_tries=4, method="POST", body=body)
        except RuntimeError:
            state["consec_fail"] += 1
            if state["consec_fail"] >= 2:
                state["stop"] = True
                print("[enrich] S2 batch 连续失败 %d 块，熔断改用 OpenAlex/Crossref"
                      % state["consec_fail"])
            return
        state["consec_fail"] = 0
        if status == 200 and isinstance(arr, list):
            for d, rec in zip(chunk, arr):
                out[d] = rec

    with ThreadPoolExecutor(max_workers=1) as ex:
        list(ex.map(worker, chunks))
    return out


def _clean_abstract(s):
    """JATS/HTML 清洗：去标签、反转义、折叠空白。"""
    if not s:
        return None
    t = re.sub(r"<[^>]+>", " ", str(s))
    t = _html.unescape(t)
    t = " ".join(t.split())
    return t or None


def _invert_abstract(inv):
    """OpenAlex abstract_inverted_index -> 纯文本摘要。"""
    if not inv:
        return None
    pairs = []
    for word, positions in inv.items():
        for p in positions or []:
            pairs.append((p, word))
    if not pairs:
        return None
    pairs.sort()
    return " ".join(w for _, w in pairs)


OA_URL = "https://api.openalex.org"


def oa_batch(dois):
    """OpenAlex 按 DOI 批量取记录（filter=doi: 管道写法，50/批）
    -> {doi: work}，work 含 abstract_inverted_index / authorships。

    配额耗尽时（连续 2 块失败）熔断返回已有结果。
    """
    out = {}
    limiter = RateLimiter(0.25, floor=0.15)
    chunks = [c for c in _chunks(sorted(set(dois)), 50)]
    state = {"consec_fail": 0, "stop": False}

    def worker(chunk):
        if state["stop"]:
            return
        filt = "doi:" + "|".join(chunk)
        url = ("%s/works?filter=%s&per-page=50&select=doi,display_name,"
               "abstract_inverted_index,authorships,publication_year&mailto=%s"
               % (OA_URL, urllib.parse.quote(filt), MAILTO))
        try:
            status, obj = http_json(url, UA_CR, limiter, max_tries=3)
        except RuntimeError:
            state["consec_fail"] += 1
            if state["consec_fail"] >= 2:
                state["stop"] = True
                print("[enrich] OpenAlex 连续失败 %d 块，熔断改用 Crossref"
                      % state["consec_fail"])
            return
        state["consec_fail"] = 0
        for w in (obj or {}).get("results") or []:
            d = w.get("doi") or ""
            d = d.rsplit("doi.org/", 1)[-1].strip().lower()
            if d:
                out[d] = w

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(worker, chunks))
    return out


# ---------------------------------------------------------------------------
# P3a placeholder
# ---------------------------------------------------------------------------

def step_placeholder(rw):
    accs = [r[0] for r in rw.execute(
        "SELECT accession_no FROM papers WHERE abstract = 'No abstract available'")]
    if not accs:
        _log("placeholder", {"nulled": 0, "note": "无占位摘要（已处理过？）"})
        return
    rw.execute("UPDATE papers SET abstract=NULL WHERE abstract='No abstract available'")
    rw.commit()
    n_flag = recompute_flags(rw, accs)
    n_fts = fts_resync(rw, accs)
    _log("placeholder", {"nulled": len(accs), "flags_updated": n_flag,
                         "fts_resynced": n_fts})


# ---------------------------------------------------------------------------
# P2a fix-doi
# ---------------------------------------------------------------------------

BAD_DOI_ACC = "2004508717961"
BAD_DOI_OLD = "10.1016./j.cor.2003.11.016"
BAD_DOI_NEW = "10.1016/j.cor.2003.11.016"


def step_fix_doi(rw):
    row = rw.execute("SELECT doi, title FROM papers WHERE accession_no=?",
                     (BAD_DOI_ACC,)).fetchone()
    if row is None:
        _log("fix_doi", {"status": "skip", "reason": "accession 不存在"})
        return
    if row["doi"] == BAD_DOI_NEW:
        _log("fix_doi", {"status": "skip", "reason": "已是正确 DOI"})
        return
    if row["doi"] != BAD_DOI_OLD:
        _log("fix_doi", {"status": "skip", "reason": "当前 doi=%r 非预期坏值" % row["doi"]})
        return
    limiter = RateLimiter(0.3, floor=0.15)
    msg = cr_get(BAD_DOI_NEW, limiter)
    cr_title = ((msg or {}).get("title") or [None])[0]
    ok = bool(cr_title) and normalize_title(cr_title) == normalize_title(row["title"])
    if not ok:
        _log("fix_doi", {"status": "abort",
                         "reason": "Crossref 标题核验未通过",
                         "cr_title": cr_title, "db_title": row["title"]})
        return
    rw.execute("UPDATE papers SET doi=? WHERE accession_no=? AND doi=?",
               (BAD_DOI_NEW, BAD_DOI_ACC, BAD_DOI_OLD))
    rw.commit()
    recompute_flags(rw, [BAD_DOI_ACC])
    _log("fix_doi", {"status": "fixed", "accession_no": BAD_DOI_ACC,
                     "old": BAD_DOI_OLD, "new": BAD_DOI_NEW,
                     "cr_title": cr_title})


# ---------------------------------------------------------------------------
# P2b writeback-doi
# ---------------------------------------------------------------------------

def step_writeback_doi(rw):
    rows = rw.execute(
        "SELECT m.accession_no AS acc, m.doi AS doi FROM paper_cit_meta m "
        "JOIN papers p ON p.accession_no=m.accession_no "
        "WHERE m.doi_source='title_match' AND m.doi IS NOT NULL AND m.doi != '' "
        "AND (p.doi IS NULL OR p.doi='')").fetchall()
    taken = {r[0] for r in rw.execute(
        "SELECT DISTINCT doi FROM papers WHERE doi IS NOT NULL AND doi != ''")}
    updates, collisions = [], []
    for r in rows:
        acc, doi = r["acc"], r["doi"]
        if doi in taken:
            collisions.append((acc, doi))
            continue
        taken.add(doi)
        updates.append((doi, acc))
    rw.executemany(
        "UPDATE papers SET doi=? WHERE accession_no=? AND (doi IS NULL OR doi='')",
        updates)
    rw.commit()
    accs = [a for _, a in updates]
    n_flag = recompute_flags(rw, accs)
    wb = _csv_write(AUDIT_DIR / "doi_writeback.csv",
                    ["accession_no", "doi"], [(a, d) for d, a in updates])
    cl = _csv_write(AUDIT_DIR / "doi_collisions.csv",
                    ["accession_no", "doi"], collisions)
    _log("writeback_doi", {"candidates": len(rows), "written": len(updates),
                           "collisions_skipped": len(collisions),
                           "flags_updated": n_flag,
                           "csv": wb, "collisions_csv": cl})


# ---------------------------------------------------------------------------
# P3b fill-abstract
# ---------------------------------------------------------------------------

def step_fill_abstract(rw):
    targets = rw.execute(
        "SELECT accession_no AS acc, doi FROM papers "
        "WHERE abstract IS NULL AND doi IS NOT NULL AND doi != ''").fetchall()
    dois = sorted({r["doi"] for r in targets})
    print("[enrich:fill-abstract] targets=%d unique_dois=%d" % (len(targets), len(dois)))
    s2rec = s2_batch(dois, "title,abstract") if dois else {}
    oarec = oa_batch(dois) if dois else {}

    limiter = RateLimiter(0.15, floor=0.1)
    cr_abs = {}
    lock = threading.Lock()

    def cr_worker(doi):
        msg = cr_get(doi, limiter)
        ab = _clean_abstract((msg or {}).get("abstract"))
        if ab:
            with lock:
                cr_abs[doi] = ab

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(cr_worker, dois))

    filled, rows_csv = [], []
    for r in targets:
        acc, doi = r["acc"], r["doi"]
        cands = []
        a_s2 = _clean_abstract((s2rec.get(doi) or {}).get("abstract"))
        if a_s2:
            cands.append(("s2", a_s2))
        a_oa = _invert_abstract((oarec.get(doi) or {}).get("abstract_inverted_index"))
        if a_oa:
            cands.append(("openalex", a_oa))
        a_cr = cr_abs.get(doi)
        if a_cr:
            cands.append(("crossref", a_cr))
        valid = [c for c in cands
                 if len(c[1]) >= 80 and c[1].lower() not in PLACEHOLDER_ABSTRACTS]
        if not valid:
            continue
        src, ab = max(valid, key=lambda c: len(c[1]))
        filled.append((ab, acc))
        rows_csv.append((acc, doi, src, len(ab)))
    rw.executemany("UPDATE papers SET abstract=? WHERE accession_no=? AND abstract IS NULL",
                   filled)
    rw.commit()
    accs = [a for _, a in filled]
    n_flag = recompute_flags(rw, accs)
    n_fts = fts_resync(rw, accs)
    path = _csv_write(AUDIT_DIR / "abstract_fill.csv",
                      ["accession_no", "doi", "source", "len"], rows_csv)
    _log("fill_abstract", {
        "targets": len(targets), "filled": len(filled),
        "from_s2": sum(1 for x in rows_csv if x[2] == "s2"),
        "from_openalex": sum(1 for x in rows_csv if x[2] == "openalex"),
        "from_crossref": sum(1 for x in rows_csv if x[2] == "crossref"),
        "still_missing": len(targets) - len(filled),
        "flags_updated": n_flag, "fts_resynced": n_fts, "csv": path})


# ---------------------------------------------------------------------------
# P4 fill-authors（3 篇无作者的实质研究论文）
# ---------------------------------------------------------------------------

FILL_AUTHOR_TARGETS = [
    ("20161602267320", "10.1109/cec.2015.7256958"),
    ("20193307321520", "10.1145/3319619.3321915"),
    ("20230713582967", "10.1109/ssci51031.2022.10022191"),
]


def step_fill_authors(rw):
    limiter = RateLimiter(0.3, floor=0.15)
    done, skipped = [], []
    for acc, doi in FILL_AUTHOR_TARGETS:
        row = rw.execute("SELECT authors_raw, title FROM papers WHERE accession_no=?",
                         (acc,)).fetchone()
        if row is None:
            skipped.append({"acc": acc, "reason": "不存在"})
            continue
        if row["authors_raw"]:
            skipped.append({"acc": acc, "reason": "已有作者（幂等跳过）"})
            continue
        # OpenAlex 优先（authorships 自带机构）；Crossref 兜底
        src_used = None
        a_rows, aff_rows, raw_list = [], [], []
        oa = oa_batch([doi]).get(doi)
        if oa and oa.get("authorships"):
            src_used = "openalex"
            seen = {}
            for pos, au in enumerate(oa["authorships"], 1):
                name = ((au.get("author") or {}).get("display_name") or
                        au.get("raw_author_name") or "").strip()
                if not name:
                    continue
                refs = []
                for inst in au.get("institutions") or []:
                    nm = (inst.get("display_name") or "").strip()
                    if not nm:
                        continue
                    if nm not in seen:
                        seen[nm] = len(seen) + 1
                        aff_rows.append((seen[nm], nm))
                    refs.append(str(seen[nm]))
                raw = name  # OpenAlex 仅 display_name，name_raw 与其保持一致
                a_rows.append((acc, pos, raw, name, ";".join(refs) or None))
                raw_list.append(name)
        else:
            msg = cr_get(doi, limiter)
            authors = (msg or {}).get("author") or []
            if authors:
                src_used = "crossref"
                seen = {}
                for pos, a in enumerate(authors, 1):
                    given = (a.get("given") or "").strip()
                    family = (a.get("family") or "").strip()
                    name_raw = (", ".join(x for x in (family, given) if x)
                                or (a.get("name") or None))
                    name_disp = (" ".join(x for x in (given, family) if x)
                                 or (a.get("name") or None))
                    refs = []
                    for aff in a.get("affiliation") or []:
                        nm = (aff.get("name") or "").strip()
                        if not nm:
                            continue
                        if nm not in seen:
                            seen[nm] = len(seen) + 1
                            aff_rows.append((seen[nm], nm))
                        refs.append(str(seen[nm]))
                    a_rows.append((acc, pos, name_raw, name_disp, ";".join(refs) or None))
                    raw_list.append(name_raw or name_disp or "（未知）")
        if not a_rows:
            skipped.append({"acc": acc, "reason": "OpenAlex/Crossref 均无作者"})
            continue
        rw.execute("DELETE FROM paper_authors WHERE accession_no=?", (acc,))
        rw.execute("DELETE FROM paper_affiliations WHERE accession_no=?", (acc,))
        rw.executemany(
            "INSERT INTO paper_authors (accession_no, position, name_raw, name_display, "
            "affil_refs) VALUES (?,?,?,?,?)", a_rows)
        if aff_rows:
            rw.executemany(
                "INSERT OR IGNORE INTO paper_affiliations (accession_no, idx, affiliation) "
                "VALUES (?,?,?)", [(acc, i, nm) for i, nm in aff_rows])
        rw.execute("UPDATE papers SET authors_raw=? WHERE accession_no=?",
                   ("; ".join(raw_list), acc))
        rw.commit()
        recompute_flags(rw, [acc])
        fts_resync(rw, [acc])
        done.append({"acc": acc, "doi": doi, "source": src_used,
                     "authors": len(a_rows), "affiliations": len(aff_rows)})
    path = _csv_write(AUDIT_DIR / "authors_fill.csv",
                      ["accession_no", "doi", "source", "n_authors", "n_affiliations",
                       "status"],
                      [(d["acc"], d["doi"], d["source"], d["authors"],
                        d["affiliations"], "filled") for d in done] +
                      [(s["acc"], "", "", "", "", s["reason"]) for s in skipped])
    _log("fill_authors", {"filled": len(done), "skipped": len(skipped),
                          "detail": done + skipped, "csv": path})


# ---------------------------------------------------------------------------
# P5 fix-year
# ---------------------------------------------------------------------------

FIX_YEAR_TARGETS = [
    ("20161202134525", "10.1287/opre.43.2.346"),
    ("20170103208115", "10.1109/tcyb.2016.2638820"),
]


def _cr_year(msg, key):
    try:
        return ((msg or {}).get(key) or {}).get("date-parts")[0][0]
    except Exception:
        return None


def step_fix_year(rw):
    limiter = RateLimiter(0.3, floor=0.15)
    changes, unchanged = [], []
    for acc, doi in FIX_YEAR_TARGETS:
        row = rw.execute("SELECT pub_year, title FROM papers WHERE accession_no=?",
                         (acc,)).fetchone()
        if row is None:
            unchanged.append({"acc": acc, "reason": "不存在"})
            continue
        msg = cr_get(doi, limiter)
        cr_print = _cr_year(msg, "published-print")
        cr_online = _cr_year(msg, "published-online")
        cr_issued = _cr_year(msg, "issued")
        new_year = cr_print or cr_issued
        rec = {"acc": acc, "doi": doi, "db_year": row["pub_year"],
               "cr_print": cr_print, "cr_online": cr_online, "cr_issued": cr_issued}
        if not new_year:
            unchanged.append({**rec, "reason": "Crossref 无出版年"})
        elif int(new_year) != int(row["pub_year"]):
            rw.execute("UPDATE papers SET pub_year=? WHERE accession_no=?",
                       (int(new_year), acc))
            rw.commit()
            changes.append({**rec, "new_year": int(new_year)})
        else:
            unchanged.append({**rec, "reason": "与 Crossref 正式出版年一致"})
    _log("fix_year", {"changed": changes, "unchanged": unchanged})


# ---------------------------------------------------------------------------
# P6 clean-terms
# ---------------------------------------------------------------------------

def step_clean_terms(rw):
    bad = rw.execute(
        "SELECT accession_no AS acc, term FROM paper_terms "
        "WHERE length(trim(term)) < 2").fetchall()
    accs = sorted({r["acc"] for r in bad})
    if not bad:
        _log("clean_terms", {"rows_deleted": 0})
        return
    rw.execute("DELETE FROM paper_terms WHERE length(trim(term)) < 2")
    rw.commit()
    n_flag = recompute_flags(rw, accs)
    n_fts = fts_resync(rw, accs)
    _log("clean_terms", {"rows_deleted": len(bad), "papers_affected": len(accs),
                         "flags_updated": n_flag, "fts_resynced": n_fts})


# ---------------------------------------------------------------------------
# P7 fix-affil（保守策略：悬挂编号一律摘除；单作者论文可用 Crossref 唯一机构补）
# ---------------------------------------------------------------------------

def step_fix_affil(rw):
    idx_map = {}
    for r in rw.execute("SELECT accession_no AS acc, idx FROM paper_affiliations"):
        idx_map.setdefault(r["acc"], set()).add(str(r["idx"]))
    dangling = {}
    updates = []
    for r in rw.execute(
            "SELECT accession_no AS acc, position AS pos, affil_refs AS ar "
            "FROM paper_authors WHERE affil_refs IS NOT NULL AND trim(affil_refs) != ''"):
        have = idx_map.get(r["acc"], set())
        refs = [t for t in re.split(r"[;,\s]+", r["ar"]) if t]
        good = [t for t in refs if t in have]
        bad = [t for t in refs if t not in have]
        if bad:
            updates.append((";".join(good) or None, r["acc"], r["pos"]))
            dangling.setdefault(r["acc"], set()).update(bad)
    rw.executemany(
        "UPDATE paper_authors SET affil_refs=? WHERE accession_no=? AND position=?",
        updates)
    rw.commit()

    # 单作者且恰好 1 个悬挂编号的论文：Crossref 唯一机构可无歧义回填
    limiter = RateLimiter(0.3, floor=0.15)
    repaired = []
    for acc in sorted(dangling):
        refs = dangling[acc]
        n_auth = rw.execute("SELECT COUNT(*) FROM paper_authors WHERE accession_no=?",
                            (acc,)).fetchone()[0]
        n_aff = rw.execute("SELECT COUNT(*) FROM paper_affiliations WHERE accession_no=?",
                           (acc,)).fetchone()[0]
        if n_auth != 1 or len(refs) != 1 or n_aff > 0:
            continue
        doi = rw.execute("SELECT doi FROM papers WHERE accession_no=?", (acc,)).fetchone()[0]
        if not doi:
            continue
        msg = cr_get(doi, limiter)
        authors = (msg or {}).get("author") or []
        affs = [a.get("affiliation") or [] for a in authors]
        if len(authors) == 1 and len(affs[0]) == 1:
            nm = (affs[0][0].get("name") or "").strip()
            if nm:
                rw.execute(
                    "INSERT OR IGNORE INTO paper_affiliations (accession_no, idx, affiliation) "
                    "VALUES (?,?,?)", (acc, 1, nm))
                rw.execute("UPDATE paper_authors SET affil_refs='1' "
                           "WHERE accession_no=? AND position=1", (acc,))
                rw.commit()
                repaired.append({"acc": acc, "affiliation": nm})
    n_flag = recompute_flags(rw, list(dangling))
    fts_resync(rw, [a for a, _, _ in updates] + [r["acc"] for r in repaired])
    _log("fix_affil", {"authors_stripped": len(updates), "papers_touched": len(dangling),
                       "repaired_from_crossref": repaired, "flags_updated": n_flag})


# ---------------------------------------------------------------------------
# P8a publisher
# ---------------------------------------------------------------------------

def step_publisher(rw):
    mode = {}
    for r in rw.execute(
            "SELECT venue_tag AS v, publisher AS p, COUNT(*) AS c FROM papers "
            "WHERE publisher IS NOT NULL AND venue_tag IS NOT NULL "
            "GROUP BY venue_tag, publisher ORDER BY venue_tag, c DESC"):
        mode.setdefault(r["v"], r["p"])
    rows = []
    for r in rw.execute(
            "SELECT accession_no AS acc, venue_tag AS v FROM papers "
            "WHERE publisher IS NULL AND venue_tag IS NOT NULL"):
        if r["v"] in mode:
            rows.append((mode[r["v"]], r["acc"]))
    rw.executemany(
        "UPDATE papers SET publisher=? WHERE accession_no=? AND publisher IS NULL", rows)
    rw.commit()
    _log("publisher", {"filled": len(rows), "venues_covered": len(mode)})


# ---------------------------------------------------------------------------
# P8b flag-affil（全库重算，含 no_affiliations）
# ---------------------------------------------------------------------------

def step_flag_affil(rw):
    all_accs = [r[0] for r in rw.execute("SELECT accession_no FROM papers")]
    n = recompute_flags(rw, all_accs)
    dist = {r[0]: r[1] for r in rw.execute(
        "SELECT quality_flags AS f, COUNT(*) AS c FROM papers GROUP BY quality_flags "
        "ORDER BY c DESC LIMIT 40")}
    _log("flag_affil", {"recomputed": n, "top_flag_combos": dist})


# ---------------------------------------------------------------------------
# D 删除
# ---------------------------------------------------------------------------

DELETE_LIST = [
    ("20081011130543", "IEEE CIM 采访专栏（Interview），非研究文献"),
    ("20081911239585", "IEEE CIM 采访专栏（Interview），非研究文献"),
    ("20081911239586", "IEEE CIM 采访专栏（Interview），非研究文献"),
    ("20092412124324", "IEEE CIM 采访专栏（Interview），非研究文献"),
    ("20094512436993", "IEEE CIM 采访专栏（Interview），非研究文献"),
    ("20150400446321", "IEEE CIM 编委会名单（CIS society officers），非研究文献"),
    ("1981120008170", "会议公告（EURO 3 征稿/通知），非研究文献"),
    ("20073610800002", "期刊卷首语（Forward），无关键词、摘要 21 字符"),
    ("20091412013154", "期刊简讯（Web search），无摘要无关键词"),
    ("20121814975050", "期刊专栏简讯（Data flood），无摘要无关键词"),
    ("20135117095031", "卸任致辞（Farewell），无摘要无关键词"),
    ("20171703592569", "免责声明（Disclaimer），无摘要无关键词"),
    ("20174904488133", "名单（Staff List），参考文献仅 1 条"),
    ("20242916727443", "卷首语（Time Flies），无摘要无关键词"),
    ("20165203176767", "会议主席致辞（Message from Conference Chair），无关键词无参考文献"),
    ("20073910830288", "会议程序主席致辞（Message from program co-chairs），同上"),
    ("20073910823878", "会议主席致辞（Message from the Chairs），同上"),
    ("2006049658148", "周年专刊导言（Anniversary focused issue），无关键词、摘要 21 字符"),
]


def step_delete_review(rw):
    rows = []
    for acc, reason in DELETE_LIST:
        r = rw.execute(
            "SELECT accession_no, pub_year, doc_type, venue_tag, title, doi "
            "FROM papers WHERE accession_no=?", (acc,)).fetchone()
        if r is None:
            rows.append([acc, "", "", "", "（库中已不存在）", "", reason])
        else:
            rows.append([r["accession_no"], r["pub_year"], r["doc_type"],
                         r["venue_tag"], r["title"], r["doi"] or "", reason])
    path = _csv_write(AUDIT_DIR / "deletion_review.csv",
                      ["accession_no", "pub_year", "doc_type", "venue_tag", "title",
                       "doi", "reason"], rows)
    _log("delete_review", {"candidates": len(DELETE_LIST), "csv": path})


def step_delete(rw, confirm=False):
    if not confirm:
        print("[enrich:delete] 拒绝执行：需要 --confirm。先运行 delete-review 核对。")
        return
    accs = [a for a, _ in DELETE_LIST]
    ph = ",".join("?" * len(accs))
    present = {r["accession_no"]: r["rowid"] for r in rw.execute(
        "SELECT accession_no, rowid FROM papers WHERE accession_no IN (%s)" % ph, accs)}
    missing = [a for a in accs if a not in present]
    stats = {"candidates": len(accs), "deleted": 0, "already_absent": len(missing)}
    if missing:
        stats["missing"] = missing
    accs_hit = [a for a in accs if a in present]
    if accs_hit:
        ph2 = ",".join("?" * len(accs_hit))
        counts = {}
        for t in ("paper_authors", "paper_affiliations", "paper_terms", "paper_sources"):
            cur = rw.execute("DELETE FROM %s WHERE accession_no IN (%s)" % (t, ph2), accs_hit)
            counts[t] = cur.rowcount
        rw.executemany("DELETE FROM papers_fts WHERE rowid=?",
                       [(present[a],) for a in accs_hit])
        cur = rw.execute("DELETE FROM papers WHERE accession_no IN (%s)" % ph2, accs_hit)
        counts["papers"] = cur.rowcount
        rw.commit()
        stats["deleted"] = counts.pop("papers")
        stats["child_rows_deleted"] = counts
    _log("delete", stats)


# ---------------------------------------------------------------------------
# S 范围裁剪（2000-2025 + 字段完整性，方案 A）
# ---------------------------------------------------------------------------

SCOPE_YEAR_LO = 2000
SCOPE_YEAR_HI = 2025


def _scope_targets(rw):
    """[(acc, year, doc_type, venue_tag, title, doi, abstract_len, reason)]。"""
    out = []
    for r in rw.execute(
            "SELECT accession_no AS acc, pub_year AS y, doc_type AS dt, "
            "venue_tag AS v, title AS t, doi AS d, "
            "length(COALESCE(abstract,'')) AS alen FROM papers "
            "WHERE pub_year IS NULL OR pub_year < ? OR pub_year > ?",
            (SCOPE_YEAR_LO, SCOPE_YEAR_HI)):
        out.append((r["acc"], r["y"], r["dt"], r["v"], r["t"], r["d"], r["alen"],
                    "out_of_range_year"))
    for r in rw.execute(
            "SELECT accession_no AS acc, pub_year AS y, doc_type AS dt, "
            "venue_tag AS v, title AS t, doi AS d, "
            "length(COALESCE(abstract,'')) AS alen, "
            "(abstract IS NULL) AS na, (doi IS NULL) AS nd, "
            "(authors_raw IS NULL) AS nau FROM papers "
            "WHERE pub_year BETWEEN ? AND ? "
            "AND (abstract IS NULL OR doi IS NULL OR authors_raw IS NULL)",
            (SCOPE_YEAR_LO, SCOPE_YEAR_HI)):
        reasons = []
        if r["na"]:
            reasons.append("missing_abstract")
        if r["nd"]:
            reasons.append("missing_doi")
        if r["nau"]:
            reasons.append("missing_authors")
        out.append((r["acc"], r["y"], r["dt"], r["v"], r["t"], r["d"], r["alen"],
                    ";".join(reasons)))
    return out


def step_scope_review(rw):
    targets = _scope_targets(rw)
    from collections import Counter
    reason_cnt = Counter(r[-1] for r in targets)
    path = _csv_write(AUDIT_DIR / "scope_deleted.csv",
                      ["accession_no", "pub_year", "doc_type", "venue_tag", "title",
                       "doi", "abstract_len", "reason"], targets)
    _log("scope_review", {"targets": len(targets),
                          "reason_counts": dict(reason_cnt), "csv": path})


def _chunked_delete(rw, table, accs, chunk=2000):
    n = 0
    for part in _chunks(accs, chunk):
        ph = ",".join("?" * len(part))
        cur = rw.execute("DELETE FROM %s WHERE accession_no IN (%s)" % (table, ph), part)
        rw.commit()
        n += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    return n


def step_scope(rw, confirm=False):
    if not confirm:
        print("[enrich:scope] 拒绝执行：需要 --confirm。先运行 scope-review 核对清单。")
        return
    targets = _scope_targets(rw)
    accs = [t[0] for t in targets]
    from collections import Counter
    reason_cnt = Counter(t[-1] for t in targets)
    # 行 id 先取（FTS 删除用），子表先删、papers 最后删
    rowids = {r["accession_no"]: r["rowid"] for r in rw.execute(
        "SELECT accession_no, rowid FROM papers")}
    stats = {"targets": len(accs), "reason_counts": dict(reason_cnt),
             "child_rows_deleted": {}}
    for t in ("paper_authors", "paper_affiliations", "paper_terms", "paper_sources"):
        stats["child_rows_deleted"][t] = _chunked_delete(rw, t, accs)
    n_fts = 0
    for part in _chunks(accs, 2000):
        ids = [rowids[a] for a in part if a in rowids]
        for i in range(0, len(ids), 900):
            ph = ",".join("?" * len(ids[i:i + 900]))
            cur = rw.execute("DELETE FROM papers_fts WHERE rowid IN (%s)" % ph,
                             ids[i:i + 900])
            n_fts += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        rw.commit()
    stats["fts_rows_deleted"] = n_fts
    stats["papers_deleted"] = _chunked_delete(rw, "papers", accs)
    rw.execute("ANALYZE")
    rw.commit()
    _log("scope", stats)


# ---------------------------------------------------------------------------
# CLI 调度
# ---------------------------------------------------------------------------

STEPS = ("placeholder", "fix-doi", "writeback-doi", "fill-abstract", "fill-authors",
         "fix-year", "clean-terms", "fix-affil", "publisher", "flag-affil",
         "delete-review", "delete", "scope-review", "scope")


def run(step, confirm=False):
    if step not in STEPS:
        raise ValueError("未知步骤 %r，可选：%s" % (step, "/".join(STEPS)))
    rw = _rw()
    try:
        if step == "placeholder":
            step_placeholder(rw)
        elif step == "fix-doi":
            step_fix_doi(rw)
        elif step == "writeback-doi":
            step_writeback_doi(rw)
        elif step == "fill-abstract":
            step_fill_abstract(rw)
        elif step == "fill-authors":
            step_fill_authors(rw)
        elif step == "fix-year":
            step_fix_year(rw)
        elif step == "clean-terms":
            step_clean_terms(rw)
        elif step == "fix-affil":
            step_fix_affil(rw)
        elif step == "publisher":
            step_publisher(rw)
        elif step == "flag-affil":
            step_flag_affil(rw)
        elif step == "delete-review":
            step_delete_review(rw)
        elif step == "delete":
            step_delete(rw, confirm=confirm)
        elif step == "scope-review":
            step_scope_review(rw)
        elif step == "scope":
            step_scope(rw, confirm=confirm)
    finally:
        rw.close()
