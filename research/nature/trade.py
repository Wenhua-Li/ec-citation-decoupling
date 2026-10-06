# -*- coding: utf-8 -*-
"""思想贸易分析 v2：EC 与非 EC 论文之间的引用流向随时间的变化。

口径（修正版）：
  - 库内边 = paper_refs_out 中 cited_doi 回连库内论文（DISTINCT 去重，跨源）
  - 分母 = 当年有参考文献列表的 EC 论文数 / 非 EC 论文数（各自的池）
  - 指标：import_rate = EC→非EC 每篇 EC 论文；export_rate = 非EC→EC 每篇非 EC 论文；
          intra_ec = EC→EC 每篇 EC 论文
  - 经典垄断度：各施引年，全部→EC 引用中被"全期被引 Top-50 EC 论文"吸走的份额；
    全部→非EC 引用中被 Top-50 非 EC 论文吸走的份额
  - A 口径（仅 A_pure_ec 核心期刊）并行输出
输出：research/nature/out/trade.json
"""
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ecdb

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

tier_of = {}
for r in ecdb.raw_sql("SELECT venue_tag, tier FROM venue_tier", max_rows=200)["rows"]:
    tier_of[r["venue_tag"]] = r["tier"]

label_of, year_of = {}, {}
for r in ecdb.raw_sql(
    "SELECT d.accession_no acc, d.label, p.pub_year y FROM paper_domain d JOIN papers p USING(accession_no)",
    max_rows=200000,
)["rows"]:
    label_of[r["acc"]] = r["label"]
    year_of[r["acc"]] = r["y"]
print(f"labels loaded: {len(label_of)}")

# 各群体可引用池：当年有参考文献列表的论文数
pool = defaultdict(lambda: {"EC": 0, "NON_EC": 0})
rows = ecdb.raw_sql(
    """
    SELECT p.pub_year y, d.label l, COUNT(DISTINCT r.accession_no) n
    FROM papers p
    JOIN paper_refs_out r USING(accession_no)
    JOIN paper_domain d USING(accession_no)
    GROUP BY p.pub_year, d.label
    """,
    max_rows=100,
)["rows"]
for r in rows:
    pool[r["y"]][r["l"]] = r["n"]

pool_a = defaultdict(lambda: {"EC": 0, "NON_EC": 0})
rows = ecdb.raw_sql(
    """
    SELECT p.pub_year y, d.label l, COUNT(DISTINCT r.accession_no) n
    FROM papers p
    JOIN paper_refs_out r USING(accession_no)
    JOIN paper_domain d USING(accession_no)
    WHERE p.venue_tag IN (SELECT venue_tag FROM venue_tier WHERE tier='A_pure_ec')
    GROUP BY p.pub_year, d.label
    """,
    max_rows=100,
)["rows"]
for r in rows:
    pool_a[r["y"]][r["l"]] = r["n"]

print("building in-db edges from refs_out (SQL join) ...", flush=True)
rows = ecdb.raw_sql(
    """
    SELECT DISTINCT p.pub_year cy, p.venue_tag vt, p.source src, d.label l_src, pc.accession_no cited_acc
    FROM paper_refs_out r
    JOIN papers p  ON p.accession_no  = r.accession_no
    JOIN papers pc ON pc.doi = r.cited_doi
    JOIN paper_domain d  ON d.accession_no  = p.accession_no
    JOIN paper_domain dc ON dc.accession_no = pc.accession_no
    """,
    max_rows=3000000,
)["rows"]
print(f"in-db edges: {len(rows)}", flush=True)

flow = defaultdict(int)  # (cy, l_src, l_dst, is_a) -> n
for r in rows:
    is_a = 1 if tier_of.get(r["vt"]) == "A_pure_ec" else 0
    flow[(r["cy"], r["l_src"], label_of[r["cited_acc"]], is_a)] += 1

# 全期被引 Top-50（按库内入度，用本边集的全期合计）
indeg = defaultdict(int)
for (cy, l_src, l_dst, is_a), n in flow.items():
    pass
# 用无向累计：直接按 (cited_acc) 重新统计
cited_cnt = defaultdict(int)
for r in rows:
    cited_cnt[r["cited_acc"]] += 1
