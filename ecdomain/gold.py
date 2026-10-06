"""金标准抽样：分层抽 200 篇生成标注 CSV（用户逐条填 label）。

分层：A 档固定 20 篇（验证"纯EC刊源"假设）；B/C 档按
{EC(auto), 非EC(auto), todo(LLM层)} × {B, C} 六层分配，
保底每层 15 篇、其余按层内规模比例。抽样种子固定，可复现。
"""
import csv
import random
from collections import defaultdict
from pathlib import Path

from . import LABEL_EC, LABEL_NON, TIER_A
from . import _db

SEED = 20260927
STRATA_ORDER = ["A_venue", "B_ec", "B_non", "B_todo", "C_ec", "C_non", "C_todo"]
STRATA_LABEL = {
    "A_venue": "A纯EC刊源(验证假设)", "B_ec": "B×规则EC", "B_non": "B×规则非EC",
    "B_todo": "B×待判(LLM层)", "C_ec": "C×规则EC", "C_non": "C×规则非EC",
    "C_todo": "C×待判(LLM层)",
}


def _pools():
    """返回 {stratum: [(accession_no, venue_tag, pub_year), ...]}（不含标题摘要，按需再取）。"""
    conn = _db.connect_ro()
    pools = defaultdict(list)
    try:
        for r in conn.execute(
                "SELECT p.accession_no, p.venue_tag, p.pub_year, vt.tier, pd.label "
                "FROM papers p "
                "JOIN venue_tier vt ON vt.venue_tag = p.venue_tag "
                "LEFT JOIN paper_domain pd ON pd.accession_no = p.accession_no "
                "AND pd.tier = 'rule'"):
            tier, label = r["tier"], r["label"]
            if tier == TIER_A:
                pools["A_venue"].append((r["accession_no"], r["venue_tag"], r["pub_year"]))
            else:
                s = ("B" if tier.startswith("B") else "C")
                key = s + ("_ec" if label == LABEL_EC else "_non" if label == LABEL_NON else "_todo")
                pools[key].append((r["accession_no"], r["venue_tag"], r["pub_year"]))
    finally:
        conn.close()
    return pools


def allocate(pools, total=200, a_n=20, min_per=15):
    n_bc = sum(len(v) for k, v in pools.items() if k != "A_venue")
    budget = total - a_n
    sizes = {k: len(v) for k, v in pools.items() if k != "A_venue"}
    alloc = {}
    for k, n in sizes.items():
        alloc[k] = max(min_per, int(budget * n / n_bc))
    # 修正到 budget：差额按规模从大到小逐步增减
    diff = budget - sum(alloc.values())
    order = sorted(sizes, key=lambda k: -sizes[k])
    i = 0
    while diff != 0:
        k = order[i % len(order)]
        if diff > 0:
            alloc[k] += 1
            diff -= 1
        elif alloc[k] > min_per:
            alloc[k] -= 1
            diff += 1
        i += 1
    alloc["A_venue"] = a_n
    return alloc


def _fetch_rows(accs):
    conn = _db.connect_ro()
    try:
        out = {}
        for j in range(0, len(accs), 500):
            ph = ",".join("?" * len(accs[j:j + 500]))
            for r in conn.execute(
                    f"SELECT accession_no, title, abstract FROM papers "
                    f"WHERE accession_no IN ({ph})", accs[j:j + 500]):
                out[r["accession_no"]] = dict(r)
        kw = defaultdict(list)
        for j in range(0, len(accs), 500):
            ph = ",".join("?" * len(accs[j:j + 500]))
            for r in conn.execute(
                    f"SELECT accession_no, term FROM paper_terms "
                    f"WHERE accession_no IN ({ph}) ORDER BY kind, term", accs[j:j + 500]):
                kw[r["accession_no"]].append(r["term"])
        return out, kw
    finally:
        conn.close()


def run_gold(total=200):
    root = Path(_db.db_path()).parent.parent
    pools = _pools()
    alloc = allocate(pools, total=total)
    rng = random.Random(SEED)
    picked = []
    for s in STRATA_ORDER:
        pool = pools.get(s, [])
        rng.shuffle(pool)
        for a, tag, yr in pool[:alloc.get(s, 0)]:
            picked.append((s, a, tag, yr))

    accs = [a for _, a, _, _ in picked]
    rows, kw = _fetch_rows(accs)
    out_csv = root / "labeling" / "gold_set_200.csv"
    out_csv.parent.mkdir(exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["gold_id", "accession_no", "stratum", "venue_tag", "pub_year",
                    "title", "abstract", "keywords", "label", "note"])
        for i, (s, a, tag, yr) in enumerate(picked, 1):
            r = rows.get(a, {})
            w.writerow([f"G{i:03d}", a, STRATA_LABEL[s], tag, yr,
                        r.get("title", ""), r.get("abstract", ""),
                        "; ".join(kw.get(a, [])), "", ""])

    _write_readme(root, alloc, total)
    print(f"[gold] 金标准 {len(picked)} 篇 -> {out_csv}")
    for s in STRATA_ORDER:
        print(f"    {STRATA_LABEL[s]:<18} 抽 {alloc.get(s,0):>3} / 层内 {len(pools.get(s,[])):>7,}")
    print("[gold] 标注说明 -> labeling/gold_set_README.md")


def _write_readme(root, alloc, total):
    p = root / "labeling" / "gold_set_README.md"
    p.write_text(f"""# 金标准标注说明（约 {total} 篇，预计 1~2 小时）

文件：`gold_set_200.csv`（UTF-8-BOM，Excel 直接打开）。每行一篇论文。

## 你要做的

只在最后两列填写：
- **label**：`EC` 或 `非EC`（其他列勿动）
- **note**（可选）：拿不准时写一句原因，例如"主方法是深度学习，GA只是对比"。

## 判定标准（广义元启发式口径）

判 **EC**：论文的**主方法**是元启发式——遗传算法/差分进化/进化策略/遗传编程/EDA/
共演化/神经演化等演化算法，PSO/蚁群/人工蜂群等群智能，灰狼/鲸鱼/萤火虫等新型自然
启发算法，模拟退火/禁忌搜索/VNS/GRASP 等单点元启发式，以及以上任何混合
（memetic/hybrid）。"用 GA 解调度问题"这类应用也算 EC。

判 **非EC**：
- 纯精确方法（MILP、分支定界、动态规划、凸优化）；
- 纯机器学习/深度学习/统计方法；纯模糊逻辑/控制；
- **主方法是 ML/精确算法，元启发式只出现为对比 baseline 或调参工具**；
- 演化生物学、演化博弈论、系统发育学（名字像但无关）。

拿不准就按"主方法"判断：论文提出/使用的核心求解方法是不是上述元启发式之一。

## 分层说明

抽样覆盖了各判定来源，所以不同 stratum 会遇到明显不同风格的论文（规则EC层大多是
明显的 EC 论文，待判层更模糊）——这是故意的，请独立判断，不要猜"系统为什么选了这篇"。

完成后把文件发回（或放到原位置告诉我），我用来校准各层准确率。
""", encoding="utf-8")
