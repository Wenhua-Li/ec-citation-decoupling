"""fetchers —— 三源抓取 + 无 DOI 论文标题匹配。

抓取器只写 JSONL 缓存，不直接写库（load 阶段统一入库）。
todo 集合 = 主库中"有可用 DOI（papers.doi 或 meta.title_match 找回的 DOI）
且非迁移论文（migrated=1，其三源数据已随旧库迁入）"的论文，按 ckey 去重。

源与节奏（沿用 p13 实测参数）：
  fetch-s2   Semantic Scholar batch API，100 DOI/请求，3s/批，1 并发；
             连续失败超 100 批自动停本轮（缓存断点续跑）。
  fetch-cr   Crossref /works/{doi}，礼貌池（UA 带 mailto），0.15s，8 并发。
  fetch-coci OpenCitations /citations/doi:{doi}，0.34s，12 并发（用满 180/min）。
  match-doi  Crossref query.bibliographic 精确标题+年份匹配，结果写 meta。
"""
import json
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from ecdb.cleaning import normalize_title

from . import _db
from ._cache import JsonlSink, cache_dir
from ._rate import RateLimiter, http_json

CR_URL = "https://api.crossref.org"
S2_URL = "https://api.semanticscholar.org/graph/v1"
OC_URL = "https://api.opencitations.net/index/v2"
MAILTO = "ec-audit@example.org"  # Crossref 礼貌池联系邮箱（占位，用户可后续替换）

UA_CR = {"User-Agent": f"EC_MAP_2026-citations/1.0 (mailto:{MAILTO})"}
UA_OC = {"User-Agent": f"EC_MAP_2026-citations/1.0 (mailto:{MAILTO})"}
UA_S2 = {"User-Agent": "EC_MAP_2026-citations/1.0"}

S2_FIELDS = ("title,externalIds,year,citationCount,referenceCount,"
             "references.externalIds,references.year,"
             "citations.externalIds,citations.year")


def _targets(conn_ro):
    """[(ckey, acc, doi)]：待抓取论文（排除已迁移的）。"""
    rows = conn_ro.execute(
        "SELECT p.accession_no, COALESCE(m.doi, p.doi) AS doi, "
        "       COALESCE(m.migrated, 0) AS migrated "
        "FROM papers p LEFT JOIN paper_cit_meta m ON m.accession_no=p.accession_no "
        "WHERE COALESCE(m.doi, p.doi) IS NOT NULL").fetchall()
    seen, out = set(), []
    for acc, doi, migrated in rows:
        if migrated:
            continue
        ckey = doi.strip().lower()
        if ckey in seen:
            continue
        seen.add(ckey)
        out.append((ckey, acc, ckey))
    return out


def _s2_ext_doi(w):
    return _dbnorm(((w or {}).get("externalIds") or {}).get("DOI"))


def _dbnorm(d):
    from ecdb._db import normalize_doi
    return normalize_doi(d)


