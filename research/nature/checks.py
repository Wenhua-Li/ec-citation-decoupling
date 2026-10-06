# -*- coding: utf-8 -*-
"""稳健性三检验（2026-09-29 W0.1 修订版）：
  C1) CD5 的 EC vs NON 分歧：按库内参考数分桶（控制参考集稀疏度的机械效应）
  C2) 出口回落：固定"稳定混合期刊集"内 NON->EC 每篇引用率的年度走势
      —— 判据改用 papers.source（venue_tag 是导出批次标签，跨段必然为空，data_caveats 第 4 条）；
         稳定集为空则报错退出；入选刊源名单写入结果文件
  C3) NSGA-II 的被引时序：oc 单源为主口径（data_caveats 第 2 条），全源对照，均止于 2025 年
"""
import json
import os
import statistics
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ecdb

HERE = os.path.dirname(os.path.abspath(__file__))

print("loading edges & refs ...", flush=True)
refs = defaultdict(set)
for r in ecdb.raw_sql(
    "SELECT DISTINCT r.accession_no acc, pc.accession_no cited FROM paper_refs_out r "
    "JOIN papers pc ON pc.doi = r.cited_doi",
    max_rows=3000000,
)["rows"]:
    refs[r["acc"]].add(r["cited"])
label_of, year_of, source_of = {}, {}, {}
for r in ecdb.raw_sql(
    "SELECT p.accession_no acc, p.pub_year y, p.source src, d.label l "
    "FROM papers p JOIN paper_domain d USING(accession_no)",
    max_rows=200000,
)["rows"]:
    label_of[r["acc"]] = r["l"]
    year_of[r["acc"]] = r["y"]
    source_of[r["acc"]] = r["src"]
cited_by = defaultdict(list)
for acc, cs in refs.items():
    for c in cs:
        cited_by[c].append(acc)

# C1: 分桶 CD5，cohort 2005-2007 vs 2018-2020
def cd5_of(p, t):
    qs = [q for q in cited_by.get(p, []) if t <= year_of.get(q, -1) <= t + 5]
    if len(qs) < 3:
        return None
    Rp = refs.get(p, set()) - {p}
    pos = neg = 0
    for q in qs:
        Rq = refs.get(q)
        if not Rq:
            continue
        if Rq & Rp:
            neg += 1
        else:
            pos += 1
    n = pos + neg
    return (pos - neg) / n if n else None

def bucket(n):
    if n < 5: return None
    if n <= 10: return "5-10"
    if n <= 20: return "11-20"
    if n <= 40: return "21-40"
    return ">40"

print("\n=== C1 分桶 CD5（均值）===")
res_c1 = {}
for era, ys in (("2005-07", range(2005, 2008)), ("2018-20", range(2018, 2021))):
    cell = defaultdict(lambda: defaultdict(list))  # label -> bucket -> vals
    for t in ys:
        for p, y in year_of.items():
            if y != t or p not in refs:
                continue
            b = bucket(len(refs[p]))
            if not b:
                continue
            v = cd5_of(p, t)
            if v is None:
                continue
            cell[label_of.get(p)][b].append(v)
    for lab in cell:
        for b, vals in sorted(cell[lab].items()):
            if len(vals) >= 30:
                key = f"{era}|{lab}|{b}"
                res_c1[key] = {"mean": round(statistics.mean(vals), 3), "n": len(vals)}
                print(f"{key}: {res_c1[key]}")

# C2: 固定稳定混合期刊集内的出口率（source 口径，W0.1 修复）
print("\n=== C2 固定期刊集 NON->EC 出口率（source 口径） ===")
src_non_year = defaultdict(lambda: defaultdict(int))
for acc, y in year_of.items():
    if label_of.get(acc) == "NON_EC":
        src_non_year[source_of[acc]][y] += 1
stable = set()
for s, ys in src_non_year.items():
    n_early = sum(v for y, v in ys.items() if 2005 <= y <= 2010)
    n_late = sum(v for y, v in ys.items() if 2020 <= y <= 2025)
    if n_early >= 300 and n_late >= 300:
        stable.add(s)
print("stable mixed sources:", sorted(stable))
if not stable:
    raise SystemExit("C2 stable source set is EMPTY — criterion or data problem; refusing to write empty result")
# 这些期刊上的 NON 论文每年引用 EC 的次数 / 该期刊 NON 论文数
non_in_stable = defaultdict(int)
for acc, y in year_of.items():
    if label_of.get(acc) == "NON_EC" and source_of[acc] in stable:
        non_in_stable[y] += 1
exp_to_ec = defaultdict(int)
for src_acc, cs in refs.items():
    if label_of.get(src_acc) == "NON_EC" and source_of.get(src_acc) in stable:
        for c in cs:
            if label_of.get(c) == "EC":
                exp_to_ec[year_of[src_acc]] += 1
res_c2 = []
for y in sorted(non_in_stable):
    if y < 2005 or y > 2025 or non_in_stable[y] < 100:
        continue
    rate = exp_to_ec.get(y, 0) / non_in_stable[y]
    res_c2.append({"year": y, "rate": round(rate, 3), "n_non": non_in_stable[y]})
    print(y, f"{rate:.3f}  (n={non_in_stable[y]})")
if not res_c2:
    raise SystemExit("C2 result is EMPTY after year/n filters — refusing to write empty result")

# C3: NSGA-II 被引时序（oc 单源为主；全源对照；均止于 2025）
print("\n=== C3 NSGA-II 被引时序（库内，oc 单源 / 全源对照） ===")
rows = ecdb.raw_sql(
    """
    SELECT c.source s, c.citing_year cy, COUNT(*) n FROM paper_cited_in c
    JOIN papers p ON p.doi='10.1109/4235.996017'
    WHERE c.accession_no = p.accession_no AND c.citing_year IS NOT NULL AND c.citing_year <= 2025
    GROUP BY s, cy ORDER BY cy
    """,
    max_rows=100,
)["rows"]
res_c3 = {"oc": {}, "all": {}}
n_trunc_c3 = ecdb.raw_sql(
    "SELECT COUNT(*) n FROM paper_cited_in c JOIN papers p ON p.doi='10.1109/4235.996017' "
    "WHERE c.accession_no = p.accession_no AND c.citing_year > 2025",
    max_rows=1,
)["rows"][0]["n"]
for r in rows:
    res_c3["all"][str(r["cy"])] = res_c3["all"].get(str(r["cy"]), 0) + r["n"]
    if r["s"] == "oc":
        res_c3["oc"][str(r["cy"])] = r["n"]
print("oc:", res_c3["oc"])
print("rows with citing_year>2025 excluded:", n_trunc_c3)

out = {
    "c1_bucket_cd5": res_c1,
    "c2_fixed_venue_export": res_c2,
    "c2_stable_sources": sorted(stable),
    "c3_nsga2_series": res_c3,
    "c3_truncated_gt2025": n_trunc_c3,
}
with open(os.path.join(HERE, "out", "checks.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