top50 = {"EC": [], "NON_EC": []}
for acc, c in sorted(cited_cnt.items(), key=lambda kv: -kv[1]):
    lab = label_of.get(acc)
    if lab in top50 and len(top50[lab]) < 50:
        top50[lab].append(acc)
top50set = {lab: set(v) for lab, v in top50.items()}
for lab in ("EC", "NON_EC"):
    ys = sorted(year_of[a] for a in top50[lab])
    print(f"Top-50 {lab} classics: year range {ys[0]}-{ys[-1]}, median {ys[len(ys)//2]}")

classic_hit = defaultdict(int)  # (cy, l_dst(被引群体), is_a) -> 来自 Top50 的引用数
for r in rows:
    lab = label_of.get(r["cited_acc"])
    is_a = 1 if tier_of.get(r["vt"]) == "A_pure_ec" else 0
    if r["cited_acc"] in top50set[lab]:
        classic_hit[(r["cy"], lab, is_a)] += 1

result = {"flow": [], "classic_monopoly": [], "top50": {k: [{"acc": a, "year": year_of[a]} for a in v] for k, v in top50.items()}}
years = sorted({r["cy"] for r in rows})
for cy in years:
    for is_a, pl in ((0, pool), (1, pool_a)):
        pe, pn = pl.get(cy, {}).get("EC", 0), pl.get(cy, {}).get("NON_EC", 0)
        if pe + pn < 50:
            continue
        ee = flow.get((cy, "EC", "EC", is_a), 0)
        en = flow.get((cy, "EC", "NON_EC", is_a), 0)
        ne = flow.get((cy, "NON_EC", "EC", is_a), 0)
        nn = flow.get((cy, "NON_EC", "NON_EC", is_a), 0)
        result["flow"].append(
            {
                "year": cy,
                "a_tier_only": bool(is_a),
                "pool_EC": pe, "pool_NON": pn,
                "EC_to_EC": ee, "EC_to_NON": en, "NON_to_EC": ne, "NON_to_NON": nn,
                "import_per_ec_paper": round(en / pe, 3) if pe else None,
                "export_per_non_paper": round(ne / pn, 3) if pn else None,
                "intra_ec_per_ec_paper": round(ee / pe, 3) if pe else None,
                "intra_non_per_non_paper": round(nn / pn, 3) if pn else None,
                # 三归一口径（W0.6，评审 F7）：比值失衡对归一方式敏感，三者并列、主结论取最保守
                "ratio_raw_edges": round(en / ne, 3) if ne else None,
                "ratio_citing_side_pools": round((en / pe) / (ne / pn), 3) if pe and pn and ne else None,
                "ratio_cited_side_pools": round((en / pn) / (ne / pe), 3) if pe and pn and ne else None,
            }
        )
        for lab in ("EC", "NON_EC"):
            tot = ee if lab == "EC" else en  # 目标为 EC 的引用总量
            if lab == "EC":
                tot = ne + ee
            else:
                tot = en + nn
            ch = classic_hit.get((cy, lab, is_a), 0)
            if tot >= 100:
                result["classic_monopoly"].append(
                    {"year": cy, "dst_group": lab, "a_tier_only": bool(is_a),
                     "share_top50": round(ch / tot, 4), "n": tot}
                )

# W0.6/F6：固定稳定混合期刊集内的流向（消除非 EC 池构成漂移；判据与 checks.py C2 一致）
print("\ncomputing fixed-source venue flow ...", flush=True)
src_non_year = defaultdict(lambda: defaultdict(int))
for r in ecdb.raw_sql(
    "SELECT p.source s, p.pub_year y, COUNT(*) n FROM papers p JOIN paper_domain d USING(accession_no) "
    "WHERE d.label='NON_EC' GROUP BY s, y",
    max_rows=20000,
)["rows"]:
    src_non_year[r["s"]][r["y"]] += r["n"]
stable = set()
for s, ys in src_non_year.items():
    n_early = sum(v for y, v in ys.items() if 2005 <= y <= 2010)
    n_late = sum(v for y, v in ys.items() if 2020 <= y <= 2025)
    if n_early >= 300 and n_late >= 300:
        stable.add(s)
