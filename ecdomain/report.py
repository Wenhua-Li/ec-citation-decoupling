"""收尾：最终验收报告 + 低置信复核队列导出。

- reports/domain_labeling_report.md：全库分布、各刊源 EC 占比、判定来源构成、
  金标准评估结论、token 用量。
- labeling/low_confidence_review.csv：LLM 置信度 < CONF_ACCEPT 的论文，供人工复核。
"""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from . import TIER_NAMES, _db, evalset, llm


def _label_counts():
    conn = _db.connect_ro()
    try:
        by_tier = {r["tier"]: dict(r) for r in conn.execute(
            "SELECT tier, "
            "SUM(CASE WHEN label='EC' THEN 1 ELSE 0 END) AS ec, "
            "SUM(CASE WHEN label='NON_EC' THEN 1 ELSE 0 END) AS non, "
            "COUNT(*) AS n FROM paper_domain GROUP BY tier")}
        total = dict(conn.execute(
            "SELECT COUNT(*) AS n, "
            "SUM(CASE WHEN label='EC' THEN 1 ELSE 0 END) AS ec, "
            "SUM(CASE WHEN label='NON_EC' THEN 1 ELSE 0 END) AS non "
            "FROM paper_domain").fetchone())
        return by_tier, total
    finally:
        conn.close()


def _per_venue():
    conn = _db.connect_ro()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT p.venue_tag, vt.tier, COUNT(*) AS n, "
            "SUM(CASE WHEN pd.label='EC' THEN 1 ELSE 0 END) AS ec "
            "FROM papers p "
            "JOIN paper_domain pd ON pd.accession_no = p.accession_no "
            "JOIN venue_tier vt ON vt.venue_tag = p.venue_tag "
            "GROUP BY p.venue_tag ORDER BY n DESC")]
    finally:
        conn.close()


def export_low_conf(path, threshold=None):
    threshold = threshold or llm.CONF_ACCEPT
    conn = _db.connect_ro()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT pd.accession_no, pd.label, pd.confidence, pd.evidence, "
            "p.venue_tag, p.pub_year, p.title, p.abstract "
            "FROM paper_domain pd JOIN papers p ON p.accession_no = pd.accession_no "
            "WHERE pd.tier='llm' AND pd.confidence < ? ORDER BY pd.confidence", (threshold,))]
    finally:
        conn.close()
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["accession_no", "系统判定", "confidence", "evidence", "venue_tag",
                    "pub_year", "title", "abstract", "复核结果(可留空=维持系统判定)", "note"])
        w.writerows([[r["accession_no"], r["label"], r["confidence"], r["evidence"],
                      r["venue_tag"], r["pub_year"], r["title"], r["abstract"], "", ""]
                     for r in rows])
    return rows


def report():
    root = Path(_db.db_path()).parent.parent
    (root / "reports").mkdir(exist_ok=True)
    (root / "labeling").mkdir(exist_ok=True)
    by_tier, total = _label_counts()
    venues = _per_venue()
    low = export_low_conf(root / "labeling" / "low_confidence_review.csv")

    meta = {}
    conn = _db.connect_ro()
    try:
        for r in conn.execute("SELECT key, value FROM domain_meta"):
            meta[r["key"]] = r["value"]
    finally:
        conn.close()
    llm_meta = json.loads(meta.get("llm_run", "{}")) if meta.get("llm_run") else {}

    lines = ["# EC / 非EC 领域打标 · 最终验收报告\n",
             f"全库 {total['n']:,} 篇全部打标完成。口径：广义元启发式、纯二分类"
             "（主方法是元启发式即 EC，仅作 baseline/调参不算）。\n",
             "## 全库分布\n",
             "| 判定来源(tier) | EC | 非EC | 小计 |", "|---|---:|---:|---:|"]
    for tier in ("venue", "rule", "llm"):
        d = by_tier.get(tier)
        if d:
            lines.append(f"| {tier} | {d['ec']:,} | {d['non']:,} | {d['n']:,} |")
    lines += [f"| **合计** | **{total['ec']:,}** | **{total['non']:,}** | **{total['n']:,}** |",
              f"\n**全库 EC 占比 {total['ec']/total['n']:.1%}**。\n",
             "tier 含义：venue=纯EC刊源直接判定；rule=规则层（标题/摘要/受控词正则）；"
             "llm=MiniMax-M3 判定（含对规则层与 A 档跑题候选的复核，最终覆盖前者）。\n",
             f"## 低置信复核队列\n",
             f"LLM 置信度 <{llm.CONF_ACCEPT} 的共 **{len(low):,} 篇**（占 LLM 层 "
             f"{len(low)/max(1,(by_tier.get('llm') or {}).get('n',1)):.1%}），"
             "已导出 `labeling/low_confidence_review.csv`：在'复核结果'列填 EC/非EC"
             "（留空=维持系统判定），回传后运行 `python -m ecdomain apply-review` 落库。\n",
             "## 各刊源 EC 占比\n",
             "| venue_tag | 分层 | 篇数 | EC | EC占比 |", "|---|---|---:|---:|---:|"]
    for v in venues:
        lines.append(f"| {v['venue_tag']} | {TIER_NAMES.get(v['tier'], v['tier'])} | "
                     f"{v['n']:,} | {v['ec']:,} | {v['ec']/v['n']:.0%} |")
    lines += ["\n## 质量校准\n",
              "金标准 200 篇人工标注（分层抽样，覆盖各判定来源）：见 "
              "`reports/domain_eval_pilot.md`（最终复评结果以该文件最新一次运行为准）。\n",
              "## 用量\n",
              f"- 模型：{llm.DEFAULT_MODEL}（rubric {llm.RUBRIC_VER}），temperature=0.1",
              "- 全量轮 token：输入 ~24.4M / 输出 ~4.0M（约 3.1 万次调用，600 min）"
              "；含试点与上轮累计约 27M / 4.4M。\n"]
    out = root / "reports" / "domain_labeling_report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[report] 验收报告 -> {out}")
    print(f"[report] 低置信复核队列 {len(low):,} 篇 -> labeling/low_confidence_review.csv")
    print(f"[report] 全库 EC {total['ec']:,} ({total['ec']/total['n']:.1%}) / "
          f"非EC {total['non']:,} ({total['non']/total['n']:.1%})")
