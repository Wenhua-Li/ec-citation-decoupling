"""edges —— 重建库内引文网络 paper_cit_edges（两端都解析回 accession_no）。

出边表（A 引了 B）与入边表（B 被 C 引）两个方向汇合，按 (施引, 被引, 源)
DISTINCT 后合并计数，跨源不重复计边。整表重建，失败回滚保留旧数据。
"""
from . import _db


def rebuild_edges():
    rw = _db.connect_rw()
    _db.ensure_schema(rw)
    rw.execute("PRAGMA foreign_keys=OFF")
    print("[edges] 重建 paper_cit_edges（单事务，失败自动回滚）...")
    try:
        rw.execute("BEGIN IMMEDIATE")
        rw.execute("DELETE FROM paper_cit_edges")
        rw.execute("""
        INSERT INTO paper_cit_edges (citing_acc, cited_acc, n_sources)
        SELECT citing_acc, cited_acc, COUNT(*) FROM (
          SELECT DISTINCT citing_acc, cited_acc, source FROM (
            SELECT r.accession_no AS citing_acc, p.accession_no AS cited_acc, r.source
            FROM paper_refs_out r JOIN papers p ON p.doi = r.cited_doi
            UNION ALL
            SELECT p.accession_no AS citing_acc, c.accession_no AS cited_acc, c.source
            FROM paper_cited_in c JOIN papers p ON p.doi = c.citing_doi
          )
        ) GROUP BY citing_acc, cited_acc
        """)
        rw.commit()
    except Exception:
        rw.rollback()
        raise
    n = rw.execute("SELECT COUNT(*) FROM paper_cit_edges").fetchone()[0]
    multi = rw.execute(
        "SELECT COUNT(*) FROM paper_cit_edges WHERE n_sources > 1").fetchone()[0]
    rw.close()
    print("[edges] 库内边 %d（多源共同支持 %d）" % (n, multi))
    return {"edges": n, "multi_source": multi}
