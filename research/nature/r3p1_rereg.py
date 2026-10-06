# -*- coding: utf-8 -*-
"""R3-P1（写稿前置 ①）：三项欠登记读数重跑、对账与登记依据。

背景：前期内部评审给出三条读数但未附输出文件路径，无法当场复核。
处置：先独立重跑验证再登记，不得直接采信。

三项（全部已复现，见 out/r3p1_*.json）：
  ① 年度三维同格 2018/2019/2020 × Rp 桶 × Rq 桶 → 23 格，21 格为负（91.3%）
  ② 回归控制 cd5 ~ EC + |Rp| + |Rq| + 年FE → n=11,134（EC 3,891），EC 效应 −0.1596
  ③ 库内解析参考文献中位数 EC vs 非 EC 逐年 → 2010 年 3/3 → 2025 年 13/4

对账记录（评审值 → 本会话复算值）：
  ① 评审"23 格中 21 格为负（91%），中位点差约 −0.17"，两个翻正格点名
     2018 年 10-19|20-29、2018 年 20-29|10-19 → **逐字复现**。关键是分桶必须用
     **整数十年桶**（//10），而非分位数十分位；本会话先用分位十分位得 13/17 为负，为口径差异。
  ② 评审 n=11,134(EC 3,891)、EC −0.1596、|Rp| −0.0172、|Rq| −0.0278、年效应 +0.0497/+0.1146
     → **逐字复现**。关键是 |Rq| 取**施引者库内参考列表中位数**（stability.py cd5_detail 口径），
     且样本限 cohort 2018–2020；若改用全池参考列表均值，EC 系数变 −0.2939（规格敏感，见 variants）。
  ③ 评审"2010 年 4/3 → 2025 年 13/5"与"2010 年前 EC 不高于非 EC" → **部分不成立**。
     2025 年非 EC 中位为 4 不是 5；2010 年前 9 年中 EC 中位高于非 EC 的有 6 年（非评审所述全不高于）。
     评审的机制线索（EC 引用密度 2010 年后反超并拉开）**方向成立**，但两个具体数字须以本会话复算值为准。

口径纪律（与既有脚本逐字一致，保证可对账）：
  - CD5：research/nature/disruption.py（窗口 [t,t+5]，|Q|>=3，无库内参考列表的施引者不计票）
  - 库内边：refs_out.cited_doi JOIN papers.doi，DISTINCT
  - rq_med：research/nature/stability.py cd5_detail
  - 解析率分母：paper_refs_out 中 DISTINCT cited_doi（NULL 剔除，与 stability.py 一致）

输出：research/nature/out/r3p1_recon.json + out/r3p1_rereg_run.log
"""
import json
import os
import statistics
import sys
from collections import defaultdict

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ecdb

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

MIN_CELL = 30          # 格内每群体最小样本（沿用 stability.py）
COHORT_3D = (2018, 2019, 2020)   # 三维同格与回归的 cohort 区间（与评审对账锚点）

# ---------------------------------------------------------------- 载入
label_of, year_of = {}, {}
for r in ecdb.raw_sql(
    "SELECT d.accession_no acc, d.label, p.pub_year y FROM paper_domain d "
    "JOIN papers p USING(accession_no)",
    max_rows=200000,
)["rows"]:
    label_of[r["acc"]] = r["label"]
    year_of[r["acc"]] = r["y"]

print("loading in-db edges ...", flush=True)
refs = defaultdict(set)
for r in ecdb.raw_sql(
    "SELECT DISTINCT r.accession_no acc, pc.accession_no cited FROM paper_refs_out r "
    "JOIN papers pc ON pc.doi = r.cited_doi",
    max_rows=3000000,
)["rows"]:
    refs[r["acc"]].add(r["cited"])
print(f"papers with in-db refs: {len(refs)}", flush=True)

print("loading ref-list sizes ...", flush=True)
total_refs = {}
for r in ecdb.raw_sql(
    "SELECT accession_no acc, COUNT(DISTINCT cited_doi) n FROM paper_refs_out "
    "WHERE cited_doi IS NOT NULL GROUP BY accession_no",
    max_rows=200000,
)["rows"]:
    total_refs[r["acc"]] = r["n"]
