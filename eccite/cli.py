"""eccite CLI：python -m eccite <stage> [options]"""
import argparse
import sys
from pathlib import Path

# 保证从任意 CWD 运行时都能 import ecdb / eccite
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from . import _db, edges, fetchers, loader, migrate, reconcile, report, validate  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="eccite",
        description="EC_MAP_2026 引文数据子系统（迁移 + 三源抓取 + 库内网络）")
    sub = ap.add_subparsers(dest="stage", required=True)

    sub.add_parser("init", help="建引文表 + 为全部论文补 meta 行")
    p = sub.add_parser("migrate", help="从 EC_History 旧库迁移引文数据")
    p.add_argument("--old-db", default=None, help="旧库路径（默认 ../EC_History/ec_corpus.db）")
    p.add_argument("--meta-only", action="store_true",
                   help="只补 paper_cit_meta（边已迁过时用）")
    for name, help_ in (("fetch-s2", "Semantic Scholar batch（入边+计数+s2_id）"),
                        ("fetch-cr", "Crossref（出边+被引计数）"),
                        ("fetch-coci", "OpenCitations COCI（入边）"),
                        ("match-doi", "无 DOI 论文标题匹配找回 DOI（Crossref）"),
                        ("match-doi-s2", "无 DOI 论文标题匹配找回 DOI（OpenAlex+S2 第二来源）"),
                        ("match-doi-relax", "Crossref 复查（rows=10 + query.title 变体）")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--limit", type=int, default=None, help="只处理前 N 篇（测试用）")
    sub.add_parser("load", help="JSONL 缓存 -> 引文表（幂等）")
    sub.add_parser("edges", help="重建库内引文网络 paper_cit_edges")
    sub.add_parser("reconcile", help="与主库对账：补新论文 meta、清孤儿行")
    sub.add_parser("sync-doi", help="主库 DOI 变更同步进 paper_cit_meta 并复位状态")
    p = sub.add_parser("validate", help="验收检查")
    p.add_argument("--old-db", default=None)
    sub.add_parser("report", help="覆盖率报告 -> reports/citations_report.md")
    sub.add_parser("status", help="进度与缓存状态")

    args = ap.parse_args(argv)
    stage = args.stage

    if stage == "init":
        rw = _db.connect_rw()
        _db.ensure_schema(rw)
        n = _db.seed_meta(rw)
        rw.close()
        print("[init] schema 就绪，新补 meta 行 %d" % n)
    elif stage == "migrate":
        _db.warn_if_build_active()
        out = migrate.migrate(old_db=args.old_db, meta_only=args.meta_only)
        print("[migrate] %s" % out)
    elif stage == "fetch-s2":
        fetchers.fetch_s2(limit=args.limit)
    elif stage == "fetch-cr":
        fetchers.fetch_cr(limit=args.limit)
    elif stage == "fetch-coci":
        fetchers.fetch_coci(limit=args.limit)
    elif stage == "match-doi":
        fetchers.match_doi(limit=args.limit)
    elif stage == "match-doi-s2":
        fetchers.match_s2(limit=args.limit)
    elif stage == "match-doi-relax":
        fetchers.match_doi_relax(limit=args.limit)
    elif stage == "load":
        _db.warn_if_build_active()
        loader.load()
    elif stage == "edges":
        _db.warn_if_build_active()
        edges.rebuild_edges()
    elif stage == "reconcile":
        reconcile.reconcile()
    elif stage == "sync-doi":
        reconcile.sync_doi()
    elif stage == "validate":
        validate.validate(old_db=args.old_db)
    elif stage == "report":
        report.report()
    elif stage == "status":
        report.status()
    return 0