def fetch_s2(limit=None):
    """Semantic Scholar batch：citations 列表（未认证截断 ~1 万）+ 计数 + s2_id。"""
    sink = JsonlSink(cache_dir() / "s2.jsonl")
    todo = [(c, a, d) for c, a, d in _targets(_db.connect_ro()) if c not in sink.done]
    if limit:
        todo = todo[:limit]
    print("[s2] todo=%d done=%d" % (len(todo), len(sink)))
    if not todo:
        sink.close()
        return
    limiter = RateLimiter(3.0, floor=2.5)  # 未认证共享配额，保守节奏
    t0 = time.time()
    stat = {"req": 0, "miss": 0, "fail": 0}
    stop = threading.Event()
    BATCH = 100

    def worker(chunk):
        if stop.is_set():
            return
        ids = [f"DOI:{doi}" for _, _, doi in chunk]
        url = f"{S2_URL}/paper/batch?fields={S2_FIELDS}"
        body = json.dumps({"ids": ids}).encode()
        try:
            status, arr = http_json(url, {**UA_S2, "Content-Type": "application/json"},
                                    limiter, max_tries=5, method="POST", body=body)
        except RuntimeError:
            stat["fail"] += 1
            if stat["fail"] > 100:
                stop.set()
                print("[s2] 连续失败过多，停止本轮（缓存续跑）")
            return
        if status != 200 or arr is None or len(arr) != len(chunk):
            stat["fail"] += 1
            if stat["fail"] > 100:
                stop.set()
                print("[s2] 连续失败过多，停止本轮（缓存续跑）")
            return
        stat["fail"] = 0
        stat["req"] += 1
        for (ckey, _acc, doi), rec in zip(chunk, arr):
            if not rec:
                sink.add({"ckey": ckey, "doi": doi, "miss": True})
                stat["miss"] += 1
                continue
            cites = [{"doi": _s2_ext_doi(c), "year": c.get("year")}
                     for c in rec.get("citations") or []]
            refs = [{"doi": _s2_ext_doi(r), "year": r.get("year")}
                    for r in rec.get("references") or []]
            sink.add({"ckey": ckey, "doi": doi, "s2id": rec.get("paperId"),
                      "cit_count": rec.get("citationCount"),
                      "ref_count": rec.get("referenceCount"),
                      "refs": refs, "cites": cites,
                      "cites_truncated": len(cites) >= 9999,
                      "refs_truncated": len(refs) >= 9999})
        if stat["req"] % 50 == 0:
            rate = stat["req"] / (time.time() - t0)
            left = (len(todo) / BATCH - stat["req"]) / max(rate, 1e-9) / 60
            print("[s2] req=%d/%d miss=%d fail=%d interval=%.2fs eta=%.0fmin" % (
                stat["req"], len(todo) // BATCH, stat["miss"], stat["fail"],
                limiter.min_interval, left))

    chunks = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    with ThreadPoolExecutor(max_workers=1) as ex:
        list(ex.map(worker, chunks))
    sink.close()
    print("[s2] finished req=%d miss=%d in %.1fmin" % (
        stat["req"], stat["miss"], (time.time() - t0) / 60))


def fetch_cr(limit=None):
    """Crossref：出版商存缴参考清单（出边）+ is-referenced-by-count。"""
    sink = JsonlSink(cache_dir() / "cr.jsonl")
    todo = [(c, a, d) for c, a, d in _targets(_db.connect_ro()) if c not in sink.done]
    if limit:
        todo = todo[:limit]
    print("[cr] todo=%d done=%d" % (len(todo), len(sink)))
    if not todo:
        sink.close()
        return
    limiter = RateLimiter(0.15, floor=0.1)  # polite pool ~7 req/s
    t0 = time.time()
    stat = {"ok": 0, "404": 0, "refs": 0}

    def worker(ckey, _acc, doi):
        url = f"{CR_URL}/works/{urllib.parse.quote(doi)}"
        try:
            status, obj = http_json(url, UA_CR, limiter, max_tries=5)
        except RuntimeError:
            return  # 重试耗尽：不写缓存，下次续跑
        msg = (obj or {}).get("message") if status == 200 else None
        if status == 404:
            sink.add({"ckey": ckey, "doi": doi, "status": 404,
                      "cited_by_count": None, "reference_count": None, "refs": []})
            stat["404"] += 1
            return
        if status != 200 or msg is None:
            return
        refs = []
        for r in msg.get("reference") or []:
            refs.append({"doi": _dbnorm(r.get("DOI")),
                         "unstructured": r.get("unstructured") or r.get("article-title"),
                         "key": r.get("key"),
                         "year": r.get("year")})
        sink.add({"ckey": ckey, "doi": doi, "status": 200,
                  "cited_by_count": msg.get("is-referenced-by-count"),
                  "reference_count": msg.get("reference-count"),
                  "refs": refs})
        stat["ok"] += 1
        stat["refs"] += len(refs)
        done = stat["ok"] + stat["404"]
        if done % 2000 == 0:
            rate = done / (time.time() - t0)
            eta = (len(todo) - done) / max(rate, 1e-9) / 60
            print("[cr] %d/%d ok=%d 404=%d refs=%d %.1f/s eta=%.0fmin" % (
                done, len(todo), stat["ok"], stat["404"], stat["refs"], rate, eta))

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(lambda t: worker(*t), todo))
    sink.close()
    print("[cr] finished ok=%d 404=%d refs=%d in %.1fmin" % (
        stat["ok"], stat["404"], stat["refs"], (time.time() - t0) / 60))