print(f"papers with ref list: {len(total_refs)}", flush=True)

cited_by = defaultdict(list)
for acc, cs in refs.items():
    for c in cs:
        cited_by[c].append(acc)

# ---------------------------------------------------------------- CD5（口径同 disruption.py）
def cd5_detail(p, t):
    """返回 (cd5, rp, rq_med)；逐字沿用 stability.py cd5_detail。"""
    qs = [q for q in cited_by.get(p, []) if t <= year_of.get(q, -1) <= t + 5]
    if len(qs) < 3:
        return None
    rp = refs.get(p, set()) - {p}
    if not rp:
        return None
    pos = neg = 0
    rqs = []
    for q in qs:
        rq = refs.get(q)
        if not rq:
            continue
        rqs.append(len(rq))
        if rq & rp:
            neg += 1
        else:
            pos += 1
    if not rqs:
        return None
    return (pos - neg) / len(qs), len(rp), statistics.median(rqs)


print("computing CD5 for cohorts 2018-2020 ...", flush=True)
info = []
for t in COHORT_3D:
    n0 = len(info)
    for p, y in year_of.items():
        if y != t or p not in refs:
            continue
        d = cd5_detail(p, t)
        if d is None:
            continue
        rq_all = [total_refs[q] for q in cited_by[p]
                  if t <= year_of.get(q, -1) <= t + 5 and total_refs.get(q)]
        info.append({
            "acc": p, "year": t, "label": label_of.get(p),
            "cd5": d[0], "rp": d[1], "rq_med": d[2],
            "rq_inmean": statistics.mean([len(refs[q]) for q in cited_by[p]
                                          if t <= year_of.get(q, -1) <= t + 5 and refs.get(q)] or [0]),
            "rq_allmean": statistics.mean(rq_all) if rq_all else None,
        })
    print(f"  cohort {t}: +{len(info)-n0} (cum {len(info)})", flush=True)
print(f"cohort 2018-2020 informative n = {len(info)}, "
      f"EC = {sum(1 for r in info if r['label'] == 'EC')}", flush=True)

# ---------------------------------------------------------------- ① 年度三维同格
def dec10(n):
    """整数十年桶（评审复用口径）。"""
    v = int(n)
    return f"{(v // 10) * 10}-{(v // 10) * 10 + 9}"


cells = defaultdict(lambda: defaultdict(list))
for r in info:
    cells[(r["year"], dec10(r["rp"]), dec10(r["rq_med"]))][r["label"]].append(r["cd5"])

tab = {}
for k, g in cells.items():
    ec, ne = g.get("EC", []), g.get("NON_EC", [])
    if len(ec) >= MIN_CELL and len(ne) >= MIN_CELL:
        tab[f"{k[0]}|{k[1]}|{k[2]}"] = {
            "gap": round(statistics.mean(ec) - statistics.mean(ne), 4),
            "ec_mean": round(statistics.mean(ec), 4), "ec_n": len(ec),
            "non_mean": round(statistics.mean(ne), 4), "non_n": len(ne),
        }
gaps = [v["gap"] for v in tab.values()]
t1 = {
    "definition": "cohort 年（2018/2019/2020，逐 year，非合并期）× Rp 整数十年桶 × Rq 中位数整数十年桶；"
                  "格内 EC 与非 EC 各 >= 30 篇",
    "n_cells": len(tab),
    "n_negative": sum(1 for g in gaps if g < 0),
    "neg_share": round(sum(1 for g in gaps if g < 0) / len(tab), 4),
    "median_gap": round(statistics.median(gaps), 4),
    "mean_gap": round(statistics.mean(gaps), 4),
    "min_gap": round(min(gaps), 4),
    "max_gap": round(max(gaps), 4),
    "positive_cells": {k: v for k, v in tab.items() if v["gap"] >= 0},
}
print(f"\n=== ① 三维同格：{t1['n_negative']}/{t1['n_cells']} 为负（{t1['neg_share']:.1%}），"
      f"中位差 {t1['median_gap']}，翻正 {len(t1['positive_cells'])} 格 ===", flush=True)
