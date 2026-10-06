# -*- coding: utf-8 -*-
"""作者世代 / 自我引用 / 互引分析。

  1) 新人率：当年论文作者中"库内首秀"作者的论文份额；老将（首秀距今>=15年）产量份额
  2) 作者自引率：库内引用边中，施引与被引共享至少一位作者姓名的边份额，按施引年
  3) 互引率（reciprocity）：边 a->b 存在时 b->a 也存在的比例；以及两人对（作者对）互引强度
  4) 产量集中度：top 1% 作者占当年论文份额（全库 & EC）
注意：作者按姓名字符串聚合（同名无法消歧），自引率是上界估计。
输出：research/nature/out/authors.json
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

print("loading authors ...", flush=True)
rows = ecdb.raw_sql(
    "SELECT a.accession_no acc, a.name_display nm, p.pub_year y, d.label l "
    "FROM paper_authors a JOIN papers p USING(accession_no) JOIN paper_domain d USING(accession_no)",
    max_rows=700000,
)["rows"]
paper_authors = defaultdict(list)  # acc -> [names]
author_years = defaultdict(list)  # name -> [years]
paper_label = {}
paper_year = {}
for r in rows:
    paper_authors[r["acc"]].append(r["nm"])
    author_years[r["nm"]].append(r["y"])
    paper_label[r["acc"]] = r["l"]
    paper_year[r["acc"]] = r["y"]
print(f"papers {len(paper_authors)}, unique names {len(author_years)}", flush=True)

first_year = {nm: min(ys) for nm, ys in author_years.items()}

# 1) 新人率 / 老将份额
print("computing entrant/veteran shares ...", flush=True)
entrant = defaultdict(lambda: [0, 0, 0])  # year -> [papers, papers_with_new_author, papers_by_veteran_lead]
for acc, names in paper_authors.items():
    y = paper_year[acc]
    if y < 2003:
        continue
    entrant[y][0] += 1
    if any(first_year.get(nm) == y for nm in names):
        entrant[y][1] += 1
    if any(first_year.get(nm, 9999) <= y - 15 for nm in names):
        entrant[y][2] += 1

# 2) 自引率（库内边）
print("loading edges ...", flush=True)
edges = ecdb.raw_sql(
    """
    SELECT DISTINCT r.accession_no src, pc.accession_no dst
    FROM paper_refs_out r JOIN papers pc ON pc.doi = r.cited_doi
    """,
    max_rows=3000000,
)["rows"]
print(f"edges {len(edges)}", flush=True)
self_cit = defaultdict(lambda: [0, 0])  # citing year -> [edges, self edges]
recip = defaultdict(lambda: [0, 0])
edge_set = {(e["src"], e["dst"]) for e in edges}
label_of = paper_label
for e in edges:
    y = paper_year[e["src"]]
    self_cit[y][0] += 1
    sa = set(paper_authors.get(e["src"], []))
    da = set(paper_authors.get(e["dst"], []))
    if sa & da:
        self_cit[y][1] += 1
    recip[y][0] += 1
    if (e["dst"], e["src"]) in edge_set:
        recip[y][1] += 1

# 3) 集中度：每年 top1% 作者（按截至前一年的累计产量）份额 — 简化：按当年产量 top1% 份额
year_prolific = defaultdict(list)
for nm, ys in author_years.items():
    for y in set(ys):
        year_prolific[y].append(nm)

result = {
    "entrants": [
        {"year": y, "papers": v[0],
         "share_papers_with_newcomer": round(v[1] / v[0], 4),
         "share_papers_with_veteran15": round(v[2] / v[0], 4)}
        for y, v in sorted(entrant.items())
    ],
    "self_citation": [
        {"year": y, "rate": round(v[1] / v[0], 4), "n": v[0]} for y, v in sorted(self_cit.items()) if v[0] > 200
    ],
    "reciprocity": [
        {"year": y, "rate": round(v[1] / v[0], 4), "n": v[0]} for y, v in sorted(recip.items()) if v[0] > 200
    ],
}

with open(os.path.join(OUT, "authors.json"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)

print("\n=== 新人率 / 老将(>=15年)份额 ===")
for r in result["entrants"]:
    print(f"{r['year']}  papers={r['papers']:>6}  新人参与={r['share_papers_with_newcomer']:.1%}  老将参与={r['share_papers_with_veteran15']:.1%}")
print("\n=== 库内边的作者自引率 ===")
for r in result["self_citation"]:
    print(f"{r['year']}  {r['rate']:.1%}  (n={r['n']})")
print("\n=== 互引率 ===")
for r in result["reciprocity"]:
    print(f"{r['year']}  {r['rate']:.2%}  (n={r['n']})")