def fetch_coci(limit=None):
    """OpenCitations COCI：入边（施引文献 DOI）。"""
    sink = JsonlSink(cache_dir() / "coci.jsonl")
    todo = [(c, a, d) for c, a, d in _targets(_db.connect_ro()) if c not in sink.done]
    if limit:
        todo = todo[:limit]
    print("[coci] todo=%d done=%d" % (len(todo), len(sink)))
    if not todo:
        sink.close()
        return
    limiter = RateLimiter(0.34, floor=0.34)  # 用满 180 req/min
    t0 = time.time()
    stat = {"done": 0, "edges": 0, "404": 0}

    def parse_ids(s):
        out = {}
        for tok in (s or "").split():
            if tok.startswith("doi:"):
                out["doi"] = _dbnorm(tok[4:])
        return out

    def worker(ckey, _acc, doi):
        url = f"{OC_URL}/citations/doi:{doi}"
        try:
            status, arr = http_json(url, UA_OC, limiter, max_tries=4)
        except RuntimeError:
            return  # 瞬时错误：下次续跑
        cites = []
        if status == 200 and arr:
            for e in arr:
                ids = parse_ids(e.get("citing", ""))
                yr = (e.get("creation") or "")[:4]
                cites.append({"doi": ids.get("doi"),
                              "year": int(yr) if yr.isdigit() else None})
        elif status != 200:
            stat["404"] += 1  # 404 = COCI 无此记录；仍写缓存（空边）避免重抓
        sink.add({"ckey": ckey, "doi": doi, "status": status, "cites": cites})
        stat["done"] += 1
        stat["edges"] += len(cites)
        if stat["done"] % 1000 == 0:
            rate = stat["done"] / (time.time() - t0)
            eta = (len(todo) - stat["done"]) / max(rate, 1e-9) / 60
            print("[coci] %d/%d edges=%d 404=%d eta=%.0fmin" % (
                stat["done"], len(todo), stat["edges"], stat["404"], eta))

    with ThreadPoolExecutor(max_workers=12) as ex:
        list(ex.map(lambda t: worker(*t), todo))
    sink.close()
    print("[coci] finished papers=%d edges=%d in %.1fmin" % (
        stat["done"], stat["edges"], (time.time() - t0) / 60))


# ---- match-doi-s2：无 DOI 论文的第二来源标题匹配 -----------------------------

OA_URL = "https://api.openalex.org"