for k, v in t1["positive_cells"].items():
    print("  翻正格:", k, v, flush=True)

# ---------------------------------------------------------------- ② 回归控制（四规格）
def run_ols(xvals, tag, definition):
    rows = [(r["cd5"], 1.0 if r["label"] == "EC" else 0.0, float(r["rp"]), float(x), r["year"])
            for r, x in zip(info, xvals) if x is not None]
    y = np.array([a[0] for a in rows])
    ec = np.array([a[1] for a in rows])
    rp = np.array([a[2] for a in rows])
    rq = np.array([a[3] for a in rows])
    yr = np.array([a[4] for a in rows])
    ys = sorted(set(yr.tolist()))
    base = ys[0]
    names = ["const", "EC", "abs_Rp", "abs_Rq"] + [f"year_{v}" for v in ys if v != base]
    X = np.column_stack([np.ones_like(y), ec, rp, rq] + [(yr == v).astype(float) for v in ys if v != base])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    dof = n - k
    XtXi = np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(XtXi) * (float(resid @ resid) / dof))
    Xh = X * resid[:, None]
    se_h = np.sqrt(np.diag(XtXi @ (Xh.T @ Xh) @ XtXi * (n / dof)))
    ye = {f"year_{v}": round(float(beta[names.index(f'year_{v}')]), 4) for v in ys if v != base}
    print(f"\n[{tag}] n={n} EC={int(ec.sum())}  EC={beta[1]:+.4f} "
          f"(se_ols {se[1]:.4f}, se_hc1 {se_h[1]:.4f})  |Rp|={beta[2]:+.4f}  |Rq|={beta[3]:+.4f}", flush=True)
    print("   year effects:", ye, flush=True)
    return {
        "tag": tag, "Rq_definition": definition, "n": n, "n_EC": int(ec.sum()),
        "beta": {"const": round(float(beta[0]), 4), "EC": round(float(beta[1]), 4),
                 "abs_Rp": round(float(beta[2]), 4), "abs_Rq": round(float(beta[3]), 4)},
        "se_ols": {"EC": round(float(se[1]), 4), "abs_Rp": round(float(se[2]), 4),
                   "abs_Rq": round(float(se[3]), 4)},
        "se_hc1": {"EC": round(float(se_h[1]), 4), "abs_Rp": round(float(se_h[2]), 4),
                   "abs_Rq": round(float(se_h[3]), 4)},
        "t_hc1": {"EC": round(float(beta[1] / se_h[1]), 3),
                  "abs_Rp": round(float(beta[2] / se_h[2]), 3),
                  "abs_Rq": round(float(beta[3] / se_h[3]), 3)},
        "year_effects": ye,
        "r2": round(1 - float(resid @ resid) / float(((y - y.mean()) ** 2).sum()), 4),
    }


variants = [
    run_ols([r["rq_med"] for r in info], "A",
            "施引者库内参考列表中位数 rq_med（stability.py cd5_detail 口径）——**正文主用规格**"),
    run_ols([r["rq_inmean"] for r in info], "B", "施引者库内参考列表均值"),
    run_ols([r["rq_allmean"] for r in info], "C", "施引者参考列表全池条数均值（含库外参考文献）"),
    run_ols([total_refs.get(r["acc"]) for r in info], "D", "被引论文自身参考列表总条数（对照规格，非正文用）"),
]
print("\n规格 A 与评审报值逐项对账：评审 EC −0.1596 / |Rp| −0.0172 / |Rq| −0.0278 / "
      "年效应 +0.0497、+0.1146", flush=True)

# ---------------------------------------------------------------- ③ 库内解析参考文献中位数逐年
by_year_res = defaultdict(lambda: defaultdict(list))
for acc, tot in total_refs.items():
    if tot < 5 or acc not in year_of:
        continue
    by_year_res[label_of[acc]][year_of[acc]].append(len(refs.get(acc, ())))

