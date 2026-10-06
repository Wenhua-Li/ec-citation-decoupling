# -*- coding: utf-8 -*-
"""W0.3/W0.5（评审 F2/F6）：P3 存亡判定——对照组稳定性与解析率分层。

A) 参考文献解析率序列：每篇论文的参考文献列表（DISTINCT cited_doi）中能回连到库内论文的
   比例，按 发表年 × EC/非EC 报告均值。评审实测 EC 2025 年约 0.312、非 EC 约 0.096（3.25 倍），
   而 CD5 对解析密度单调——分化的机械成分必须在同解析率层内检验。
B) 稳定 source 对照组 CD5：非 EC 限定为"2005-2010 与 2020-2025 各 ≥300 篇非 EC 论文"的
   source 集合（与 checks.py C2 同判据，消除非 EC 池 +112% 的构成漂移），重算 CD5 序列。
C) CD5 二维分层：按 被引侧 |Rp| 桶 × 施引侧中位 |Rq| 桶 分格，比较 2005-07 与 2018-20 两期
   EC 与非 EC 的同格差距（把解析密度机械成分从行为分化中剥离）。
D) 高解析期刊子集：source×年 均解析率 ≥90%（该年 ≥30 篇带参考文献论文）的期刊集，
   在其上重算 CD5 序列（受限共同语料版）。
口径与 disruption.py 一致：CD5 窗口 [t, t+5]，|Q|≥3，无库内参考列表的施引者不计票。
输出：research/nature/out/stability.json
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

label_of, year_of, source_of = {}, {}, {}
for r in ecdb.raw_sql(
    "SELECT d.accession_no acc, d.label, p.pub_year y, p.source s FROM paper_domain d JOIN papers p USING(accession_no)",
    max_rows=200000,
)["rows"]:
    label_of[r["acc"]] = r["label"]
    year_of[r["acc"]] = r["y"]
    source_of[r["acc"]] = r["s"]

print("loading in-db edges ...", flush=True)
refs = defaultdict(set)
for r in ecdb.raw_sql(
    "SELECT DISTINCT r.accession_no acc, pc.accession_no cited FROM paper_refs_out r "
    "JOIN papers pc ON pc.doi = r.cited_doi",
    max_rows=3000000,
)["rows"]:
    refs[r["acc"]].add(r["cited"])

print("loading total ref-list sizes ...", flush=True)
total_refs = {}
for r in ecdb.raw_sql(
    "SELECT accession_no acc, COUNT(DISTINCT cited_doi) n FROM paper_refs_out "
    "WHERE cited_doi IS NOT NULL GROUP BY accession_no",
    max_rows=200000,
)["rows"]:
    total_refs[r["acc"]] = r["n"]
print(f"papers with ref list: {len(total_refs)}, resolved: {len(refs)}", flush=True)

# A) 解析率序列（只统计参考文献列表 ≥5 条的论文，避免极短列表噪声）
res_rate = defaultdict(lambda: defaultdict(list))  # label -> year -> [rates]
for acc, tot in total_refs.items():
    if tot < 5 or acc not in year_of:
        continue
    res_rate[label_of[acc]][year_of[acc]].append(len(refs.get(acc, ())) / tot)

result_a = {}
for lab, ys in res_rate.items():
    result_a[lab] = [
        {"year": y, "mean_rate": round(statistics.mean(v), 4), "n": len(v)}
        for y, v in sorted(ys.items()) if len(v) >= 100 and 2002 <= y <= 2025
    ]
print("\n=== A) 解析率（参考文献≥5条的论文均值） ===")
for lab in ("EC", "NON_EC"):
    print(lab, {r["year"]: r["mean_rate"] for r in result_a.get(lab, []) if r["year"] % 5 == 0})

# CD5 一次算好，供 B/C/D 复用
cited_by = defaultdict(list)
for acc, cs in refs.items():
    for c in cs:
        cited_by[c].append(acc)


def cd5_detail(p, t):
    qs = [q for q in cited_by.get(p, []) if t <= year_of.get(q, -1) <= t + 5]
    if len(qs) < 3:
        return None
    Rp = refs.get(p, set()) - {p}
    n_pos = n_neg = 0
    rqs = []
    for q in qs:
        Rq = refs.get(q)
        if not Rq:
            continue
        rqs.append(len(Rq))
        if Rq & Rp:
            n_neg += 1
        else:
            n_pos += 1
    n = n_pos + n_neg
    if n == 0:
        return None
    return {"cd5": (n_pos - n_neg) / n, "rp": len(Rp), "rq_med": statistics.median(rqs)}


print("\ncomputing CD5 details for cohorts 2002-2020 ...", flush=True)
paper_info = []  # per paper: dict
for t in range(2002, 2021):
    for p, y in year_of.items():
        if y != t or p not in refs:
            continue
        d = cd5_detail(p, t)
        if d is None:
            continue
        paper_info.append(
            {
                "year": t, "label": label_of.get(p), "source": source_of.get(p),
                "cd5": d["cd5"], "rp": d["rp"], "rq_med": d["rq_med"],
            }
        )
    print(f"cohort {t}: cumulative {len(paper_info)}", flush=True)


def bucket(n):
    if n < 5:
        return None
    if n <= 10:
        return "5-10"
    if n <= 20:
        return "11-20"
    if n <= 40:
        return "21-40"
    return ">40"


# B) 稳定 source 对照组
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
print(f"\nstable mixed sources (n={len(stable)}):", sorted(stable))

result_b = {"stable_sources": sorted(stable), "series": {}}
for gname, keep in (
    ("EC", lambda r: r["label"] == "EC"),
    ("NON_EC_all", lambda r: r["label"] == "NON_EC"),
    ("NON_EC_stable", lambda r: r["label"] == "NON_EC" and r["source"] in stable),
):
    by_year = defaultdict(list)
    for r in paper_info:
        if keep(r):
            by_year[r["year"]].append(r["cd5"])
    result_b["series"][gname] = [
        {"year": y, "n": len(v), "mean": round(statistics.mean(v), 4)}
        for y, v in sorted(by_year.items()) if len(v) >= 30
    ]
print("=== B) CD5 序列（稳定对照组） ===")
for gname, s in result_b["series"].items():
    print(gname, {r["year"]: r["mean"] for r in s if r["year"] % 3 == 0})

# C) 二维分层（era × label × rp_bucket × rq_bucket）
result_c = {}
for era, ys in (("2005-07", range(2005, 2008)), ("2018-20", range(2018, 2021))):
    cell = defaultdict(lambda: defaultdict(list))
    for r in paper_info:
        if r["year"] not in ys:
            continue
        brp, brq = bucket(r["rp"]), bucket(r["rq_med"])
        if not brp or not brq:
            continue
        cell[r["label"]][(brp, brq)].append(r["cd5"])
    for lab, cells in cell.items():
        for (brp, brq), v in sorted(cells.items()):
            if len(v) >= 30:
                result_c[f"{era}|{lab}|Rp{brp}|Rq{brq}"] = {"mean": round(statistics.mean(v), 3), "n": len(v)}
print("\n=== C) CD5 二维分层（节选 Rp 21-40 桶） ===")
for k in sorted(result_c):
    if "Rp21-40" in k:
        print(k, result_c[k])

# D) 高解析期刊子集：source×年 均解析率 ≥90%（该年 ≥30 篇带参考文献论文）
src_year_rate = defaultdict(lambda: defaultdict(list))
for acc, tot in total_refs.items():
    if tot < 5 or acc not in year_of:
        continue
    src_year_rate[source_of[acc]][year_of[acc]].append(len(refs.get(acc, ())) / tot)
high_res_sources = set()
for s, ys in src_year_rate.items():
    ok = True
    for y in range(2005, 2021):  # CD5 队列区间
        v = ys.get(y)
        if v and len(v) >= 30 and statistics.mean(v) < 0.9:
            ok = False
            break
    if ok and any(len(v) >= 30 for v in ys.values()):
        high_res_sources.add(s)
print(f"\nhigh-resolution sources (>=90% all years, n={len(high_res_sources)}):", sorted(high_res_sources))

result_d = {"sources": sorted(high_res_sources), "series": {}}
for gname, keep in (
    ("EC", lambda r: r["label"] == "EC" and r["source"] in high_res_sources),
    ("NON_EC", lambda r: r["label"] == "NON_EC" and r["source"] in high_res_sources),
):
    by_year = defaultdict(list)
    for r in paper_info:
        if keep(r):
            by_year[r["year"]].append(r["cd5"])
    result_d["series"][gname] = [
        {"year": y, "n": len(v), "mean": round(statistics.mean(v), 4)}
        for y, v in sorted(by_year.items()) if len(v) >= 30
    ]
print("=== D) 高解析期刊子集 CD5 ===")
for gname, s in result_d["series"].items():
    print(gname, {r["year"]: r["mean"] for r in s if r["year"] % 3 == 0})

out = {"a_resolution_rate": result_a, "b_stable_control_cd5": result_b,
       "c_cd5_2d_strata": result_c, "d_highres_cd5": result_d}
with open(os.path.join(OUT, "stability.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("\nsaved stability.json")