def match_s2(limit=None):
    """无 DOI 论文标题匹配第二来源：Semantic Scholar 优先，429/未命中回退 OpenAlex。

    命中条件统一为规范化标题全等 + 年份 ±1（OpenAlex 用 title.search 缩小候选）。
    命中写 paper_cit_meta.doi（doi_source='title_match'），原 no_doi 状态复位为
    pending 进入抓取队列；主库 papers.doi 的回写由 ecdb enrich 统一执行。
    """
    conn_ro = _db.connect_ro()
    todo = [(r["accession_no"], r["title"], r["pub_year"])
            for r in _no_doi_papers(conn_ro)]
    conn_ro.close()
    if limit:
        todo = todo[:limit]
    sink = JsonlSink(cache_dir() / "titlematch_s2.jsonl", key="acc")
    todo = [t for t in todo if t[0] not in sink.done]
    print("[match-s2] todo=%d done=%d" % (len(todo), len(sink)))
    if not todo:
        sink.close()
        return
    lim_s2 = RateLimiter(3.0, floor=2.0)   # S2 未认证共享配额，保守节奏
    lim_oa = RateLimiter(0.5, floor=0.3)   # OpenAlex polite pool（单任务串行使用）
    t0 = time.time()
    stat = {"hit_s2": 0, "hit_oa": 0, "miss": 0, "fail": 0}
    lock = threading.Lock()
    # S2 熔断：连续失败 >=5 次视为共享池配额耗尽，本次运行不再尝试 S2
    s2_state = {"consec_fail": 0, "disabled": False}

    def s2_ok():
        with lock:
            return not s2_state["disabled"]

    def s2_note(ok):
        with lock:
            if ok:
                s2_state["consec_fail"] = 0
            else:
                s2_state["consec_fail"] += 1
                if s2_state["consec_fail"] >= 5:
                    s2_state["disabled"] = True
                    print("[match-s2] S2 连续失败 5 次，本次运行熔断，仅用 OpenAlex")
    from ecdb import _paths
    reports = _paths.project_root() / "reports"
    reports.mkdir(exist_ok=True)
    csv_path = reports / "title_match_s2.csv"
    csv_f = open(csv_path, "a", encoding="utf-8-sig", newline="")
    csv_f.seek(0, 2)
    if csv_f.tell() == 0:
        csv_f.write("accession_no,title,year,matched_doi,matched_title,matched_year,matched_source\n")

    def _write_hit(acc, title, year, hit):
        doi, ct, cy, src = hit
        rw = _db.connect_rw()
        rw.execute(
            "INSERT INTO paper_cit_meta (accession_no, doi, doi_source, "
            "refs_status, cites_status) VALUES (?,?, 'title_match','pending','pending') "
            "ON CONFLICT(accession_no) DO UPDATE SET doi=excluded.doi, "
            "doi_source='title_match', "
            "refs_status=CASE WHEN paper_cit_meta.refs_status='no_doi' THEN 'pending' "
            "ELSE paper_cit_meta.refs_status END, "
            "cites_status=CASE WHEN paper_cit_meta.cites_status='no_doi' THEN 'pending' "
            "ELSE paper_cit_meta.cites_status END", (acc, doi))
        rw.commit()
        rw.close()
        with lock:
            stat["hit_s2" if src == "s2" else "hit_oa"] += 1
            csv_f.write("%s,%s,%s,%s,%s,%s,%s\n" % (
                acc, title.replace(",", " "), year or "", doi,
                (ct or "").replace(",", " "), cy or "", src))
            sink.add({"acc": acc, "title": title, "year": year,
                      "matched_doi": doi, "source": src})

    def worker(acc, title, year):
        nt = normalize_title(title)
        hit = None
        # -- OpenAlex 优先：title.search + 年份过滤（配额宽裕，速度快）
        try:
            url = (f"{OA_URL}/works?filter=title.search:{urllib.parse.quote(title)},"
                   f"publication_year:{year}&per-page=5&select=doi,display_name,"
                   f"publication_year&mailto={MAILTO}")
            status, obj = http_json(url, UA_CR, lim_oa, max_tries=4)
            if status == 200 and obj:
                for item in obj.get("results") or []:
                    ct = item.get("display_name")
                    doi = _dbnorm(item.get("doi"))
                    cy = item.get("publication_year")
                    if (ct and doi and normalize_title(ct) == nt
                            and (year is None or cy is None
                                 or abs(int(cy) - int(year)) <= 1)):
                        hit = (doi, ct, cy, "openalex")
                        break
        except RuntimeError:
            with lock:
                stat["fail"] += 1
        # -- S2 /paper/search/match 兜底（未认证共享池，限流时放弃）
        if hit is None and s2_ok():
            try:
                url = (f"{S2_URL}/paper/search/match?query={urllib.parse.quote(title)}"
                       "&fields=title,year,externalIds")
                status, obj = http_json(url, UA_S2, lim_s2, max_tries=2)
                if status == 200 and obj:
                    for item in obj.get("data") or []:
                        ct = item.get("title")
                        doi = ((item.get("externalIds") or {}).get("DOI") or "").strip().lower()
                        cy = item.get("year")
                        if (ct and doi and normalize_title(ct) == nt
                                and (year is None or cy is None
                                     or abs(int(cy) - int(year)) <= 1)):
                            hit = (doi, ct, cy, "s2")
                            break
                s2_note(status == 200)
            except RuntimeError:
                s2_note(False)
        if hit:
            _write_hit(acc, title, year, hit)
        else:
            with lock:
                stat["miss"] += 1
        n = stat["hit_s2"] + stat["hit_oa"] + stat["miss"]
        if n % 50 == 0:
            eta = (len(todo) - n) / max(n / (time.time() - t0), 1e-9) / 60
            print("[match-s2] %d/%d s2=%d oa=%d miss=%d fail=%d eta=%.0fmin" % (
                n, len(todo), stat["hit_s2"], stat["hit_oa"], stat["miss"],
                stat["fail"], eta))

    with ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(lambda t: worker(*t), todo))
    csv_f.close()
    sink.close()
    print("[match-s2] finished s2=%d oa=%d miss=%d fail=%d in %.1fmin -> %s" % (
        stat["hit_s2"], stat["hit_oa"], stat["miss"], stat["fail"],
        (time.time() - t0) / 60, csv_path))


