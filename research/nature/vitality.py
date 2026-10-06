# -*- coding: utf-8 -*-
"""W5 第一步（PLAN v3）：四维活力指标的年度相关矩阵——先验证维度间关系，再决定是否合成。

维度与主口径（全部经 W0 重算，数字引 NUMBERS.md 登记表）：
  D1 颠覆性：CD5 EC 均值（disruption.json rows[].EC.mean，队列止 2020）
  D2 知识收支：固定 8 刊源出口率（checks.json c2_fixed_venue_export[].rate，构成稳定口径）
  D3 引用记忆：新文献引用偏好比 I(1)/I(6)（memory.json youth_bias_oc，oc 主口径）
  D4 议程自主性：外部主题合计份额（terms.json 五个外部词 ec 口径之和；注意五词可能一文多计，
     作量级指标）
相关计算：Pearson（线性）与 Spearman（秩，对单调非线性稳健）；公共区间 2006-2020（D1 右删失限制）。
输出：research/nature/out/vitality.json
"""
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


def load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as f:
        return json.load(f)


disruption = load("disruption.json")
checks = load("checks.json")
memory = load("memory.json")
terms = load("terms.json")

D1 = {r["year"]: r["EC"]["mean"] for r in disruption if r.get("EC")}
D2 = {r["year"]: r["rate"] for r in checks["c2_fixed_venue_export"]}
D3 = {r["year"]: r["I1_over_I6"] for r in memory["youth_bias_oc"]}
EXT = ["deep learning", "reinforcement learning", "LLM/GPT", "transformer", "explainable AI"]
D4 = {}
for name in EXT:
    for y, v in terms["share"][name].items():
        if v.get("ec") is not None:
            D4[int(y)] = D4.get(int(y), 0.0) + v["ec"]

series = {"D1_disruption": D1, "D2_outflow": D2, "D3_youth": D3, "D4_external": D4}
years_common = sorted(set(D1) & set(D2) & set(D3) & set(D4))
years_common = [y for y in years_common if 2006 <= y <= 2020]


def pearson(x, y):
    n = len(x)
    mx, my = statistics.mean(x), statistics.mean(y)
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    vx = sum((a - mx) ** 2 for a in x) ** 0.5
    vy = sum((b - my) ** 2 for b in y) ** 0.5
    return cov / (vx * vy) if vx and vy else None


def rank_avg(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(x, y):
    return pearson(rank_avg(x), rank_avg(y))


names = list(series)
matrix = {}
for i, a in enumerate(names):
    for b in names[i:]:
        xa = [series[a][y] for y in years_common]
        xb = [series[b][y] for y in years_common]
        r = pearson(xa, xb)
        rho = spearman(xa, xb)
        matrix[f"{a}~{b}"] = {"pearson": round(r, 3) if r is not None else None,
                              "spearman": round(rho, 3) if rho is not None else None}
        if a != b:
            matrix[f"{b}~{a}"] = matrix[f"{a}~{b}"]

# 去趋势（一阶差分）相关：剔除共同趋势后，四维是否仍逐年协同
delta = {k: {y: v[y] - v[y - 1] for y in years_common[1:]} for k, v in series.items()}
years_d = years_common[1:]
dcorr = {}
for i, a in enumerate(names):
    for b in names[i:]:
        xa = [delta[a][y] for y in years_d]
        xb = [delta[b][y] for y in years_d]
        r = pearson(xa, xb)
        dcorr[f"{a}~{b}"] = {"pearson": round(r, 3) if r is not None else None}
        if a != b:
            dcorr[f"{b}~{a}"] = dcorr[f"{a}~{b}"]

out = {
    "years_common": years_common,
    "n": len(years_common),
    "series": {k: {str(y): v for y, v in sorted(d.items()) if y in years_common} for k, d in series.items()},
    "corr": matrix,
    "corr_first_difference": dcorr,
    "note": "D1 队列止 2020，公共区间 2006-2020；D4 为五词份额之和（一文可多计，量级指标）；"
            "水平相关受共同趋势影响（两个趋势序列的相关可能是伪相关），一阶差分相关用于检验"
            "去趋势后的逐年协同；相关性高不等于因果；W5 合成与否据此判定",
}
with open(os.path.join(OUT, "vitality.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

print(f"公共区间 {years_common[0]}-{years_common[-1]}，n={len(years_common)}")
print(f"{'':<18}" + "".join(f"{n:>20}" for n in names))
for a in names:
    row = f"{a:<18}"
    for b in names:
        c = matrix[f"{a}~{b}"]
        row += f"  r={c['pearson']:+.3f} ρ={c['spearman']:+.3f}"
    print(row)
print("\n一阶差分相关（去趋势，n=%d）:" % len(years_d))
for a in names:
    row = f"{a:<18}"
    for b in names:
        row += f"  Δr={dcorr[f'{a}~{b}']['pearson']:+.3f}      "
    print(row)
print("\n各维序列（公共区间）:")
for k, s in series.items():
    print(k, {y: round(s[y], 3) for y in years_common if y % 3 == 0})
