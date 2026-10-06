# -*- coding: utf-8 -*-
"""W3 §5 重算：多维协同判据（≥2 维同 3 年窗转折）在正负例上的区分力。

输入：research/nature/out/early_warning_table.json（w1w2 包 M4 方法的转折年）
两种口径分层计算（缺一不可，结论依赖分层）：
  A. 指标变体口径——m1_median_age 与 m1_share_ge5 各算一"维"（协议字面读法）；
  B. 独立维度口径——两 m1 变体同属"引用记忆"一维（维度=指标族；转折年取最早变体），
     独立维 = 引用记忆 / 议程自主 / 颠覆性（CD 历史面板结构性缺席）。
信号定义：任两"维"转折年相差 ≤2（同一 3 年窗）；信号年=簇内最早年；
正例命中 = 信号年 − 事件年 ∈ [−15, −1]（模糊逻辑另报产业口径 1991 敏感性）；
负例假阳性 = 无事件领域出现任一簇。
输出：research/nature/out/w3s5_coturn.json
"""
import json
import os
from itertools import combinations

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

DIM = {"m1_median_age": "memory", "m1_share_ge5": "memory", "m2_cd5": "disruption", "m3_theme_share": "agenda"}
EVENT = {"expert_systems": 1987, "symbolic_ai": 1994, "fuzzy_logic": 2000}
EVENT_INDUSTRIAL = {"fuzzy_logic": 1991}  # OQ-1 敏感性口径


def clusters(turns):
    """turns: {name: year}（None 剔除）→ 满足 |Δ|<=2 的簇列表（[(name,year)...]）。"""
    items = [(n, y) for n, y in turns.items() if y is not None]
    out = []
    for a, b in combinations(items, 2):
        if abs(a[1] - b[1]) <= 2:
            out.append([a, b])
    return out


def evaluate(turns):
    cl = clusters(turns)
    if not cl:
        return {"triggered": False, "signal_year": None, "cluster": None, "n_dims_or_metrics": len(cl)}
    best = min(cl, key=lambda c: min(y for _, y in c))
    return {"triggered": True, "signal_year": min(y for _, y in best),
            "cluster": [list(p) for p in best]}


src = json.load(open(os.path.join(OUT, "early_warning_table.json"), encoding="utf-8"))

result = {"granularity_A_indicator_variants": {}, "granularity_B_independent_dimensions": {},
          "design_note": "A 口径把 m1 两变体各算一维（协议字面）；B 口径合并为引用记忆一维（独立读法）。"
                         "A 的'改善'若主要由同维变体共转构成即为伪影，以 B 为准。"}

for granular in ("A", "B"):
    tag = f"granularity_{granular}_indicator_variants" if granular == "A" else f"granularity_{granular}_independent_dimensions"
    res = {"positives": {}, "negatives": {}}
    for case, metrics in src["cases"].items():
        turns = {m: d.get("turning_year") for m, d in metrics.items()}
        if granular == "B":
            by_dim = {}
            for m, y in turns.items():
                if y is None:
                    continue
                d = DIM[m]
                by_dim[d] = min(by_dim.get(d, 9999), y)
            turns_eval = by_dim
        else:
            turns_eval = {m: y for m, y in turns.items() if y is not None}
        ev = evaluate(turns_eval)
        if ev["triggered"]:
            ev["lead_main"] = ev["signal_year"] - EVENT[case]
            ev["hit_main"] = -15 <= ev["lead_main"] <= -1
            if case in EVENT_INDUSTRIAL:
                ev["lead_industrial"] = ev["signal_year"] - EVENT_INDUSTRIAL[case]
                ev["hit_industrial"] = -15 <= ev["lead_industrial"] <= -1
        res["positives"][case] = ev
    for case, metrics in src["negative_controls"].items():
        turns = {m: d.get("turning_year") for m, d in metrics.items()}
        if granular == "B":
            by_dim = {}
            for m, y in turns.items():
                if y is None:
                    continue
                d = DIM[m]
                by_dim[d] = min(by_dim.get(d, 9999), y)
            turns_eval = by_dim
        else:
            turns_eval = {m: y for m, y in turns.items() if y is not None}
        ev = evaluate(turns_eval)
        ev["false_positive"] = ev["triggered"]
        res["negatives"][case] = ev
    p = res["positives"]
    n_trig = sum(1 for c in p.values() if c["triggered"])
    n_hit = sum(1 for c in p.values() if c.get("hit_main"))
    n_hit_ind = sum(1 for c in p.values() if c.get("hit_industrial"))
    n_fp = sum(1 for c in res["negatives"].values() if c["false_positive"])
    res["summary"] = {
        "positives_triggered": f"{n_trig}/3",
        "hits_main_anchor": f"{n_hit}/3",
        "hits_industrial_anchor_FUZZY_only": n_hit_ind,
        "negative_fields_with_false_positive": f"{n_fp}/2",
    }
    result[tag] = res

# 自动判读：A 的触发簇是否全部/主要由同一维度变体构成
a = result["granularity_A_indicator_variants"]["positives"]
artifacts = []
for case, ev in a.items():
    if ev["triggered"]:
        dims = {DIM[n] for n, _ in ev["cluster"]}
        artifacts.append({"case": case, "same_dimension_only": len(dims) == 1, "dims": sorted(dims)})
result["artifact_check_A"] = artifacts
same_dim_only = all(x["same_dimension_only"] for x in artifacts if x["case"] != "fuzzy_logic" or True)
result["conclusion"] = {
    "A_indicator_level": "正例 3/3 触发，但仅 2/3 落入提前窗（专家系统 −5、符号 AI −10；模糊逻辑 1978 触发、−22 超窗，"
                         "仅产业口径 1991 下 −13 命中）；负例 JTB 1 次假阳性、ML 无——表面改善（假阳性 7→1）",
    "A_artifact": ("全部触发簇均由引用记忆维度的两个变体构成（同维共转）→ 改善系伪影" if same_dim_only
                   else "存在跨维触发，见 artifact_check_A"),
    "B_dimension_level": "独立维度（记忆/议程/颠覆）转折年相距 6–18 年，协同判据 0 触发（0/3 敏感度、0 假阳性）——不可判",
    "final": "正文维持 W3 §3 个体指标表述（6/9 + 负例 7 次）；多维协同判据不作为回测验证的能力主张，"
             "仅作为协议设计属性（四维共趋势依据来自 EC 主面板 W5）；历史 OA 面板可用独立维 ≤2（CD 结构性缺席、知识收支未建），判据不具评估条件",
}

with open(os.path.join(OUT, "w3s5_coturn.json"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)

for g, tag in (("A", "granularity_A_indicator_variants"), ("B", "granularity_B_independent_dimensions")):
    r = result[tag]
    print(f"=== 口径 {g} ===  positives: {r['summary']['positives_triggered']} triggered, hits {r['summary']['hits_main_anchor']}"
          f" (industrial {r['summary']['hits_industrial_anchor_FUZZY_only']}), FP fields {r['summary']['negative_fields_with_false_positive']}")
    for c, ev in r["positives"].items():
        print("  +", c, ev.get("cluster"), "lead", ev.get("lead_main"), "hit", ev.get("hit_main"),
              ("| industrial lead %s hit %s" % (ev.get("lead_industrial"), ev.get("hit_industrial"))) if "lead_industrial" in ev else "")
    for c, ev in r["negatives"].items():
        print("  -", c, "FP" if ev["false_positive"] else "clean", ev.get("cluster"))
print("artifact_check:", result["artifact_check_A"])
print("saved w3s5_coturn.json")
