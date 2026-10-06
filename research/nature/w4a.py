# -*- coding: utf-8 -*-
"""W4a 稳健性扩展（PLAN v3 第四节；评审 F9/F10）：只读查询，不动库。

1) CD 窗口变体（截断敏感性）：CD3 / CD5 / CD10 并列（窗口 [t, t+w]，w 年施引者计票）
2) 自引剔除版 CD5：施引者与被引论文共享至少一位作者姓名的票不计
3) 团队规模控制（呼应 Wu/Wang/Evans 2019）：按被引论文作者数分桶的 CD5，EC vs 非 EC 同桶比较
4) 期刊构成控制（source 固定效应近似）：同一 source 内早期(2003-10) vs 晚期(2013-20)的 EC CD5 变化
5) 自引率口径的姓名密度敏感性（评审 F10）：随机论文对的同名重合概率（按姓名-论文频次的平方和近似）
   随年份的上升幅度，与观测自引率的下降并排——若同名机械贡献在涨而观测值在降，真实降幅更大
口径与 disruption.py 一致；作者按姓名字符串聚合（同名即合并，已知上限偏差）。
输出：research/nature/out/w4a.json
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

print("loading authors ...", flush=True)
paper_authors = defaultdict(set)
for r in ecdb.raw_sql(
    "SELECT accession_no acc, name_display nm FROM paper_authors", max_rows=800000
)["rows"]:
    paper_authors[r["acc"]].add(r["nm"])

print("loading in-db edges ...", flush=True)
refs = defaultdict(set)
for r in ecdb.raw_sql(
    "SELECT DISTINCT r.accession_no acc, pc.accession_no cited FROM paper_refs_out r "
    "JOIN papers pc ON pc.doi = r.cited_doi",
    max_rows=3000000,
)["rows"]:
    refs[r["acc"]].add(r["cited"])
cited_by = defaultdict(list)
for acc, cs in refs.items():
    for c in cs:
        cited_by[c].append(acc)

# 每篇论文的施引票明细：(citing_year, vote, is_self)
print("computing vote details (cohorts 2002-2020, window up to 10y) ...", flush=True)
votes = {}  # acc -> list[(cy, vote, self)]
for t in range(2002, 2021):
    for p, y in year_of.items():
        if y != t or p not in refs:
            continue
        Rp = refs.get(p, set()) - {p}
        pa = paper_authors.get(p, set())
        lst = []
        for q in cited_by.get(p, ()):
            cy = year_of.get(q)
            if cy is None or not (t <= cy <= t + 10):
                continue
            Rq = refs.get(q)
            if not Rq:
                continue
            v = -1 if (Rq & Rp) else 1
            is_self = 1 if (pa & paper_authors.get(q, set())) else 0
            lst.append((cy, v, is_self))
        if len(lst) >= 3:
            votes[p] = lst
    if t % 5 == 0:
        print(f"  cohort {t}: {len(votes)} papers with votes", flush=True)


def cd(p, w, drop_self=False):
    t = year_of[p]
    pos = neg = 0
    for cy, v, is_self in votes[p]:
        if cy > t + w:
            continue
        if drop_self and is_self:
            continue
        if v > 0:
            pos += 1
        else:
            neg += 1
    n = pos + neg
    return (pos - neg) / n if n >= 3 else None


def series(gname, w, drop_self=False):
    by_year = defaultdict(list)
    for p, _ in votes.items():
        if label_of.get(p) != gname:
            continue
        v = cd(p, w, drop_self)
        if v is not None and year_of[p] <= 2025 - w:
            by_year[year_of[p]].append(v)
    return {y: {"n": len(v), "mean": round(statistics.mean(v), 4)}
            for y, v in sorted(by_year.items()) if len(v) >= 30}


out = {}

# 1) 窗口变体
out["cd_window_variants"] = {}
for w in (3, 5, 10):
    out["cd_window_variants"][f"CD{w}"] = {
        "EC": series("EC", w), "NON_EC": series("NON_EC", w),
    }
    print(f"\n=== CD{w} ===")
    ec = out["cd_window_variants"][f"CD{w}"]["EC"]
    non = out["cd_window_variants"][f"CD{w}"]["NON_EC"]
    for y in sorted(set(ec) & set(non)):
        if y % 3 == 0 or y in (2019, 2020):
            print(f"{y}  EC={ec[y]['mean']:+.3f}  NON={non[y]['mean']:+.3f}  gap={ec[y]['mean']-non[y]['mean']:+.3f}")

# 2) 自引剔除版 CD5
out["cd5_no_self"] = {"EC": series("EC", 5, drop_self=True), "NON_EC": series("NON_EC", 5, drop_self=True)}
print("\n=== CD5 剔除自引票 ===")
for y in sorted(set(out["cd5_no_self"]["EC"]) & set(out["cd5_no_self"]["NON_EC"])):
    if y % 3 == 0:
        print(f"{y}  EC={out['cd5_no_self']['EC'][y]['mean']:+.3f}  NON={out['cd5_no_self']['NON_EC'][y]['mean']:+.3f}")

# 3) 团队规模分桶
def team_bucket(n):
    if n <= 2: return "1-2"
    if n <= 4: return "3-4"
    if n <= 6: return "5-6"
    return "7+"


out["team_size"] = {"buckets": {}, "mean_team_size": {}}
for era, ys in (("2005-07", range(2005, 2008)), ("2018-20", range(2018, 2021))):
    cell = defaultdict(lambda: defaultdict(list))
    for p, _ in votes.items():
        if year_of[p] not in ys:
            continue
        b = team_bucket(len(paper_authors.get(p, ())))
        v = cd(p, 5)
        if v is not None:
            cell[label_of.get(p)][b].append(v)
    for lab, bs in cell.items():
        for b, v in bs.items():
            if len(v) >= 30:
                out["team_size"]["buckets"][f"{era}|{lab}|{b}"] = {"mean": round(statistics.mean(v), 3), "n": len(v)}
for lab in ("EC", "NON_EC"):
    ms = defaultdict(list)
    for p in votes:
        if label_of.get(p) == lab:
            ms[year_of[p]].append(len(paper_authors.get(p, ())))
    out["team_size"]["mean_team_size"][lab] = {str(y): round(statistics.mean(v), 2)
                                               for y, v in sorted(ms.items()) if len(v) >= 100 and y >= 2005}
print("\n=== 团队规模分桶 CD5（EC vs NON 同桶） ===")
for k in sorted(out["team_size"]["buckets"]):
    print(k, out["team_size"]["buckets"][k])
print("mean team size EC:", {y: v for y, v in out["team_size"]["mean_team_size"]["EC"].items() if int(y) % 5 == 0})

# 4) source 固定效应近似：同 source 早期 vs 晚期（EC 论文）
cell = defaultdict(lambda: {"early": [], "late": []})
for p, _ in votes.items():
    if label_of.get(p) != "EC":
        continue
    v = cd(p, 5)
    if v is None:
        continue
    y = year_of[p]
    s = source_of.get(p)
    if 2003 <= y <= 2010:
        cell[s]["early"].append(v)
    elif 2013 <= y <= 2020:
        cell[s]["late"].append(v)
out["source_within_decline"] = {}
for s, d in cell.items():
    if len(d["early"]) >= 80 and len(d["late"]) >= 80:
        e, l = statistics.mean(d["early"]), statistics.mean(d["late"])
        out["source_within_decline"][s] = {
            "early_mean": round(e, 3), "late_mean": round(l, 3), "delta": round(l - e, 3),
            "n_early": len(d["early"]), "n_late": len(d["late"]),
        }
print("\n=== 同一 source 内 EC CD5 变化（2003-10 → 2013-20） ===")
for s, d in sorted(out["source_within_decline"].items(), key=lambda kv: kv[1]["delta"]):
    print(f"{s[:60]:<60} {d['early_mean']:+.3f} -> {d['late_mean']:+.3f}  Δ={d['delta']:+.3f}  (n={d['n_early']}/{d['n_late']})")

# 5) 姓名密度敏感性：随机论文对同名重合概率（Σ_n (c_n/N)^2，c_n 为姓名 n 截至该年的累计论文数）
name_papers = defaultdict(list)
for acc, names in paper_authors.items():
    for nm in names:
        y = year_of.get(acc)
        if y:
            name_papers[nm].append(y)


def name_overlap_proxy(year):
    """随机抽两篇论文（截至 year），它们共享至少一位同名作者的概率下界近似 = Σ(c_n/N)^2。"""
    s = n = 0
    for ys in name_papers.values():
        c = 0
        for y in ys:
            if y <= year:
                c += 1
        if c:
            s += c * c
            n += c
    return round(s / (n * n), 5) if n else None


out["name_density"] = {}
for y in range(2005, 2026, 3):
    out["name_density"][str(y)] = name_overlap_proxy(y)
    print(f"name-overlap proxy {y}: {out['name_density'][str(y)]}")

with open(os.path.join(OUT, "w4a.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("\nsaved w4a.json")
