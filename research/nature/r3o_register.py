# -*- coding: utf-8 -*-
"""R3-O 登记脚本：叙事定稿两个新量 + 作者槽位权重版校正比 + 格级区间与覆盖度。

产出：research/nature/out/r3o_quantities.json
  1) 构成校正首选比（论文权重版）= 新人首选份额 / 当年 EC 论文语料份额；
  2) 构成校正首选比（作者槽位权重版，方向未定）= 同分子 / 当年 EC 作者槽位语料份额；
  3) 二维同格格级表（2018-20 八个共有格的 gap/n）+ 区间 + 覆盖率（对 disruption.json 可算总数）。

自检（脚本内置，任一失败即非零退出）：
  - 首选份额与 PKG-A authors_flow.json first_dir_series.full 逐年一致（|diff|<=0.002）；
  - 八个共有格 gap 全负且落在 [-0.25, -0.08]；
  - 覆盖率与叙事定稿引值一致（EC ~84.1% / NON ~67.0%，容差 0.5pp）。
只读库；不写 NUMBERS.md（登记行由主线按本输出手工写入）。
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

# --- 1) 新人首选份额（与 PKG-A author_flow.py build() 逐字同口径） -----------------
print("loading author-paper-label rows ...", flush=True)
rows = ecdb.raw_sql(
    "SELECT a.name_display nm, p.pub_year y, d.label l "
    "FROM paper_authors a JOIN papers p USING(accession_no) JOIN paper_domain d USING(accession_no)",
    max_rows=2000000,
)["rows"]
author_years_labels = defaultdict(list)  # nm -> [(year, label)]
skipped = 0
for r in rows:
    if r["nm"] is None or r["y"] is None:
        skipped += 1
        continue
    author_years_labels[r["nm"]].append((r["y"], r["l"]))
print(f"authors: {len(author_years_labels)}; skipped null rows: {skipped}", flush=True)

first_dir = defaultdict(lambda: [0, 0])  # year -> [n_first_ec, n_total]
for nm, yls in author_years_labels.items():
    first_y = min(y for y, _ in yls)
    if first_y >= 2003:
        first_dir[first_y][1] += 1
        ec = sum(1 for y, l in yls if y == first_y and l == "EC")
        non = sum(1 for y, l in yls if y == first_y and l != "EC")
        if ec > non:
            first_dir[first_y][0] += 1

share = {str(y): round(v[0] / v[1], 4) for y, v in sorted(first_dir.items()) if v[1] >= 100}

# --- 2) 语料份额（论文权重 / 作者槽位权重） ----------------------------------------
cnt = ecdb.raw_sql(
    "SELECT p.pub_year y, d.label l, COUNT(*) n_p FROM papers p "
    "JOIN paper_domain d ON d.accession_no=p.accession_no GROUP BY y, l",
    max_rows=500,
)["rows"]
slot = ecdb.raw_sql(
    "SELECT p.pub_year y, d.label l, COUNT(*) n_s FROM paper_authors a "
    "JOIN papers p USING(accession_no) JOIN paper_domain d ON d.accession_no=p.accession_no "
    "GROUP BY y, l",
    max_rows=500,
)["rows"]

def ec_share_by(res, key):
    tot, ec = defaultdict(int), defaultdict(int)
    for r in res:
        tot[r["y"]] += r[key]
        if r["l"] == "EC":
            ec[r["y"]] += r[key]
    return {str(y): round(ec[y] / tot[y], 4) for y in sorted(tot)}

ec_share_paper = ec_share_by(cnt, "n_p")
ec_share_slot = ec_share_by(slot, "n_s")

corrected_paper, corrected_slot = {}, {}
for y, s in share.items():
    if y in ec_share_paper and ec_share_paper[y] > 0:
        corrected_paper[y] = round(s / ec_share_paper[y], 4)
    if y in ec_share_slot and ec_share_slot[y] > 0:
        corrected_slot[y] = round(s / ec_share_slot[y], 4)

# --- 3) 格级表与覆盖率（stability.json + disruption.json） -------------------------
st = json.load(open(os.path.join(OUT, "stability.json"), encoding="utf-8"))
dj = json.load(open(os.path.join(OUT, "disruption.json"), encoding="utf-8"))
cells = {}
for k, v in st["c_cd5_2d_strata"].items():
    win, grp, rp, rq = k.split("|")
    cells.setdefault((win, rp, rq), {})[grp] = v

table = []
sum_n = {"EC": 0, "NON_EC": 0}
for (win, rp, rq), g in sorted(cells.items()):
    if win != "2018-20":
        continue
    for grp in ("EC", "NON_EC"):
        if grp in g:
            sum_n[grp] += g[grp]["n"]
    if "EC" in g and "NON_EC" in g:
        table.append({
            "cell": f"{rp}|{rq}", "ec_mean": g["EC"]["mean"], "ec_n": g["EC"]["n"],
            "non_mean": g["NON_EC"]["mean"], "non_n": g["NON_EC"]["n"],
            "gap": round(g["EC"]["mean"] - g["NON_EC"]["mean"], 3),
        })
gaps = [t["gap"] for t in table]
tot_comp = {"EC": 0, "NON_EC": 0}
for e in dj:
    if e.get("year") in (2018, 2019, 2020):
        tot_comp["EC"] += e["EC"]["n"]
        tot_comp["NON_EC"] += e["NON_EC"]["n"]
coverage = {g: round(sum_n[g] / tot_comp[g], 4) for g in ("EC", "NON_EC")}

# --- 自检 -------------------------------------------------------------------------
ok = True
pkg = json.load(open(os.path.join(ROOT, "archive", "packages", "w6_authors", "out", "authors_flow.json"),
                     encoding="utf-8"))["first_dir_series"]["full"]
for y, v in pkg.items():
    if y in share and abs(share[y] - v) > 0.002:
        print(f"[FAIL] first-choice mismatch {y}: {share[y]} vs PKG-A {v}")
        ok = False
assert len(table) == 8, f"matched cells != 8: {len(table)}"
if not (all(g < 0 for g in gaps) and -0.26 <= min(gaps) and max(gaps) <= -0.07):
    print(f"[FAIL] gap range: {min(gaps)}..{max(gaps)}")
    ok = False
if abs(coverage["EC"] - 0.841) > 0.005 or abs(coverage["NON_EC"] - 0.670) > 0.005:
    print(f"[FAIL] coverage vs narrative: {coverage}")
    ok = False
if not ok:
    sys.exit(1)

result = {
    "first_choice_share": share,
    "ec_corpus_share_paper_weight": ec_share_paper,
    "ec_corpus_share_slot_weight": ec_share_slot,
    "corrected_first_choice_ratio_paper_weight": corrected_paper,
    "corrected_first_choice_ratio_slot_weight": corrected_slot,
    "strata_2018_20_matched_cells": table,
    "strata_gap_range_2018_20": [min(gaps), max(gaps)],
    "strata_n_range_ec": [min(t["ec_n"] for t in table), max(t["ec_n"] for t in table)],
    "strata_coverage_2018_20": {**coverage,
                                "denominator_computable": tot_comp,
                                "numerator_strata_n": sum_n,
                                "definition": "分层表该组全部格 n 之和 / disruption.json 该组 2018-20 可算论文数"},
    "checks": "all PASS (vs PKG-A series / 8-cell range / narrative coverage)",
}
with open(os.path.join(OUT, "r3o_quantities.json"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)

print("\nfirst-choice anchors:", {y: share[y] for y in ("2005", "2025") if y in share})
print("EC paper share:", {y: ec_share_paper[y] for y in ("2000", "2005", "2025")})
print("corrected (paper):", {y: corrected_paper.get(y) for y in ("2003", "2005", "2013", "2022", "2025")})
print("corrected (slot): ", {y: corrected_slot.get(y) for y in ("2003", "2005", "2013", "2022", "2025")})
print(f"strata: 8 cells, gaps {min(gaps)}..{max(gaps)}, EC n {result['strata_n_range_ec']}")
print("coverage:", coverage, "totals:", tot_comp)
print("saved r3o_quantities.json")
