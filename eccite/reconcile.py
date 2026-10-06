"""reconcile —— 主库与引文表对账（清洗会话跑完/跑批后执行）。

1. 为新增论文补 meta 行（pending，进入抓取队列）。
2. 清理孤儿行（papers 中已不存在的 accession_no 的引文数据；
   FK 关闭写入时可能残留，去重删行也不依赖 CASCADE）。
3. 提示需要补跑的阶段（load / fetch）。
"""
from . import _db


def reconcile():
    rw = _db.connect_rw()
    _db.ensure_schema(rw)
    out = {}

    # 1) 新增论文补 meta
    out["meta_seeded"] = _db.seed_meta(rw)

    # 2) 孤儿清理（分表统计）
    out["orphans"] = {}
    for table in ("paper_refs_out", "paper_cited_in", "paper_cit_meta",
                  "paper_cit_edges"):
        cur = rw.execute(
            "DELETE FROM %s WHERE accession_no NOT IN "
            "(SELECT accession_no FROM papers)" % table
            if table != "paper_cit_edges" else
            "DELETE FROM paper_cit_edges WHERE citing_acc NOT IN "
            "(SELECT accession_no FROM papers) OR cited_acc NOT IN "
            "(SELECT accession_no FROM papers)")
        rw.commit()
        out["orphans"][table] = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0

    # 3) 待办统计
    row = rw.execute(
        "SELECT SUM(CASE WHEN refs_status='pending' THEN 1 ELSE 0 END), "
        "       SUM(CASE WHEN cites_status='pending' THEN 1 ELSE 0 END), "
        "       COUNT(*) FROM paper_cit_meta").fetchone()
    out["meta_total"] = row[2]
    out["refs_pending"] = row[0] or 0
    out["cites_pending"] = row[1] or 0
    n_papers = rw.execute(
        "SELECT COUNT(*) FROM papers WHERE doi IS NOT NULL AND doi != ''").fetchone()[0]
    out["papers_with_doi"] = n_papers
    rw.close()
    print("[reconcile] 新补 meta=%d，孤儿清理=%s，待抓取 refs=%d cites=%d" % (
        out["meta_seeded"], out["orphans"], out["refs_pending"], out["cites_pending"]))
    if out["refs_pending"] or out["cites_pending"]:
        print("[reconcile] 提示：先重跑 fetch-*（断点续传只抓缺的），再 load。")
    return out


def sync_doi():
    """把主库 papers.doi 同步进 paper_cit_meta（enrich fix-doi / 回写后执行）。

    - meta 无 DOI 而 papers 有（title_match 回写后）：写入并复位状态待抓；
    - meta.doi_source='ei' 且与 papers.doi 不一致（如坏 DOI 修正）：以主库为准
      覆盖并复位 refs/cites 为 pending、各源 done 清零，重跑 fetch-* 即补抓。
    title_match 来源的 meta 行不在此覆盖范围（其 DOI 本就来自 meta）。
    """
    rw = _db.connect_rw()
    cur = rw.execute(
        "UPDATE paper_cit_meta SET "
        "doi=(SELECT p.doi FROM papers p WHERE p.accession_no=paper_cit_meta.accession_no), "
        "doi_source='ei', "
        "refs_status=CASE WHEN refs_status IN ('no_doi','pending') THEN 'pending' "
        "ELSE refs_status END, "
        "cites_status=CASE WHEN cites_status IN ('no_doi','pending') THEN 'pending' "
        "ELSE cites_status END "
        "WHERE (doi IS NULL OR doi='') AND EXISTS "
        "(SELECT 1 FROM papers p WHERE p.accession_no=paper_cit_meta.accession_no "
        " AND p.doi IS NOT NULL AND p.doi != '')")
    n1 = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    cur2 = rw.execute(
        "UPDATE paper_cit_meta SET "
        "doi=(SELECT p.doi FROM papers p WHERE p.accession_no=paper_cit_meta.accession_no), "
        "refs_status='pending', cites_status='pending', "
        "cr_done=0, s2_done=0, coci_done=0 "
        "WHERE doi_source='ei' AND doi IS NOT NULL AND EXISTS "
        "(SELECT 1 FROM papers p WHERE p.accession_no=paper_cit_meta.accession_no "
        " AND p.doi IS NOT NULL AND p.doi != paper_cit_meta.doi)")
    n2 = cur2.rowcount if cur2.rowcount and cur2.rowcount > 0 else 0
    rw.commit()
    rw.close()
    print("[sync-doi] meta 补 DOI %d 行，以主库覆盖不一致 %d 行" % (n1, n2))
    return {"meta_added": n1, "meta_overridden": n2}
