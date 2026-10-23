# -*- coding: utf-8 -*-
"""零分母占比探针（P2-8，2026-10-20 批次 1；只读，不写库）。

问题：E3（跨域参考文献份额）对"零条已解析参考文献"的论文记 0 并保留在分母中
（stable8_merged.py:115-121 的 tot_refs 口径：(e/tr) if tr else 0.0）。
审稿要求按方向报告这类零分母论文在七源共同支持池中的占比。

口径完全复刻 stable8_merged.py：
  - 刊名规范化 CANON 三映射（:56-60）；
  - 共同支持 = STABLE8 去掉 Computers and Industrial Engineering（2021 后退出）；
  - 已解析参考标识 = paper_refs_out 中 cited_doi IS NOT NULL 的 DISTINCT 计数；
  - 零分母论文 = 该计数为 0（含无任何 paper_refs_out 行的论文）。

输出：research/nature/out/zero_resolved_share.json
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ecdb

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "zero_resolved_share.json")

CANON = {
    "Applied Soft Computing Journal": "Applied Soft Computing",
    "Information sciences": "Information Sciences",
    "Computers & Operations Research": "Computers and Operations Research",
}
COMMON7 = (
    "Applied Soft Computing",
    "Computers and Operations Research",
    "Engineering Applications of Artificial Intelligence",
    "European Journal of Operational Research",
    "Expert Systems with Applications",
    "IEEE Transactions on Fuzzy Systems",
    "Information Sciences",
)
YEARS = (2019, 2021, 2024, 2025)

meta = {}
for r in ecdb.raw_sql(
    "SELECT accession_no acc, pub_year y, source src, "
    "(SELECT label FROM paper_domain d WHERE d.accession_no=p.accession_no) lab "
    "FROM papers p",
    max_rows=200000,
)["rows"]:
    meta[r["acc"]] = (r["y"], CANON.get(r["src"], r["src"]), r["lab"])

tot_refs = {}
for r in ecdb.raw_sql(
    "SELECT accession_no acc, COUNT(DISTINCT cited_doi) n FROM paper_refs_out "
    "WHERE cited_doi IS NOT NULL GROUP BY 1",
    max_rows=300000,
)["rows"]:
    tot_refs[r["acc"]] = r["n"]

n_empty = ecdb.raw_sql(
    "SELECT COUNT(*) n FROM paper_refs_out WHERE cited_doi = ''", max_rows=1
)["rows"][0]["n"]

result = {
    "scope": "seven-source common support (merged canonical benchmark set minus Computers and Industrial Engineering)",
    "definition": "zero-denominator paper: COUNT(DISTINCT cited_doi)=0 over paper_refs_out rows with cited_doi IS NOT NULL (mirrors stable8_merged.py tot_refs; papers without any refs_out row count as zero)",
    "empty_string_cited_doi_rows": n_empty,
    "years": {},
}
for y in YEARS:
    cell = {}
    for key, lab in (("forward_non_ec", "NON_EC"), ("reverse_ec", "EC")):
        pool = [a for a, (yy, s, l) in meta.items() if yy == y and s in COMMON7 and l == lab]
        n_zero = sum(1 for a in pool if tot_refs.get(a, 0) == 0)
        cell[key] = {
            "n_papers": len(pool),
            "n_zero_denominator": n_zero,
            "share": round(n_zero / len(pool), 4) if pool else None,
        }
    result["years"][str(y)] = cell
    print(y, cell, flush=True)

with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("written:", os.path.relpath(OUT, ROOT))
