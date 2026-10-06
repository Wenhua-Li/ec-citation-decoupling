# -*- coding: utf-8 -*-
"""引用记忆分析：领域是否正在'忘记'自己的过去。（2026-09-29 W0.4/W0.7 修订版）

问题：一条引用从施引年份看向被引论文的年龄分布，随日历年如何漂移？
口径（评审 F5/F16 修订）：
  - 右删失：施引年 > 2025 的行一律剔除并计数（oc 施引年为记录创建年，2026 只有半年；
    data_caveats 第 2/3 条）
  - 分源并列：oc 单源（主口径，无 S2 高被引截断偏移）/ s2 单源（对照）/ all=oc+s2（与旧版可比）；
    主结论以 oc 口径为准，s2 对照一致性单独报告
  - 归一化：年龄 a 在年份 Y 的引用强度 = C(a,Y) / P(Y-a)，P 为该年出生的库内论文数
    （消除"老论文池子变大"的机械效应；注意分子含库外施引者、分母为库内容量的不对称）
  - 队列即时性用固定相对窗口（无右删失）：w01/(w01+w23)，w01+w23 对队列 t<=2023 观测完整
输出：research/nature/out/memory.json + 控制台摘要
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

CY_MAX = 2025  # 年度曲线一律止于 2025

pool = defaultdict(int)
for r in ecdb.raw_sql("SELECT pub_year y, COUNT(*) n FROM papers GROUP BY pub_year", max_rows=100)["rows"]:
    pool[r["y"]] = r["n"]

n_trunc = ecdb.raw_sql(
    "SELECT COUNT(*) n FROM paper_cited_in WHERE citing_year > ?", params=(CY_MAX,), max_rows=1
)["rows"][0]["n"]
print(f"truncated rows (citing_year > {CY_MAX}): {n_trunc}", flush=True)

print("aggregating citation ages in SQL (by source) ...", flush=True)
rows = ecdb.raw_sql(
    """
    SELECT (c.citing_year - p.pub_year) AS age, c.citing_year AS cy, c.source AS src, COUNT(*) AS n
    FROM paper_cited_in c JOIN papers p USING(accession_no)
    WHERE c.citing_year >= p.pub_year AND c.citing_year <= ?
    GROUP BY age, cy, src
    """,
    params=(CY_MAX,),
    max_rows=5000,
)["rows"]

cites = {"all": defaultdict(int), "oc": defaultdict(int), "s2": defaultdict(int)}
n_total = 0
for r in rows:
    age = min(r["age"], 30)
    cites["all"][(age, r["cy"])] += r["n"]
    if r["src"] in cites:
        cites[r["src"]][(age, r["cy"])] += r["n"]
    n_total += r["n"]
print(f"used={n_total} citing_year range capped at {CY_MAX}")


def share_series(cd):
    out = []
    for cy in range(2002, CY_MAX + 1):
        ages = []
        for (age, y), n in cd.items():
            if y == cy:
                ages.extend([age] * n)
        if len(ages) < 500:
            continue
        out.append(
            {
                "year": cy,
                "n": len(ages),
                "median_age": statistics.median(ages),
                "share_age_le_1": round(sum(1 for a in ages if a <= 1) / len(ages), 4),
                "share_age_ge_5": round(sum(1 for a in ages if a >= 5) / len(ages), 4),
                "share_age_ge_10": round(sum(1 for a in ages if a >= 10) / len(ages), 4),
            }
        )
    return out


def intensity_of(cd):
    inten = defaultdict(dict)
    for (age, cy), n in cd.items():
        p = pool.get(cy - age, 0)
        if p > 0:
            inten[age][cy] = n / p
    return inten


def youth_of(inten):
    arr = []
    for cy in range(2002, CY_MAX):
        i1, i2, i6 = (inten.get(a, {}).get(cy) for a in (1, 2, 6))
        if i1 and i2 and i6:
            arr.append({"year": cy, "I1_over_I6": round(i1 / i6, 3), "I2_over_I6": round(i2 / i6, 3)})
    return arr


result = {"truncated_rows_gt_2025": n_trunc, "cy_max": CY_MAX}
for src in ("oc", "s2", "all"):
    cd = cites[src]
    result[f"by_citing_year_{src}"] = share_series(cd)
    inten = intensity_of(cd)
    result[f"intensity_{src}"] = {
        str(a): {str(y): round(v, 4) for y, v in sorted(d.items())} for a, d in sorted(inten.items())
    }
    result[f"youth_bias_{src}"] = youth_of(inten)

rows2 = ecdb.raw_sql(
    """
    SELECT p.pub_year AS t,
      SUM(CASE WHEN c.citing_year - p.pub_year BETWEEN 0 AND 1 THEN 1 ELSE 0 END) AS w01,
      SUM(CASE WHEN c.citing_year - p.pub_year BETWEEN 2 AND 3 THEN 1 ELSE 0 END) AS w23,
      SUM(CASE WHEN c.citing_year - p.pub_year BETWEEN 4 AND 5 THEN 1 ELSE 0 END) AS w45
    FROM papers p JOIN paper_cited_in c USING(accession_no)
    WHERE c.citing_year >= p.pub_year AND c.citing_year <= ?
    GROUP BY p.pub_year
    """,
    params=(CY_MAX,),
    max_rows=100,
)["rows"]
result["cohort_windows_complete_through"] = 2023  # w01+w23 对 t<=2023 观测完整
result["cohort_windows"] = [
    {
        "year": r["t"],
        "w01": r["w01"], "w23": r["w23"], "w45": r["w45"],
        "early_share_01_of_0_3": round(r["w01"] / max(1, r["w01"] + r["w23"]), 4),
    }
    for r in rows2
]

with open(os.path.join(OUT, "memory.json"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)

print("\n=== 按施引年份：引用年龄结构（oc 单源·主口径） ===")
for r in result["by_citing_year_oc"]:
    print(
        f"{r['year']}  n={r['n']:>9}  median_age={r['median_age']:>5}  "
        f"<=1y:{r['share_age_le_1']:.1%}  >=5y:{r['share_age_ge_5']:.1%}  >=10y:{r['share_age_ge_10']:.1%}"
    )
print("\n=== s2 单源对照（仅 <=1y 与 >=5y） ===")
for r in result["by_citing_year_s2"]:
    print(f"{r['year']}  n={r['n']:>9}  <=1y:{r['share_age_le_1']:.1%}  >=5y:{r['share_age_ge_5']:.1%}")
print("\n=== 青年偏置 I(1)/I(6), I(2)/I(6)（oc 主 / s2 对照 / all 旧口径） ===")
yoc = {r["year"]: r for r in result["youth_bias_oc"]}
ys2 = {r["year"]: r for r in result["youth_bias_s2"]}
yall = {r["year"]: r for r in result["youth_bias_all"]}
for y in sorted(set(yoc) | set(ys2) | set(yall)):
    a = yoc.get(y, {}).get("I1_over_I6")
    b = ys2.get(y, {}).get("I1_over_I6")
    c = yall.get(y, {}).get("I1_over_I6")
    print(f"{y}  oc={a}  s2={b}  all={c}")
print("\n=== 队列固定窗口（观测完整队列 t<=2019）===")
for r in result["cohort_windows"]:
    if r["year"] <= 2019:
        print(f"{r['year']}  w01={r['w01']:>8}  w23={r['w23']:>8}  w45={r['w45']:>8}  w01/(w01+w23)={r['early_share_01_of_0_3']:.1%}")
