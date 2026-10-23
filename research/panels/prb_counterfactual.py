# -*- coding: utf-8 -*-
"""E1 实证补充：physics->materials 方向若把 PRB 分裂源记录（S4210237713）计入
共同支持聚合，pooled E1 变化会被扭曲到多少（对照剔除后的已登记 +56.2%）。

只读冻结输出 research/panels/out/fieldmap.json，不改任何采集数据。
输出冻结到 research/panels/out/prb_counterfactual.json 供 NUMBERS 登记。
用法：python research/panels/prb_counterfactual.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "out", "fieldmap.json")
OUT = os.path.join(HERE, "out", "prb_counterfactual.json")

SPLIT = "S4210237713"
DIR = "physics->materials"


def pooled(per_source, keys):
    e = sum(per_source[k]["early"]["edges"] for k in keys)
    ea = sum(per_source[k]["early"]["n_articles"] for k in keys)
    m = sum(per_source[k]["modern"]["edges"] for k in keys)
    ma = sum(per_source[k]["modern"]["n_articles"] for k in keys)
    return e, ea, m, ma, (m / ma) / (e / ea) - 1


def main():
    d = json.load(open(SRC, encoding="utf-8"))
    pm = d["directions"][DIR]
    ps = pm["per_source"]
    keys_excl = [k for k in ps if k != SPLIT]
    keys_incl = list(ps.keys())
    e0, a0, m0, ma0, rel_excl = pooled(ps, keys_excl)
    e1, a1, m1, ma1, rel_incl = pooled(ps, keys_incl)
    prb = ps[SPLIT]
    out = {
        "direction": DIR,
        "split_source": SPLIT,
        "split_source_articles": {"early": prb["early"]["n_articles"],
                                  "modern": prb["modern"]["n_articles"]},
        "split_source_edges": {"early": prb["early"]["edges"],
                               "modern": prb["modern"]["edges"]},
        "excluded": {"early_edges": e0, "early_articles": a0,
                     "modern_edges": m0, "modern_articles": ma0,
                     "pooled_e1_rel_change": round(rel_excl, 6)},
        "included": {"early_edges": e1, "early_articles": a1,
                     "modern_edges": m1, "modern_articles": ma1,
                     "pooled_e1_rel_change": round(rel_incl, 6)},
        "distortion_pp": round((rel_incl - rel_excl) * 100, 2),
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
