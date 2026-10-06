"""load —— 把 cache_citations/*.jsonl 的抓取结果幂等写入主库引文表。

ckey -> accession 映射实时从主库构建（DOI 唯一；noDOI:<acc> 直接映射），
因此主库被 build --rebuild 重建或去重换 keeper 后，重跑 load 即可从缓存恢复。
meta 的 cr_done/s2_done/coci_done 记录各源是否完成抓取（含"该源确认无记录"），
refs_status/cites_status 在批次末尾按"表内有行则 ok，源已完成则 none"重算。
"""
import hashlib
import json

from . import _db
from ._cache import cache_dir


def _mdk(*parts) -> str:
    return "x:" + hashlib.md5("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


class JsonlIter:
    """逐行读取 JSONL，跳过残缺行。"""

    def __init__(self, path):
        self.path = path

    def __iter__(self):
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def _mdk(*parts) -> str:
    return "x:" + hashlib.md5("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


def _acc_map(conn_ro):
    """ckey(doi) -> [accession_no]；含 title_match 找回的 DOI。"""
    m = {}
    for acc, doi in conn_ro.execute(
            "SELECT accession_no, doi FROM papers WHERE doi IS NOT NULL AND doi != ''"):
        m.setdefault(doi.strip().lower(), []).append(acc)
    for acc, doi in conn_ro.execute(
            "SELECT accession_no, doi FROM paper_cit_meta "
            "WHERE doi IS NOT NULL AND doi != ''"):
        m.setdefault(doi.strip().lower(), []).append(acc)
    return m


META_S2 = ("UPDATE paper_cit_meta SET s2_id=COALESCE(?,s2_id), "
           "s2_cit_count=COALESCE(?,s2_cit_count), "
           "s2_ref_count=COALESCE(?,s2_ref_count), s2_done=1, fetched_at=? "
           "WHERE accession_no=?")
META_CR = ("UPDATE paper_cit_meta SET cr_cit_count=COALESCE(?,cr_cit_count), "
           "cr_ref_count=COALESCE(?,cr_ref_count), cr_done=1, fetched_at=? "
           "WHERE accession_no=?")
META_COCI = ("UPDATE paper_cit_meta SET coci_done=1, fetched_at=? "
             "WHERE accession_no=?")
META_TOUCH = ("INSERT INTO paper_cit_meta (accession_no, doi, doi_source, "
              "refs_status, cites_status) VALUES (?,?, 'ei','pending','pending') "
              "ON CONFLICT(accession_no) DO NOTHING")


def _flush(rows_out, rows_in, meta, rw, counters):
    if rows_out:
        rw.executemany(
            "INSERT OR IGNORE INTO paper_refs_out (accession_no, source, cited_key,"
            " seq, cited_doi, cited_title, cited_year) VALUES (?,?,?,?,?,?,?)",
            rows_out)
    if rows_in:
        rw.executemany(
            "INSERT OR IGNORE INTO paper_cited_in (accession_no, source, citing_key,"
            " citing_doi, citing_year) VALUES (?,?,?,?,?)", rows_in)
    if meta:
        rw.executemany(META_TOUCH, meta[0])
        rw.executemany(META_S2, meta[1])
        rw.executemany(META_CR, meta[2])
        rw.executemany(META_COCI, meta[3])
    rw.commit()
    counters["out"] += len(rows_out)
    counters["in"] += len(rows_in)


def load():
    from .fetchers import _dbnorm  # 复用 normalize_doi 包装
    conn_ro = _db.connect_ro()
    rw = _db.connect_rw()
    _db.ensure_schema(rw)
    amap = _acc_map(conn_ro)
    counters = {"out": 0, "in": 0, "orphan": 0, "s2": 0, "cr": 0, "coci": 0}
    rows_out, rows_in = [], []
    meta_touch, meta_s2, meta_cr, meta_coci = [], [], [], []
    touched = set()
    now = _db.utcnow()

    def flush():
        _flush(rows_out, rows_in, (meta_touch, meta_s2, meta_cr, meta_coci),
               rw, counters)
        rows_out.clear(); rows_in.clear()
        meta_touch.clear(); meta_s2.clear(); meta_cr.clear(); meta_coci.clear()

    # --- s2.jsonl ---
    p = cache_dir() / "s2.jsonl"
    if p.exists():
        for rec in JsonlIter(p):
            counters["s2"] += 1
            accs = amap.get(rec["ckey"])
            if not accs:
                counters["orphan"] += 1
                continue
            for i, acc in enumerate(accs):
                meta_touch.append((acc, rec.get("doi"),))
                meta_s2.append((rec.get("s2id"), rec.get("cit_count"),
                                rec.get("ref_count"), now, acc))
                touched.add(acc)
                if rec.get("miss"):
                    continue
                for j, r in enumerate(rec.get("refs") or []):
                    d = _dbnorm(r.get("doi"))
                    rows_out.append((acc, "s2", d or _mdk(rec["ckey"], "s2r", i, j),
                                     None, d, None, r.get("year")))
                for j, c in enumerate(rec.get("cites") or []):
                    d = _dbnorm(c.get("doi"))
                    rows_in.append((acc, "s2", d or _mdk(rec["ckey"], "s2c", i, j),
                                    d, c.get("year")))
            if len(rows_out) + len(rows_in) >= _db.BATCH_ROWS:
                flush()
        flush()
        print("[load] s2 缓存 %d 条，orphan %d" % (counters["s2"], counters["orphan"]))

    # --- cr.jsonl ---
    p = cache_dir() / "cr.jsonl"
    if p.exists():
        for rec in JsonlIter(p):
            counters["cr"] += 1
            accs = amap.get(rec["ckey"])
            if not accs:
                counters["orphan"] += 1
                continue
            for i, acc in enumerate(accs):
                meta_touch.append((acc, rec.get("doi")))
                meta_cr.append((rec.get("cited_by_count"), rec.get("reference_count"),
                                now, acc))
                touched.add(acc)
                for j, r in enumerate(rec.get("refs") or []):
                    d = _dbnorm(r.get("doi"))
                    rows_out.append((acc, "crossref",
                                     d or _mdk(rec["ckey"], "cr", i, j),
                                     j + 1, d, r.get("unstructured"), r.get("year")))
            if len(rows_out) >= _db.BATCH_ROWS:
                flush()
        flush()
        print("[load] cr 缓存 %d 条" % counters["cr"])

    # --- coci.jsonl ---
    p = cache_dir() / "coci.jsonl"
    if p.exists():
        for rec in JsonlIter(p):
            counters["coci"] += 1
            accs = amap.get(rec["ckey"])
            if not accs:
                counters["orphan"] += 1
                continue
            for i, acc in enumerate(accs):
                meta_touch.append((acc, rec.get("doi")))
                meta_coci.append((now, acc))
                touched.add(acc)
                for j, c in enumerate(rec.get("cites") or []):
                    d = _dbnorm(c.get("doi"))
                    rows_in.append((acc, "oc", d or _mdk(rec["ckey"], "oc", i, j),
                                    d, c.get("year")))
            if len(rows_in) >= _db.BATCH_ROWS:
                flush()
        flush()
        print("[load] coci 缓存 %d 条" % counters["coci"])

    # --- 重算被触碰论文的状态 ---
    for chunk in _db.chunked(sorted(touched), 5000):
        ph = ",".join("?" * len(chunk))
        rw.execute(
            "UPDATE paper_cit_meta SET refs_status = CASE WHEN EXISTS("
            "  SELECT 1 FROM paper_refs_out r WHERE r.accession_no=paper_cit_meta.accession_no)"
            " THEN 'ok' WHEN COALESCE(cr_done,0)=1 THEN 'none' ELSE refs_status END "
            "WHERE accession_no IN (%s)" % ph, chunk)
        rw.execute(
            "UPDATE paper_cit_meta SET cites_status = CASE WHEN EXISTS("
            "  SELECT 1 FROM paper_cited_in c WHERE c.accession_no=paper_cit_meta.accession_no)"
            " THEN 'ok' WHEN COALESCE(s2_done,0)+COALESCE(coci_done,0)>0 THEN 'none'"
            " ELSE cites_status END "
            "WHERE accession_no IN (%s)" % ph, chunk)
        rw.commit()

    rw.close(); conn_ro.close()
    counters["touched"] = len(touched)
    print("[load] 完成：%s" % counters)
    return counters
