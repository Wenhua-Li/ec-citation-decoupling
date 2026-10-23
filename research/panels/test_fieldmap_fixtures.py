# -*- coding: utf-8 -*-
"""fieldmap.py 逻辑对拍（合成小样例，2026-10-18）。

手算基准（见各 assert 注释）构造 2 领域 × 2 源 fixture，驱动 analyze_direction，
核对 E1/E2/E3、Laspeyres/Paasche/pooled 相对变化、宽度、符号记分卡、分档逻辑。
不访问网络；fixture 写在 out/_test/ 下，跑完即删。
"""
import gzip
import json
import os
import shutil
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fieldmap  # noqa: E402

FIX = os.path.join(HERE, "out", "_test")
ROOT = os.path.join(FIX, "root")  # fieldmap.HERE 重定向根（其内含 out/ 层）


def w(i):
    return f"https://openalex.org/W{i}"


def setup():
    shutil.rmtree(FIX, ignore_errors=True)
    os.makedirs(os.path.join(ROOT, "out", "idsets"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "out", "citing"), exist_ok=True)
    # 目标集：T1..T5；X* 为非目标
    json.dump({"field": "B", "ids": [f"W{i}" for i in range(1, 6)],  # 采集侧存短 id（rsplit 后）
               "per_source": {}}, open(os.path.join(ROOT, "out", "idsets", "B.json"), "w", encoding="utf-8"))
    arts = {
        "early": {
            "SA1": [("W100", [w(1), w(11)]), ("W101", [w(2), w(11)]), ("W102", [w(11)]), ("W103", [])],
            "SA2": [("W200", [w(1)]), ("W201", [w(11), w(12)])],
        },
        "modern": {
            "SA1": [("W110", [w(1), w(2), w(11)]), ("W111", [w(3)]), ("W112", [w(4)]), ("W113", [w(5)])],
            "SA2": [("W210", [w(1), w(2)]), ("W211", [w(11)])],
        },
    }
    for wtag, per in arts.items():
        with gzip.open(os.path.join(ROOT, "out", "citing", f"A__{wtag}.jsonl.gz"), "wt", encoding="utf-8") as f:
            for sid, lst in per.items():
                for aid, refs in lst:
                    f.write(json.dumps({"sid": sid, "id": aid, "y": 2012 if wtag == "early" else 2022,
                                        "refs": refs}, ensure_ascii=False) + "\n")


def run():
    setup()
    fieldmap.HERE = ROOT  # 重定向数据根
    fieldmap.S = {"A": ["SA1", "SA2"], "B": ["SB1", "SB2"]}  # 覆盖锚源字典
    idsets = {"B": {f"W{i}" for i in range(1, 6)}}  # 与 phase A 存储一致（短 id）
    r = fieldmap.analyze_direction("A", "B", {}, idsets)
    ps = r["per_source"]
    # SA1 early: hits=[1,1,0,0] -> E1=0.5 E2=0.5 edges=2；E3=mean(1/2,1/2,0,0)=0.25
    assert ps["SA1"]["early"]["E1"] == 0.5 and ps["SA1"]["early"]["E2"] == 0.5
    assert ps["SA1"]["early"]["edges"] == 2 and abs(ps["SA1"]["early"]["E3"] - 0.25) < 1e-9
    # SA1 modern: hits=[2,1,1,1] -> E1=1.25 E2=1.0 edges=5；E3=mean(2/3,1,1,1)
    assert ps["SA1"]["modern"]["E1"] == 1.25 and ps["SA1"]["modern"]["E2"] == 1.0
    assert ps["SA1"]["modern"]["edges"] == 5 and abs(ps["SA1"]["modern"]["E3"] - (2 / 3 + 3) / 4) < 1e-6
    # SA2: early E1=0.5 edges=1；modern E1=1.0 edges=2
    assert ps["SA2"]["early"]["E1"] == 0.5 and ps["SA2"]["modern"]["E1"] == 1.0
    # 权重两窗相同（4:2）-> L=P=pooled：rel = 1.1666667/0.5 - 1 = 1.3333333
    e1 = r["aggregates"]["E1"]
    for k in ("laspeyres_rel", "paasche_rel", "pooled_rel"):
        assert abs(e1[k] - 1.3333333) < 1e-4, (k, e1[k])
    assert e1["width_pp"] == 0.0  # 两窗权重相同
    # 记分卡：SA1 +150%、SA2 +100% -> 全上
    assert r["scorecard"]["E1"]["consistent"] is True and r["scorecard"]["E1"]["direction"] == "up"
    # 分档：默认阈值 100 -> pooled(3,7) 不足 -> refused
    assert r["tier"] == "refused", r["tier"]
    # 阈值=2：SA2 early 1 < 2 -> e1_tier；阈值=1 -> full
    fieldmap.TIER_EDGES = 2
    r2 = fieldmap.analyze_direction("A", "B", {}, idsets)
    assert r2["tier"] == "e1_tier", r2["tier"]
    fieldmap.TIER_EDGES = 1
    r3 = fieldmap.analyze_direction("A", "B", {}, idsets)
    # full 档成立；但 2 源方向不触发逐源留一（len(support)>2 保护，留一后仅剩单源无意义）
    assert r3["tier"] == "full" and r3["loo_e1"] == {}
    fieldmap.TIER_EDGES = 100
    # bootstrap 可跑、分位数有序、中位数贴近真值（6 篇微样本 pos_share 天然 <1，只设下限）
    b = fieldmap.boot_pooled_rel(r["_pooled_h"]["early"], r["_pooled_h"]["modern"], 1)
    assert b["q025"] <= b["q50"] <= b["q975"] and b["pos_share"] >= 0.9 and b["n_valid"] > 0
    assert abs(b["q50"] - 1.3333) < 0.15
    g = fieldmap.boot_pair_gap(r["_pooled_h"]["early"], r["_pooled_h"]["modern"],
                               r["_pooled_h"]["early"], r["_pooled_h"]["modern"], 2)
    assert g["q025"] <= g["q50"] <= g["q975"] and abs(g["q50"]) < 1e-9  # 自身对自身 gap=0
    print("fieldmap fixture checks: ALL PASS")
    shutil.rmtree(FIX, ignore_errors=True)


if __name__ == "__main__":
    run()
