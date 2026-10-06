# -*- coding: utf-8 -*-
"""破坏性指数 CD5（Funk & Owen-Smith / Park et al. Nature 2023 口径，库内子网适配）。

对 cohort 年 t 的每篇论文 p：
  - R(p) = p 的库内参考文献（refs_out 中 cited_doi 回连库内的 DISTINCT 边）
  - 施引集 Q = [t, t+5] 内引用 p 的库内论文（同样由 refs_out 回连得到）
  - q∈Q：若 R(q) ∩ (R(p)\{p}) = 空 → 破坏性引用(+1)；否则 巩固性引用(−1)
  - CD5 = (N+ − N−) / |Q|（要求 |Q| ≥ 3）
分 cohort 年输出均值/中位数，分 EC / NON_EC / A_pure_ec 三口径。
输出：research/nature/out/disruption.json
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

print("loading in-db edges (refs_out doi-join) ...", flush=True)
refs = defaultdict(set)  # acc -> set(cited acc)
edge_rows = ecdb.raw_sql(
    """
    SELECT DISTINCT r.accession_no acc, pc.accession_no cited
    FROM paper_refs_out r
    JOIN papers pc ON pc.doi = r.cited_doi
    """,
    max_rows=3000000,
)["rows"]
for r in edge_rows:
    refs[r["acc"]].add(r["cited"])
print(f"edges: {len(edge_rows)}, papers with refs: {len(refs)}", flush=True)

# 库内被引：cited -> [citing]
cited_by = defaultdict(list)
for acc, cs in refs.items():
    for c in cs:
        cited_by[c].append(acc)

def cd5(p, t):
    qs = [q for q in cited_by.get(p, []) if t <= year_of.get(q, -1) <= t + 5]
    if len(qs) < 3:
        return None, len(qs)
    Rp = refs.get(p, set()) - {p}
    n_pos = n_neg = 0
    for q in qs:
        Rq = refs.get(q)
        if not Rq:
            continue  # 无参考列表的施引者无法判别，跳过
        if Rq & Rp:
            n_neg += 1
        else:
            n_pos += 1
    n = n_pos + n_neg
    if n == 0:
        return None, len(qs)
    return (n_pos - n_neg) / n, n

result = []
groups = {"all": lambda a: True,
          "EC": lambda a: label_of.get(a) == "EC",
          "NON_EC": lambda a: label_of.get(a) == "NON_EC",
          "A_pure_ec": lambda a: tier_of.get(venue_of.get(a)) == "A_pure_ec"}

venue_of = {}
for r in ecdb.raw_sql("SELECT accession_no acc, venue_tag vt FROM papers", max_rows=200000)["rows"]:
    venue_of[r["acc"]] = r["vt"]

for t in range(2000, 2021):
    accs = [a for a, y in year_of.items() if y == t]
    row = {"year": t}
    for gname, gfn in groups.items():
        vals, ns = [], []
        for p in accs:
            if p not in refs or not gfn(p):
                continue
            v, n = cd5(p, t)
            if v is not None:
                vals.append(v)
                ns.append(n)
        if len(vals) >= 30:
            row[gname] = {"n": len(vals), "mean": round(statistics.mean(vals), 4),
                          "median": round(statistics.median(vals), 4)}
    result.append(row)
    print(t, {k: v for k, v in row.items() if k != "year"}, flush=True)

with open(os.path.join(OUT, "disruption.json"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)
print("saved.")
