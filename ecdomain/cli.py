"""ecdomain CLI：python -m ecdomain <stage> [options]"""
import argparse
import json
import sys
from pathlib import Path

# 保证从任意 CWD 运行时都能 import ecdb / ecdomain
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from . import _db, evalset, gold, llm, report, rules, venues  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="ecdomain",
        description="EC / 非EC 领域打标子系统（venue分层 + 规则层 + LLM + 金标准校准）")
    sub = ap.add_subparsers(dest="stage", required=True)

    sub.add_parser("venues", help="venue 分层入表 + 生成核定表(labeling/venue_tier_review.csv)")
    sub.add_parser("rules", help="规则层：B/C 论文双向预判，auto 桶写入 paper_domain")
    p = sub.add_parser("gold", help="分层抽样生成金标准标注 CSV")
    p.add_argument("--total", type=int, default=200)
    sub.add_parser("status", help="当前打标进度与各层计数")
    sub.add_parser("llm-pilot", help="对金标准 200 篇跑 LLM 试点（不入库，写缓存）")
    p = sub.add_parser("llm", help="对规则层 todo 队列跑 LLM（全量或 --limit 抽样）")
    p.add_argument("--limit", type=int, default=None, help="只跑随机抽样的 N 篇")
    p.add_argument("--yes", action="store_true", help="确认写库（>5000 篇时需要）")
    sub.add_parser("eval", help="金标准标注回传后计算各层准确率 -> reports/domain_eval_pilot.md")
    sub.add_parser("report", help="最终验收报告 + 低置信复核队列导出")
    sub.add_parser("apply-review", help="低置信复核 CSV 回传后落库（tier=human）")

    args = ap.parse_args(argv)
    stage = args.stage

    if stage == "venues":
        n_new, have, rows = venues.ensure_venue_tiers()
        root = _ROOT
        (root / "labeling").mkdir(exist_ok=True)
        (root / "reports").mkdir(exist_ok=True)
        venues.write_review_csv(root / "labeling" / "venue_tier_review.csv")
        venues.write_review_md(root / "reports" / "venue_tier_review.md")
        print("[venues] 分层入表：新增 %d 行，共 %d 个 venue_tag" % (n_new, have))
        n_add, n_del = venues.write_venue_labels()
        if n_add or n_del:
            print(f"[venues] A档 venue 标签落库：新增 {n_add:,}，清理 {n_del:,}")
        counts = venues.tier_counts()
        total = sum(counts.values())
        for t, n in sorted(counts.items()):
            print(f"    {t:<14} {n:>7,} ({n/total:.1%})")
        print("[venues] 核定表 -> labeling/venue_tier_review.csv（Excel 打开，"
              "在最后一列填 A/B/C 裁定后发回）")
        print("[venues] 说明 -> reports/venue_tier_review.md")
    elif stage == "rules":
        rules.run_rules()
    elif stage == "gold":
        gold.run_gold(total=args.total)
    elif stage == "llm-pilot":
        llm.pilot()
    elif stage == "llm":
        if len(llm.todo_accessions()) > 5000 and not args.yes:
            raise SystemExit("本次为全量判定（约 3.6 万篇）并写库；确认请加 --yes")
        llm.full_run(limit=args.limit)
    elif stage == "eval":
        evalset.eval_pilot()
    elif stage == "report":
        report.report()
    elif stage == "apply-review":
        evalset.apply_review()
    elif stage == "status":
        conn = _db.connect_ro()
        try:
            rows = conn.execute(
                "SELECT tier, label, COUNT(*) AS n FROM paper_domain "
                "GROUP BY tier, label ORDER BY tier, label").fetchall()
            meta_keys = conn.execute("SELECT key, value, updated_at FROM domain_meta").fetchall()
            n_papers = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
            n_labeled = conn.execute("SELECT COUNT(*) FROM paper_domain").fetchone()[0]
        finally:
            conn.close()
        print(f"[status] 全库 {n_papers:,} 篇，已打标 {n_labeled:,} "
              f"({n_labeled/n_papers:.1%})")
        for r in rows:
            print(f"    tier={r['tier']:<6} label={r['label']:<7} {r['n']:>8,}")
        for r in meta_keys:
            print(f"    meta[{r['key']}] @ {r['updated_at']}: {r['value'][:160]}")