# ---- match-doi-relax：Crossref 放宽通道（rows=10 + query.title 变体）---------

def match_doi_relax(limit=None):
    """match_doi 未命中者的 Crossref 复查：候选 5→10 条，并追加 query.title
    检索变体。命中门槛不变（规范化标题全等 + 年份 ±1）。"""
    conn_ro = _db.connect_ro()
    todo = [(r["accession_no"], r["title"], r["pub_year"])
            for r in _no_doi_papers(conn_ro)]
    conn_ro.close()
    if limit:
        todo = todo[:limit]
    sink = JsonlSink(cache_dir() / "titlematch_relax.jsonl", key="acc")
    todo = [t for t in todo if t[0] not in sink.done]
    print("[match-relax] todo=%d done=%d" % (len(todo), len(sink)))
    if not todo:
        sink.close()
        return
    limiter = RateLimiter(0.3, floor=0.25)
    t0 = time.time()
    stat = {"hit": 0, "miss": 0, "fail": 0}
    lock = threading.Lock()

    def _find(title, year, nt):
        for query_key in ("query.bibliographic", "query.title"):
            url = (f"{CR_URL}/works?{query_key}={urllib.parse.quote(title)}"
                   "&rows=10&select=DOI,title,issued")
            try:
                status, obj = http_json(url, MATCH_UA, limiter, max_tries=4)
            except RuntimeError:
                return None, True
            if status != 200 or not obj:
                continue
            for item in (obj.get("message") or {}).get("items") or []:
                ct = (item.get("title") or [None])[0]
                if not ct:
                    continue
                try:
                    cy = (item["issued"]["date-parts"] or [[None]])[0][0]
                except Exception:
                    cy = None
                if normalize_title(ct) == nt and (year is None or cy is None
                                                  or abs(int(cy) - int(year)) <= 1):
                    return (item["DOI"].lower(), ct, cy), False
        return None, False

    def worker(acc, title, year):
        nt = normalize_title(title)
        hit, failed = _find(title, year, nt)
        if hit:
            rw = _db.connect_rw()
            rw.execute(
                "INSERT INTO paper_cit_meta (accession_no, doi, doi_source, "
                "refs_status, cites_status) VALUES (?,?, 'title_match','pending','pending') "
                "ON CONFLICT(accession_no) DO UPDATE SET doi=excluded.doi, "
                "doi_source='title_match', "
                "refs_status=CASE WHEN paper_cit_meta.refs_status='no_doi' THEN 'pending' "
                "ELSE paper_cit_meta.refs_status END, "
                "cites_status=CASE WHEN paper_cit_meta.cites_status='no_doi' THEN 'pending' "
                "ELSE paper_cit_meta.cites_status END", (acc, hit[0]))
            rw.commit()
            rw.close()
            with lock:
                stat["hit"] += 1
                sink.add({"acc": acc, "title": title, "year": year,
                          "matched_doi": hit[0]})
        else:
            with lock:
                stat["fail" if failed else "miss"] += 1
        n = stat["hit"] + stat["miss"]
        if n % 100 == 0:
            eta = (len(todo) - n) / max(n / (time.time() - t0), 1e-9) / 60
            print("[match-relax] %d/%d hit=%d miss=%d fail=%d eta=%.0fmin" % (
                n, len(todo), stat["hit"], stat["miss"], stat["fail"], eta))

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(lambda t: worker(*t), todo))
    sink.close()
    print("[match-relax] finished hit=%d miss=%d fail=%d in %.1fmin" % (
        stat["hit"], stat["miss"], stat["fail"], (time.time() - t0) / 60))


# ---- match-doi：无 DOI 论文的标题匹配 ---------------------------------------

MATCH_UA = UA_CR


