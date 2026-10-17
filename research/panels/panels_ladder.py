# -*- coding: utf-8 -*-
"""Multi-source panel ladder (2026-10-15): the decisive cross-corpus test.

Design (frozen BEFORE results, sources.json purpose field):
  Fields    : economics (5 sources), psychology (4), mathematics (4) --
             expected dispersion gradient econ > psych > math.
  Protocol  : same as pilot_ladder.py (article filter, cross-panel edges via
             referenced_works, E1/E2/E3, endpoints 2013->2023).
  Prediction: lagged per-source dispersion (growth rates 2007->2013) predicts
             the later baseline-choice width (|Paasche-Laspeyres|, 2013->2023)
             across multi-source directions, out of sample.
  Sign test : sign unanimity of per-source growth in the lag window predicts
             whether the main-window aggregate sign is reweighting-robust.

Output: research/panels/out/panels_ladder.json
"""
import json
import os
import statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "out", "panels_ladder.json")

spec = json.load(open(os.path.join(HERE, "sources.json"), encoding="utf-8"))
FIELDS = sorted({s["field"] for s in spec["sources"]})
SRC_NAME = {s["sid"]: s["journal"] for s in spec["sources"]}

papers = []
for s in spec["sources"]:
    path = os.path.join(DATA, f"{s['field']}__{s['sid']}.jsonl")
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("type") != "article" or not r.get("id") or not r.get("publication_year"):
                continue
            papers.append({"panel": s["field"], "src": s["sid"],
                           "year": r["publication_year"], "wid": r["id"],
                           "refs": r.get("referenced_works") or []})
print(f"articles: {len(papers)}", flush=True)

LAG = ((2005, 2007), (2011, 2013))
MAIN = ((2011, 2013), (2021, 2023))

def per_source_cells(citing, target_ids, y0, y1):
    """cells[s] = [n, edges, particip] over years y0..y1 (inclusive)."""
    cells = defaultdict(lambda: [0, 0, 0])
    for p in papers:
        if p["panel"] != citing or not (y0 <= p["year"] <= y1):
            continue
        e = sum(1 for r in p["refs"] if r in target_ids)
        c = cells[p["src"]]
        c[0] += 1
        c[1] += e
        c[2] += 1 if e else 0
    return cells

def direction_stats(citing, cited, lag=LAG, main=MAIN):
    target_ids = {p["wid"] for p in papers if p["panel"] == cited}
    lag_cells = per_source_cells(citing, target_ids, lag[0][0], lag[1][1])
    main_cells = per_source_cells(citing, target_ids, main[0][0], main[1][1])
    srcs = sorted({s for s, c in main_cells.items() if c[0] >= 30}
                  & {s for s, c in lag_cells.items() if c[0] >= 30})
    if len(srcs) < 2:
        return {"n_sources": len(srcs), "degenerate": True}

    def rate(cells, s):
        return cells[s][1] / cells[s][0]

    def rate_cell(cell):
        return cell[1] / cell[0]

    # lagged dispersion: sd of per-source E1 growth rates at lag endpoints
    lagA = per_source_cells(citing, target_ids, *lag[0])
    lagB = per_source_cells(citing, target_ids, *lag[1])
    growths, ok = [], []
    for s in srcs:
        a = lagA.get(s); b = lagB.get(s)
        if a and b and a[0] >= 15 and b[0] >= 15 and rate_cell(a) > 0:
            growths.append(rate_cell(b) / rate_cell(a) - 1)
            ok.append(s)
    disp_sd = statistics.stdev(growths) if len(growths) > 1 else None
    mixed = any(g > 0 for g in growths) and any(g < 0 for g in growths)
    # main window: endpoints, Laspeyres/Paasche on E1
    eA = per_source_cells(citing, target_ids, *main[0])
    eB = per_source_cells(citing, target_ids, *main[1])
    sMain = [s for s in srcs if s in eA and s in eB and eA[s][0] >= 15 and eB[s][0] >= 15]
    def agg(cellsA, cellsB, weights):
        den = sum(weights[s] * rate(cellsA, s) for s in sMain)
        num = sum(weights[s] * rate(cellsB, s) for s in sMain)
        return num / den - 1 if den else None
    wA = {s: eA[s][0] for s in sMain}; nA = sum(wA.values())
    wB = {s: eB[s][0] for s in sMain}; nB = sum(wB.values())
    las = agg(eA, eB, {s: wA[s] / nA for s in sMain})
    paa = agg(eA, eB, {s: wB[s] / nB for s in sMain})
    # pooled raw
    pooledA = [sum(eA[s][k] for s in sMain) for k in range(3)]
    pooledB = [sum(eB[s][k] for s in sMain) for k in range(3)]
    raw = (pooledB[1] / pooledB[0]) / (pooledA[1] / pooledA[0]) - 1 if pooledA[1] else None
    # main-window per-source signs
    main_signs_mixed = any(rate(eB, s) > rate(eA, s) for s in sMain) and any(rate(eB, s) < rate(eA, s) for s in sMain)
    return {"n_sources": len(sMain), "lag_disp_sd": round(disp_sd, 4) if disp_sd is not None else None,
            "lag_mixed_signs": mixed, "raw": round(raw, 4) if raw is not None else None,
            "laspeyres": round(las, 4) if las is not None else None,
            "paasche": round(paa, 4) if paa is not None else None,
            "width_pp": round(abs(paa - las) * 100, 2) if (las is not None and paa is not None) else None,
            "main_mixed_signs": main_signs_mixed,
            "per_source_main_growth": {s: round(rate(eB, s) / rate(eA, s) - 1, 4)
                                       for s in sMain if rate(eA, s) > 0}}

result = {"design": {"lag": LAG, "main": MAIN, "robustness_note": "4-year lag windows + edges>=3 variant tried 2026-10-15 and REJECTED: per-source growth dispersion is inherently fragile below ~3 edges/100 papers (1-2 edges flip signs); lag-prediction stays honestly thin, soft wording retained", "dispersion_gradient_hypothesis": "econ > psych > math"},
          "directions": {}}
pairs = [(A, B) for i, A in enumerate(FIELDS) for B in FIELDS[i + 1:]]
for A, B in pairs:
    for citing, cited in ((A, B), (B, A)):
        key = f"{citing}->{cited}"
        result["directions"][key] = direction_stats(citing, cited)
        print(key, result["directions"][key], flush=True)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)

# cross-corpus scatter: lag dispersion vs width (multi-source directions only)
pts = [{"dir": k, "disp": v["lag_disp_sd"], "width": v["width_pp"]}
       for k, v in result["directions"].items() if v.get("width_pp") is not None and v.get("lag_disp_sd") is not None]
print("\ncross-corpus points:", json.dumps(pts, ensure_ascii=False))
