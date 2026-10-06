"""migrate —— 把 EC_History/ec_corpus.db 的引文数据按 DOI 重键迁入主库。

旧库 cit_out/cit_in/cit_meta 以旧 papers.id（整数）为键；本模块把旧 canonical
论文的 DOI 映射到新库 accession_no 后重键写入 paper_refs_out / paper_cited_in /
paper_cit_meta。旧库中无 DOI 的论文尝试"规范化标题+年份"库内匹配（不调 API）。

幂等：全部 INSERT OR IGNORE / upsert，重跑行数不变。
被引/参考条目 cited_key 规则：
  - 有 DOI：DOI 本身
  - 无 DOI 有 OpenAlex W ID：'oa:<wid>'
  - 都没有：'x:'+md5(f"mig|{旧pid}|{旧rowid}")（旧库是静态快照，rowid 稳定，
    保证重跑幂等）
"""
import hashlib
import sqlite3
import time

from ecdb.cleaning import normalize_title

from . import _db


def _mdk(*parts) -> str:
    return "x:" + hashlib.md5("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


def _open_old(path):
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _log(msg, t0=None):
    if t0 is not None:
        print("[migrate] %s (%.1fmin)" % (msg, (time.time() - t0) / 60))
    else:
        print("[migrate] " + msg)


def _title_index(rw):
    """新库 (规范化标题, 年份) -> [accession_no]，供旧库无 DOI 论文库内匹配。"""
    idx = {}
    for acc, title, year in rw.execute(
            "SELECT accession_no, title, pub_year FROM papers"):
        nt = normalize_title(title)
        if nt:
            idx.setdefault((nt, year), []).append(acc)
    return idx


META_UPSERT = """
INSERT INTO paper_cit_meta
  (accession_no, doi, doi_source, s2_id, oa_id, oa_cited_by_count,
   s2_cit_count, s2_ref_count, cr_cit_count, refs_status, cites_status, migrated)
VALUES (?, ?, 'ei', ?, ?, ?, ?, ?, ?, 'migrated', 'migrated', 1)
ON CONFLICT(accession_no) DO UPDATE SET
  s2_id=COALESCE(excluded.s2_id, paper_cit_meta.s2_id),
  oa_id=COALESCE(excluded.oa_id, paper_cit_meta.oa_id),
  oa_cited_by_count=COALESCE(excluded.oa_cited_by_count, paper_cit_meta.oa_cited_by_count),
  cr_cit_count=excluded.cr_cit_count,
  s2_cit_count=excluded.s2_cit_count,
  s2_ref_count=excluded.s2_ref_count,
  doi=COALESCE(paper_cit_meta.doi, excluded.doi),
  doi_source=COALESCE(paper_cit_meta.doi_source, excluded.doi_source),
  migrated=1,
  refs_status=CASE WHEN paper_cit_meta.refs_status='pending' THEN 'migrated'
                   ELSE paper_cit_meta.refs_status END,
  cites_status=CASE WHEN paper_cit_meta.cites_status='pending' THEN 'migrated'
                    ELSE paper_cit_meta.cites_status END
"""


def migrate(old_db=None, verbose=True, meta_only=False):
    old_path = str(old_db) if old_db else str(_db.old_db_default())
    old = _open_old(old_path)
    rw = _db.connect_rw()
    _db.ensure_schema(rw)
    t0 = time.time()

    # 1) 新库 DOI -> [accession_no] 与 accession -> doi 快照
    doi2accs, acc2doi = {}, {}
    for acc, doi in rw.execute(
            "SELECT accession_no, doi FROM papers WHERE doi IS NOT NULL AND doi != ''"):
        d = doi.strip().lower()
        doi2accs.setdefault(d, []).append(acc)
        acc2doi[acc] = d
    _log("新库 DOI 索引 %d 项" % len(doi2accs))

    # 2) 旧库 canonical 论文：有 DOI 的按 DOI 映射；无 DOI 的按标题+年份匹配
    pid2accs = {}
    n_mapped = 0
    for pid, doi in old.execute(
            "SELECT p.id, p.doi FROM papers p JOIN cit_meta m ON m.paper_id=p.id "
            "WHERE p.id=p.canonical_id AND p.doi IS NOT NULL AND p.doi != ''"):
        accs = doi2accs.get(doi.strip().lower())
        if accs:
            pid2accs[pid] = accs
            n_mapped += 1
    n_title = 0
    cand = old.execute(
        "SELECT p.id, p.title, p.year FROM papers p JOIN cit_meta m ON m.paper_id=p.id "
        "WHERE p.id=p.canonical_id AND (p.doi IS NULL OR p.doi='') "
        "AND p.title IS NOT NULL").fetchall()
    if cand:
        tidx = _title_index(rw)
        for pid, title, year in cand:
            nt = normalize_title(title)
            accs = tidx.get((nt, year)) or tidx.get((nt, None))
            if accs and len(accs) == 1:
                pid2accs[pid] = accs
                n_title += 1
    _log("旧库可映射论文 %d（DOI %d + 标题匹配 %d）；旧库 canonical 无 DOI 未匹配 %d" % (
        len(pid2accs), n_mapped, n_title,
        old.execute("SELECT COUNT(*) FROM papers p JOIN cit_meta m ON m.paper_id=p.id "
                    "WHERE p.id=p.canonical_id AND (p.doi IS NULL OR p.doi='')").fetchone()[0]
        - n_title))

    n_out = n_in = 0
    per_src_out = per_src_in = {}
    if not meta_only:
        n_out, per_src_out = _migrate_edges_out(old, rw, pid2accs, t0)
        n_in, per_src_in = _migrate_edges_in(old, rw, pid2accs, t0)

    # 5) 迁移 cit_meta（标识符 + 计数）
    meta_rows = []
    for pid, s2id, oaid, oacbc, s2cit, s2ref, crcit in old.execute(
            "SELECT m.paper_id, m.s2_id, m.oa_id, m.oa_cited_by_count, "
            "m.s2_cit_count, m.s2_ref_count, m.cr_cit_count FROM cit_meta m "
            "JOIN papers p ON p.id=m.paper_id WHERE p.id=p.canonical_id"):
        accs = pid2accs.get(pid)
        if not accs:
            continue
        for acc in accs:
            meta_rows.append((acc, acc2doi.get(acc), s2id, oaid, oacbc,
                              s2cit, s2ref, crcit))
    for chunk in _db.chunked(meta_rows, 5000):
        rw.executemany(META_UPSERT, chunk)
        rw.commit()
    n_meta = rw.execute(
        "SELECT COUNT(*) FROM paper_cit_meta WHERE migrated=1").fetchone()[0]
    _log("meta 完成：迁移标记 %d 篇" % n_meta, t0)

    old.close()
    rw.close()
    return {"mapped": len(pid2accs), "mapped_by_doi": n_mapped,
            "mapped_by_title": n_title, "out_inserted": n_out,
            "in_inserted": n_in, "meta_migrated": n_meta,
            "per_src_out": per_src_out, "per_src_in": per_src_in}


def _migrate_edges_out(old, rw, pid2accs, t0):
    """迁移 cit_out（出边）。返回 (插入行数, 库内分源现量)。"""
    out_sql = ("INSERT OR IGNORE INTO paper_refs_out "
               "(accession_no, source, cited_key, seq, cited_doi, cited_title, cited_year) "
               "VALUES (?,?,?,NULL,?,NULL,NULL)")
    batch, n_out = [], 0
    for rowid, pid, oa, doi, src in old.execute(
            "SELECT rowid, paper_id, cited_oa, cited_doi, source FROM cit_out"):
        accs = pid2accs.get(pid)
        if not accs:
            continue
        doi = doi.strip().lower() if doi else None
        key = doi or ("oa:" + oa if oa else _mdk("mig", pid, rowid))
        for acc in accs:
            batch.append((acc, src, key, doi))
        if len(batch) >= _db.BATCH_ROWS:
            rw.executemany(out_sql, batch)
            rw.commit()
            n_out += len(batch)
            batch = []
            _log("cit_out 已写入 %d 行" % n_out)
    if batch:
        rw.executemany(out_sql, batch)
        rw.commit()
        n_out += len(batch)
    per_src = dict(rw.execute(
        "SELECT source, COUNT(*) FROM paper_refs_out GROUP BY source"))
    _log("出边完成：插入 %d 行，库内现量 %s" % (n_out, per_src), t0)
    return n_out, per_src


def _migrate_edges_in(old, rw, pid2accs, t0):
    """迁移 cit_in（入边）。返回 (插入行数, 库内分源现量)。"""
    in_sql = ("INSERT OR IGNORE INTO paper_cited_in "
              "(accession_no, source, citing_key, citing_doi, citing_year) "
              "VALUES (?,?,?,?,?)")
    batch, n_in = [], 0
    for rowid, pid, oa, doi, yr, src in old.execute(
            "SELECT rowid, paper_id, citing_oa, citing_doi, citing_year, source "
            "FROM cit_in"):
        accs = pid2accs.get(pid)
        if not accs:
            continue
        doi = doi.strip().lower() if doi else None
        key = doi or ("oa:" + oa if oa else _mdk("migin", pid, rowid))
        for acc in accs:
            batch.append((acc, src, key, doi, yr))
        if len(batch) >= _db.BATCH_ROWS:
            rw.executemany(in_sql, batch)
            rw.commit()
            n_in += len(batch)
            batch = []
            _log("cit_in 已写入 %d 行" % n_in)
    if batch:
        rw.executemany(in_sql, batch)
        rw.commit()
        n_in += len(batch)
    per_src = dict(rw.execute(
        "SELECT source, COUNT(*) FROM paper_cited_in GROUP BY source"))
    _log("入边完成：插入 %d 行，库内现量 %s" % (n_in, per_src), t0)
    return n_in, per_src
