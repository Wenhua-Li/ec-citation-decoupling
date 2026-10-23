# -*- coding: utf-8 -*-
"""采集前硬闸门 4：密度分层阈值功效校准（方案 v3 §5，零新数据，2026-10-18）。

问题：逐源记分卡的符号判定在泊松噪声下的错误率随"期望边数/源/窗"如何变化；
池化（E1 级档）读数同理。据此冻结三档阈值（登记 NUMBERS 后生效）。

设计：m0 ~ Pois(lam0)，m1 ~ Pois(lam0*(1+delta))；判定 sign(m1-m0) 是否等于 sign(delta)。
lam0 网格 5..600；|delta| ∈ {0.10, 0.20, 0.50}；每格 20,000 次重复；种子 20261018。
（对称性：delta<0 与 +delta 同错率，只算正向；m1<=m0 计为错，平局保守计错。）
范围声明：本校准只针对 E1 边数层的符号判定；E2/E3 是篇级均值，噪声由篇数（数百以上）主导，
不在此校准；U3 的 43.78% 漏检率标定于 EC 千篇级样本，与低密度尺度不可互推。

用法：python tier_calibration.py
输出：out/tier_calibration.json（错误率表 + 阈值读数）
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261018
NREP = 20000
LAMS = [5, 10, 15, 20, 30, 40, 50, 65, 80, 100, 130, 160, 200, 260, 320, 400, 500, 600]
DELTAS = [0.10, 0.20, 0.50]


def err_rate(lam0, delta, rng):
    """真实变化 +delta 时，观测符号判错（m1<=m0）的比率（泊松，向量化）。"""
    m0 = rng.poisson(lam0, NREP)
    m1 = rng.poisson(lam0 * (1.0 + delta), NREP)
    return float(np.mean(m1 <= m0))


def pooled_err(lam0_total, k_sources, delta, rng):
    """池化 E1 级读数：k 个源合计 lam0_total（均分）时的符号错率。"""
    per = lam0_total / k_sources
    m0 = rng.poisson(per, (NREP, k_sources)).sum(axis=1)
    m1 = rng.poisson(per * (1.0 + delta), (NREP, k_sources)).sum(axis=1)
    return float(np.mean(m1 <= m0))


def main():
    rng = np.random.default_rng(SEED)
    table = []
    for lam in LAMS:
        row = {"lam0": lam}
        for d in DELTAS:
            row[f"err_d{int(d*100)}"] = round(err_rate(lam, d, rng), 4)
        table.append(row)
        print(f"lam0={lam:5d}  " + "  ".join(f"d{int(d*100)}:err={row[f'err_d{int(d*100)}']:.3f}" for d in DELTAS), flush=True)

    pooled = []
    for total in [20, 30, 40, 50, 65, 80, 100, 130]:
        row = {"lam0_total": total, "k": 4}
        for d in (0.20, 0.50):
            row[f"err_d{int(d*100)}"] = round(pooled_err(total, 4, d, rng), 4)
        pooled.append(row)
        print(f"pooled_total={total:4d} (4 src)  d20:err={row['err_d20']:.3f}  d50:err={row['err_d50']:.3f}", flush=True)

    def first_lam(target_err, d):
        for row in table:
            if row[f"err_d{int(d*100)}"] <= target_err:
                return row["lam0"]
        return None
    readings = {
        "per_source_edges_for_10pct_sign_error_at_20pct_change": first_lam(0.10, 0.20),
        "per_source_edges_for_5pct_sign_error_at_20pct_change": first_lam(0.05, 0.20),
        "per_source_edges_for_10pct_sign_error_at_10pct_change": first_lam(0.10, 0.10),
        "per_source_edges_for_2pct_sign_error_at_50pct_change": first_lam(0.02, 0.50),
    }
    print(json.dumps(readings, ensure_ascii=False, indent=1), flush=True)

    out = {"design": {"model": "m0~Pois(lam0), m1~Pois(lam0*(1+delta)); sign error = P(m1<=m0)",
                      "nrep": NREP, "seed": SEED, "lams": LAMS, "deltas": DELTAS,
                      "scope": "E1 边数层符号判定；E2/E3 篇级估计量不在此校准（篇数主导）"},
           "per_source_table": table, "pooled_table": pooled, "readings": readings}
    path = os.path.join(HERE, "out", "tier_calibration.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved:", path)


if __name__ == "__main__":
    main()
