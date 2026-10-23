# -*- coding: utf-8 -*-
"""De-circularisation check (2026-10-15, reframe reviews' top priority).

Within the EC corpus: does the LAGGED per-source dispersion (growth rates over
2019->2021) predict the LATER baseline-choice width (|Paasche - Laspeyres| of
E1 over 2021->2024)?  Leave-one-source-out jackknife gives 7 (dispersion,
width) points; Spearman correlation across them is the test.  Until this is
positive, the paper may only say "consistent with the covariance proposition",
not "predicts" (soft-wording rule, deepseek).

Output: research/nature/out/decirc.json
"""
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "out", "stable8_merged.json")

d = json.load(open(SRC, encoding="utf-8"))
ps = d["per_source_e1"]
srcs = sorted({k.split("|")[1] for k in ps if k.startswith("2019|")}
              & {k.split("|")[1] for k in ps if k.startswith("2021|")}
              & {k.split("|")[1] for k in ps if k.startswith("2024|")})

def get(y, s):
    return ps[f"{y}|{s}"]["E1"], ps[f"{y}|{s}"]["n_non"]

def width_and_disp(subset, lag=(2019, 2021), main=(2021, 2024)):
    # lagged dispersion: sd of per-source growth rates over the lag window
    growths = [get(lag[1], s)[0] / get(lag[0], s)[0] - 1 for s in subset]
    disp = statistics.stdev(growths) if len(growths) > 1 else None
    mixed_signs = (any(g > 0 for g in growths) and any(g < 0 for g in growths))
    # later width: |Paasche - Laspeyres| over the main window
    def agg(base):
        cells = {s: get(base, s) for s in subset}
        tot = sum(n for _, n in cells.values())
        w = {s: n / tot for s, (m, n) in cells.items()}
        num = sum(w[s] * get(main[1], s)[0] for s in subset)
        den = sum(w[s] * get(main[0], s)[0] for s in subset)
        return num / den - 1
    las, paa = agg(main[0]), agg(main[1])
    return {"disp_sd": round(disp, 4) if disp is not None else None,
            "mixed_signs_lagged": mixed_signs,
            "laspeyres": round(las, 4), "paasche": round(paa, 4),
            "width_pp": round(abs(paa - las) * 100, 2)}

full = {"subset": srcs, **width_and_disp(srcs)}
loo = []
for drop in srcs:
    sub = [s for s in srcs if s != drop]
    loo.append({"dropped": drop, **width_and_disp(sub)})

# Spearman across the 7 LOO points
def rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r

xs = [p["disp_sd"] for p in loo]
ys = [p["width_pp"] for p in loo]
rx, ry = rank(xs), rank(ys)
mx, my = statistics.mean(rx), statistics.mean(ry)
num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
spearman = round(num / den, 4) if den else None

result = {"test": "lagged dispersion (2019->2021) vs later width (2021->2024), E1, EC 7 sources",
          "full_set": full, "loo": loo, "spearman_loo": spearman,
          "soft_wording_rule": "until positive, write 'consistent with', not 'predicts'"}
with open(os.path.join(HERE, "out", "decirc.json"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)
print(json.dumps({"full": {k: full[k] for k in ("disp_sd", "mixed_signs_lagged", "laspeyres", "paasche", "width_pp")},
                  "spearman_loo": spearman,
                  "loo_points": [{"dropped": p["dropped"][:12], "disp": p["disp_sd"], "width": p["width_pp"]} for p in loo]},
                 ensure_ascii=False, indent=1))