series = {}
for lab in ("EC", "NON_EC"):
    series[lab] = [
        {"year": y, "median": round(statistics.median(v), 2),
         "mean": round(statistics.mean(v), 3), "n": len(v)}
        for y, v in sorted(by_year_res[lab].items())
        if len(v) >= 100 and 2002 <= y <= 2025
    ]
print("\n=== ③ 库内解析参考文献中位数（EC / 非 EC 逐年） ===", flush=True)
ec_le = n_tot = 0
for a, b in zip(series["EC"], series["NON_EC"]):
    flag = ""
    if a["year"] <= 2010:
        n_tot += 1
        if a["median"] <= b["median"]:
            ec_le += 1
            flag = "  <<< EC<=非EC"
    print(f"  {a['year']}  EC {a['median']:>5}   非EC {b['median']:>5}{flag}", flush=True)


def seg(lab, y0, y1):
    v = [x["median"] for x in series[lab] if y0 <= x["year"] <= y1]
    return round(statistics.mean(v), 2) if v else None


def endpoint(lab, y):
    return next((x["median"] for x in series[lab] if x["year"] == y), None)


t3 = {
    "definition": "论文库内解析参考文献数（refs_out 中 doi 回连库内、DISTINCT）；"
                  "仅统计参考文献列表 >=5 条的论文；每年 >=100 篇",
    "ec_le_non_until_2010": f"{ec_le}/{n_tot}",
    "seg_means": {"EC_2002_2010": seg("EC", 2002, 2010), "NON_EC_2002_2010": seg("NON_EC", 2002, 2010),
                  "EC_2011_2025": seg("EC", 2011, 2025), "NON_EC_2011_2025": seg("NON_EC", 2011, 2025)},
    "endpoints": {"EC_2010": endpoint("EC", 2010), "NON_EC_2010": endpoint("NON_EC", 2010),
                  "EC_2025": endpoint("EC", 2025), "NON_EC_2025": endpoint("NON_EC", 2025)},
    "review_claim_check": {
        "review_claimed": "2010 年 4/3 → 2025 年 13/5；2010 年前 EC 不高于非 EC",
        "recomputed": f"2010 年 3/3 → 2025 年 {endpoint('EC', 2025)}/{endpoint('NON_EC', 2025)}；"
                      f"2010 年前 9 年中 EC <= 非 EC 的为 {ec_le}/{n_tot}",
        "verdict": "方向成立、两个具体数不成立——须以本表复算值为准，不得沿用评审报值",
    },
}

# ---------------------------------------------------------------- 落盘
out = {
    "meta": {
        "purpose": "写稿前置 ① 三项欠登记读数重跑与登记依据",
        "cd5_spec": "disruption.py 逐字一致；窗口 [t,t+5]；|Q|>=3；无参考列表施引者不计票",
        "rq_med_spec": "stability.py cd5_detail 逐字一致",
        "cohort": list(COHORT_3D),
        "min_cell": MIN_CELL,
        "bin": "整数十年桶（Rp、Rq 中位数各自 //10）",
        "reconciliation": {
            "①": "评审 23 格 / 21 负 / 中位 −0.17 / 两个点名翻正格 → 逐字复现（须用整数十年桶，非分位十分位）",
            "②": "评审 n=11,134(EC 3,891) / EC −0.1596 / |Rp| −0.0172 / |Rq| −0.0278 / 年效应 +0.0497、+0.1146 "
                 "→ 逐字复现（|Rq| 须取施引者库内参考列表中位数，规格 A）",
            "③": "评审 4/3→13/5 与'2010 年前 EC 不高于非 EC' → 部分不成立；2025 非 EC 中位为 4；"
                 "2010 年前 9 年中 3 年 EC<=非 EC。机制方向成立，数值须以复算为准",
        },
    },
    "t1_3d_strata": t1,
    "t1_cells": tab,
    "t2_regression_variants": variants,
    "t3_median_resolved_refs": {"summary": t3, "series": series},
}
path = os.path.join(OUT, "r3p1_recon.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(f"\nsaved {path}", flush=True)
