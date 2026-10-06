"""评估：金标准标注回传后，计算各层准确率并出报告。

- 规则层（A_venue / *_ec / *_non）：系统标签（venue 或 rule）vs 金标准。
- LLM 层（*_todo）：cache_domain/<model>.jsonl 里的试点判定 vs 金标准。
- 输出 reports/domain_eval_pilot.md。
"""
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from . import LABEL_EC, LABEL_NON
from . import _db

_POS = {"ec", "1", "y", "yes", "是", "e"}
_NEG = {"非ec", "non", "non_ec", "nonec", "n", "0", "no", "否", "nec"}


def _norm_label(raw):
    v = (raw or "").strip().lower()
    if v in _POS:
        return LABEL_EC
    if v in _NEG:
        return LABEL_NON
    return None


def load_gold():
    root = Path(_db.db_path()).parent.parent
    p = root / "labeling" / "gold_set_200.csv"
    if not p.exists():
        raise SystemExit("金标准 CSV 不存在")
    out = []
    with open(p, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            lab = _norm_label(r.get("label"))
            out.append({"gold_id": r["gold_id"], "accession_no": r["accession_no"],
                        "stratum": r["stratum"], "gold": lab,
                        "note": r.get("note", "")})
    done = sum(1 for g in out if g["gold"])
    if done < len(out):
        print(f"[eval] 注意：还有 {len(out)-done} 篇未标注（label 列为空），先按已标部分算")
    return [g for g in out if g["gold"]]


def _system_labels(accs):
    conn = _db.connect_ro()
    try:
        return {r["accession_no"]: (r["label"], r["tier"], r["confidence"])
                for r in conn.execute(
                    "SELECT accession_no, label, tier, confidence FROM paper_domain "
                    f"WHERE accession_no IN ({','.join('?'*len(accs))})", accs)}
    finally:
        conn.close()


def _llm_labels(accs, model="MiniMax-M3"):
    root = Path(_db.db_path()).parent.parent
    p = root / "cache_domain" / f"{model}.jsonl"
    cache = {}
    if p.exists():
        want = set(accs)
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                o = json.loads(line)
                if o["accession_no"] in want:
                    cache[o["accession_no"]] = o
            except (json.JSONDecodeError, KeyError):
                continue
    return cache


def eval_pilot(model="MiniMax-M3"):
    gold = load_gold()
    if not gold:
        raise SystemExit("金标准还没有任何标注")
    accs = [g["accession_no"] for g in gold]
    syslab = _system_labels(accs)
    llmlab = _llm_labels(accs, model)

    by_stratum = defaultdict(list)
    for g in gold:
        by_stratum[g["stratum"]].append(g)

    table_rows, bad_lines = [], []
    overall = Counter()
    for s in ["A纯EC刊源(验证假设)", "B×规则EC", "B×规则非EC", "B×待判(LLM层)",
              "C×规则EC", "C×规则非EC", "C×待判(LLM层)"]:
        rows = by_stratum.get(s, [])
        if not rows:
            continue
        n = len(rows)
        agree = disagrees = 0
        for g in rows:
            a = g["accession_no"]
            if "待判" in s:
                rec = llmlab.get(a)
                sys = (rec["label"], "llm", rec["confidence"]) if rec else (None, None, None)
            else:
                sys = syslab.get(a, (None, None, None))
            sysl = sys[0]
            if sysl is None:
                disagrees += 1
                continue
            if sysl == g["gold"]:
                agree += 1
                overall["ok"] += 1
            else:
                disagrees += 1
                overall["bad"] += 1
                bad_lines.append(f"- **不一致** {g['gold_id']} [{s}] gold={g['gold']} "
                                 f"sys={sysl}(tier={sys[1]},conf={sys[2]}) "
                                 f"note={g['note'][:80]}")
        acc = agree / n if n else 0
        table_rows.append(f"| {s} | {n} | {agree} | {disagrees} | {acc:.0%} |")
    tot = overall["ok"] + overall["bad"]
    lines = [f"# 金标准评估（n={len(gold)}）\n",
             "| 层 | n | 一致 | 不一致 | 准确率 |",
             "|---|---:|---:|---:|---:|",
             f"| **整体** | {tot} | {overall['ok']} | {overall['bad']} | "
             f"{overall['ok']/tot:.0%} |",
             *table_rows, "", "## 不一致明细\n", *bad_lines]

    lines += ["\n## 建议动作\n"]
    rate = overall["ok"] / tot if tot else 0
    if rate >= 0.95:
        lines.append("- 整体达标（≥95%）：可按当前口径放量全量 LLM。")
    else:
        lines.append("- 整体未达 95%：先看上方不一致明细，调 rubric/阈值后复跑试点。")
    lines.append("- 不一致集中在某层时：规则层问题调 PATTERNS/阈值（改 rules.py 后 "
                 "`python -m ecdomain rules` 幂等重算）；LLM 层问题调 RUBRIC 后清缓存重跑试点。")
    root = Path(_db.db_path()).parent.parent
    out = root / "reports" / "domain_eval_pilot.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[eval] 报告 -> {out}")
    print(f"[eval] 整体一致率 {overall['ok']}/{tot} = {rate:.0%}")


def apply_review():
    """低置信复核 CSV 回传后落库：复核结果列非空的行改为 tier='human' 终判。"""
    import csv as _csv
    root = Path(_db.db_path()).parent.parent
    p = root / "labeling" / "low_confidence_review.csv"
    if not p.exists():
        raise SystemExit("复核 CSV 不存在：先 python -m ecdomain report")
    updates = []
    with open(p, encoding="utf-8-sig") as f:
        for r in _csv.DictReader(f):
            lab = _norm_label(r.get("复核结果(可留空=维持系统判定)"))
            if lab:
                updates.append((r["accession_no"], lab, (r.get("note") or "")[:200]))
    if not updates:
        print("[apply-review] 没有填写复核结果的行，库未改动")
        return
    conn = _db.connect_rw()
    try:
        _db.ensure_schema(conn)
        now = _db.utcnow()
        for j in range(0, len(updates), 2000):
            conn.executemany(
                "UPDATE paper_domain SET label=?, tier='human', confidence=1.0, "
                "evidence=COALESCE(NULLIF(?,''), evidence), judged_at=? "
                "WHERE accession_no=?", [(lab, note, now, a) for a, lab, note in updates[j:j+2000]])
        _db.set_meta(conn, "review_applied", json.dumps(
            {"n": len(updates), "ts": now}))
        conn.commit()
    finally:
        conn.close()
    print(f"[apply-review] 人工复核落库 {len(updates):,} 篇（tier=human）")