print("stable mixed sources:", sorted(stable))

pool_f = defaultdict(lambda: {"EC": 0, "NON_EC": 0})
for r in ecdb.raw_sql(
    """
    SELECT p.source s, p.pub_year y, d.label l, COUNT(DISTINCT r.accession_no) n
    FROM papers p JOIN paper_refs_out r USING(accession_no) JOIN paper_domain d USING(accession_no)
    GROUP BY s, y, l
    """,
    max_rows=20000,
)["rows"]:
    if r["s"] in stable:
        pool_f[r["y"]][r["l"]] += r["n"]

fflow = defaultdict(int)  # (cy, l_src, l_dst) -> n
for r in rows:
    if r["src"] in stable:
        fflow[(r["cy"], r["l_src"], label_of[r["cited_acc"]])] += 1
result["fixed_venue_flow"] = []
for cy in sorted({k[0] for k in fflow}):
    pe, pn = pool_f.get(cy, {}).get("EC", 0), pool_f.get(cy, {}).get("NON_EC", 0)
    if pe + pn < 50:
        continue
    en = fflow.get((cy, "EC", "NON_EC"), 0)
    ne = fflow.get((cy, "NON_EC", "EC"), 0)
    result["fixed_venue_flow"].append(
        {
            "year": cy, "pool_EC": pe, "pool_NON": pn,
            "EC_to_NON": en, "NON_to_EC": ne,
            "import_per_ec_paper": round(en / pe, 3) if pe else None,
            "export_per_non_paper": round(ne / pn, 3) if pn else None,
            "ratio_raw_edges": round(en / ne, 3) if ne else None,
            "ratio_citing_side_pools": round((en / pe) / (ne / pn), 3) if pe and pn and ne else None,
            "ratio_cited_side_pools": round((en / pn) / (ne / pe), 3) if pe and pn and ne else None,
        }
    )
result["fixed_venue_sources"] = sorted(stable)

print("\n=== 固定期刊集内流向（三归一并列） ===")
print("year  en=EC->NON  ne=NON->EC  raw  citing_side  cited_side")
for r in result["fixed_venue_flow"]:
    if r["year"] >= 2005:
        print(
            f"{r['year']}  {r['EC_to_NON']:>6}  {r['NON_to_EC']:>6}  "
            f"{r['ratio_raw_edges']}  {r['ratio_citing_side_pools']}  {r['ratio_cited_side_pools']}"
        )

with open(os.path.join(OUT, "trade.json"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)

print("\n=== 全库：各群体内部每篇论文的库内引用数 ===")
print("year  poolEC  poolNON   EC->EC/EC  EC->NON/EC  NON->EC/NON  NON->NON/NON")
for r in result["flow"]:
    if not r["a_tier_only"] and r["year"] >= 2004:
        print(
            f"{r['year']}  {r['pool_EC']:>6}  {r['pool_NON']:>7}   "
            f"{r['intra_ec_per_ec_paper']:.2f}  {r['import_per_ec_paper']:.2f}  "
            f"{r['export_per_non_paper']:.3f}  {r['intra_non_per_non_paper']:.2f}"
        )
print("\n=== A_pure_ec 期刊内：每篇 EC 论文 ===")
for r in result["flow"]:
    if r["a_tier_only"] and r["year"] >= 2005 and r["pool_EC"] > 50:
        print(
            f"{r['year']}  poolEC={r['pool_EC']:>5}  EC->EC={r['intra_ec_per_ec_paper']:.2f}"
            f"  EC->NON={r['import_per_ec_paper']:.2f}"
        )
print("\n=== 经典垄断度（→EC 引用中 Top-50 老论文份额）===")
for r in result["classic_monopoly"]:
    if r["dst_group"] == "EC" and not r["a_tier_only"] and r["year"] >= 2005:
        print(f"{r['year']}  {r['share_top50']:.1%}  (n={r['n']})")
print("\n=== 经典垄断度（→非EC 引用中 Top-50 份额）===")
for r in result["classic_monopoly"]:
    if r["dst_group"] == "NON_EC" and not r["a_tier_only"] and r["year"] >= 2005:
        print(f"{r['year']}  {r['share_top50']:.1%}  (n={r['n']})")