def _no_doi_papers(conn_ro):
    """[(acc, title, year)]：主库无 DOI 且 meta 未找回 DOI 的论文。"""
    return conn_ro.execute(
        "SELECT p.accession_no, p.title, p.pub_year FROM papers p "
        "LEFT JOIN paper_cit_meta m ON m.accession_no=p.accession_no "
        "WHERE p.doi IS NULL AND COALESCE(m.doi, '') = ''").fetchall()


def match_doi(limit=None):
    """Crossref query.bibliographic 候选 + 规范化标题精确相等 + 年份 ±1。

    命中写 paper_cit_meta.doi（doi_source='title_match'），不写主库 papers。
    全量匹配结果导出 reports/title_match.csv 供人工核对。
    """
    conn_ro = _db.connect_ro()
    todo = [(r["accession_no"], r["title"], r["pub_year"])
            for r in _no_doi_papers(conn_ro)]
    if limit:
        todo = todo[:limit]
    print("[match-doi] todo=%d" % len(todo))
    if not todo:
        return
    limiter = RateLimiter(0.3, floor=0.25)
    t0 = time.time()
    stat = {"hit": 0, "miss": 0, "fail": 0}
    lock = threading.Lock()
    sink = JsonlSink(cache_dir() / "titlematch.jsonl", key="acc")
    from ecdb import _paths
    reports = _paths.project_root() / "reports"
    reports.mkdir(exist_ok=True)
    csv_path = reports / "title_match.csv"
    # 追加模式：重跑时保留已写入的核对行（todo 过滤保证同一论文不会重复出现）
    csv_exists = csv_path.exists()
    csv_f = open(csv_path, "a", encoding="utf-8-sig", newline="")
    if not csv_exists:
        csv_f.write("accession_no,title,year,matched_doi,matched_title,matched_year\n")

    def worker(acc, title, year):
        nt = normalize_title(title)
        url = (f"{CR_URL}/works?query.bibliographic={urllib.parse.quote(title)}"
               "&rows=5&select=DOI,title,issued")
        try:
            status, obj = http_json(url, MATCH_UA, limiter, max_tries=4)
        except RuntimeError:
            with lock:
                stat["fail"] += 1
            return
        hit = None
        if status == 200 and obj:
            for item in (obj.get("message") or {}).get("items") or []:
                ct = (item.get("title") or [None])[0]
                if not ct:
                    continue
                try:
                    cy = (item["issued"]["date-parts"] or [[None]])[0][0]
                except Exception:
                    cy = None
                if normalize_title(ct) == nt and (year is None or cy is None
                                                  or abs(int(cy) - int(year)) <= 1):
                    hit = (item["DOI"].lower(), ct, cy)
                    break
        if hit:
            rw = _db.connect_rw()
            rw.execute(
                "INSERT INTO paper_cit_meta (accession_no, doi, doi_source, "
                "refs_status, cites_status) VALUES (?,?, 'title_match','pending','pending') "
                "ON CONFLICT(accession_no) DO UPDATE SET doi=excluded.doi, "
                "doi_source='title_match'", (acc, hit[0]))
            rw.commit()
            rw.close()
            with lock:
                stat["hit"] += 1
                csv_f.write("%s,%s,%s,%s,%s,%s\n" % (
                    acc, title.replace(",", " "), year or "",
                    hit[0], (hit[1] or "").replace(",", " "), hit[2] or ""))
            sink.add({"acc": acc, "title": title, "year": year,
                      "matched_doi": hit[0]})
        else:
            with lock:
                stat["miss"] += 1
        n = stat["hit"] + stat["miss"]
        if n % 100 == 0:
            eta = (len(todo) - n) / max(n / (time.time() - t0), 1e-9) / 60
            print("[match-doi] %d/%d hit=%d miss=%d fail=%d eta=%.0fmin" % (
                n, len(todo), stat["hit"], stat["miss"], stat["fail"], eta))

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(lambda t: worker(*t), todo))
    csv_f.close()
    sink.close()
    print("[match-doi] finished hit=%d miss=%d fail=%d in %.1fmin -> %s" % (
        stat["hit"], stat["miss"], stat["fail"], (time.time() - t0) / 60, csv_path))
