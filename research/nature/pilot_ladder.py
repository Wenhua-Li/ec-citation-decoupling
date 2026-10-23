# -*- coding: utf-8 -*-
"""U2 (2026-10-15): cross-corpus replication of the scope ladder on W1 panels.

Pre-registered protocol (innovation_chair.md upgrade package):
  Pairs     : OR(EJOR+ManSci, 2 sources) <-> ML(Machine Learning, 1 source),
              OR <-> evo(J Theor Biol, 1 source); both directions each.
  Records   : OpenAlex type == "article" only (non-research records excluded).
  Edge      : citing.referenced_works  ∩  cited-panel work-id set (panel-to-panel;
              cross-panel != cross-field -- declared, see assembly v1.1).
  Estimators: E1 mean panel-to-panel edges per citing paper; E2 participation;
              E3 mean share of referenced_works over papers with >=1 ref
              (per-year reference availability reported).
  Endpoints : 2013 -> 2023 (fixed before inspecting outcomes).
  Ladder    : raw pooled -> same-support (degenerate when 1 source) ->
              fixed composition (OR citing side only: Laspeyres = 2013 weights,
              Paasche = 2023 weights, aggregate ratio).
  Criterion : 2/2 pairs show E1 Laspeyres-Paasche width >= 10pp
              (EC reference value 12.8pp).  Failure => venue downgrade path.

Output: research/nature/out/pilot_ladder.json
"""
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.abspath(os.path.join(HERE, "..", "..", "archive", "packages", "w1w2", "data"))
OUT = os.path.join(HERE, "out", "pilot_ladder.json")

PANELS = {
    "OR": ["operations_research__S103321696.jsonl", "operations_research__S33323087.jsonl"],
    "ML": ["machine_learning_bull__S62148650.jsonl"],
    "evo": ["evolutionary_biology__S109682412.jsonl"],
}
SRC_NAME = {
    "operations_research__S103321696.jsonl": "EJOR",
    "operations_research__S33323087.jsonl": "ManSci",
    "machine_learning_bull__S62148650.jsonl": "ML",
    "evolutionary_biology__S109682412.jsonl": "JTB",
}

def load():
    papers = []  # (panel, src, year, nrefs, refs)
    ids = set()
    for panel, files in PANELS.items():
        for fn in files:
            path = os.path.join(DATA, fn)
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    r = json.loads(line)
                    if r.get("type") != "article":
                        continue
                    refs = r.get("referenced_works") or []
                    y = r.get("publication_year")
                    wid = r.get("id")
                    if not wid or not y:
                        continue
                    ids.add(wid)
                    papers.append({"panel": panel, "src": SRC_NAME[fn], "year": y,
                                   "wid": wid, "refs": refs})
    return papers, ids

papers, all_ids = load()
print(f"articles loaded: {len(papers)}", flush=True)
id_panel = {p["wid"]: p["panel"] for p in papers}

PAIRS = [("OR", "ML"), ("OR", "evo")]
result = {"protocol": {"type_filter": "article", "endpoints": [2013, 2023],
                       "edge": "citing.referenced_works ∩ cited-panel ids",
                       "criterion": "2/2 pairs: E1 Laspeyres-Paasche width >= 10pp",
                       "note": "cross-panel != cross-field; single-source citing panels have no composition layer (declared degeneracy)"},
         "pairs": {}}

START, END = 2013, 2023
for A, B in PAIRS:
    both = {}
    for direction, (citing, cited) in ((f"{A}->{B}", (A, B)), (f"{B}->{A}", (B, A))):
        target_ids = {p["wid"] for p in papers if p["panel"] == cited}
        per_src = defaultdict(lambda: [0, 0, 0, 0.0, 0])  # n, edges, particip, share_sum, n_with_refs
        pooled = [0, 0, 0, 0.0, 0]
        for p in papers:
            if p["panel"] != citing or not (2005 <= p["year"] <= 2024):
                continue
            e = sum(1 for r in p["refs"] if r in target_ids)
            tr = len(p["refs"])
            for agg in (per_src[p["src"]], pooled):
                agg[0] += 1
                agg[1] += e
                agg[2] += 1 if e else 0
                agg[3] += (e / tr) if tr else 0.0
                agg[4] += 1 if tr else 0
        def cells_to_series(per_src):
            out = {}
            years = sorted({p["year"] for p in papers if p["panel"] == citing})
            for y in years:
                if not (START <= y <= END):
                    continue
                c = [0, 0, 0, 0.0, 0]
                for src, cc in per_src.items():
                    pass
                out[y] = c
            return out
        # pooled series per year
        series = defaultdict(lambda: [0, 0, 0, 0.0, 0])
        src_year = defaultdict(lambda: [0, 0, 0, 0.0, 0])
        for p in papers:
            if p["panel"] != citing or not (START <= p["year"] <= END):
                continue
            e = sum(1 for r in p["refs"] if r in target_ids)
            tr = len(p["refs"])
            for agg in (series[p["year"]], src_year[(p["year"], p["src"])]):
                agg[0] += 1
                agg[1] += e
                agg[2] += 1 if e else 0
                agg[3] += (e / tr) if tr else 0.0
                agg[4] += 1 if tr else 0
        def est(c):
            return {"n": c[0], "E1": round(c[1] / c[0], 6) if c[0] else None,
                    "E2": round(c[2] / c[0], 6) if c[0] else None,
                    "E3": round(c[3] / c[4], 6) if c[4] else None,
                    "ref_avail": round(c[4] / c[0], 4) if c[0] else None}
        d = {"pooled": {str(y): est(c) for y, c in sorted(series.items())},
             "per_source": {f"{y}|{s}": est(c) for (y, s), c in sorted(src_year.items())}}
        # fixed composition (only if citing side has >=2 sources present at both endpoints)
        srcs = sorted({s for (y, s) in src_year if y in (START, END) and src_year[(y, s)][0] > 0}
                      & {s for (y, s) in src_year if y == START and src_year[(y, s)][0] > 0}
                      & {s for (y, s) in src_year if y == END and src_year[(y, s)][0] > 0})
        if len(srcs) >= 2:
            def agg_ratio(base_year, col):
                b = {s: src_year[(base_year, s)] for s in srcs if (base_year, s) in src_year and src_year[(base_year, s)][0] > 0}
                tot = sum(c[0] for c in b.values())
                w = {s: c[0] / tot for s, c in b.items()}
                def val(y):
                    return sum(w[s] * (src_year[(y, s)][col] / src_year[(y, s)][0]) for s in b if (y, s) in src_year)
                return val(END) / val(START) - 1 if val(START) else None
            d["fixed_composition"] = {
                "sources": srcs,
                "Laspeyres": {n: (round(agg_ratio(START, col), 4) if agg_ratio(START, col) is not None else None)
                              for n, col in (("E1", 1), ("E2", 2))},
            }
            # Paasche: end-year weights
            def paa_ratio(col):
                e = {s: src_year[(END, s)] for s in srcs if (END, s) in src_year and src_year[(END, s)][0] > 0}
                tot = sum(c[0] for c in e.values())
                w = {s: c[0] / tot for s, c in e.items()}
                def val(y):
                    return sum(w[s] * (src_year[(y, s)][col] / src_year[(y, s)][0]) for s in e if (y, s) in src_year)
                return val(END) / val(START) - 1 if val(START) else None
            d["fixed_composition"]["Paasche"] = {n: (round(paa_ratio(col), 4) if paa_ratio(col) is not None else None)
                                                 for n, col in (("E1", 1), ("E2", 2))}
            las = d["fixed_composition"]["Laspeyres"]["E1"]
            paa = d["fixed_composition"]["Paasche"]["E1"]
            if las is not None and paa is not None:
                d["fixed_composition"]["E1_width_pp"] = round(abs(paa - las) * 100, 2)
        else:
            d["fixed_composition"] = {"degenerate": f"citing side has {len(srcs)} source(s) at endpoints; no composition layer"}
        both[direction] = d
    result["pairs"][f"{A}<->{B}"] = both

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)

for pair, both in result["pairs"].items():
    print("=====", pair)
    for direction, d in both.items():
        ps, pe = d["pooled"].get(str(START)), d["pooled"].get(str(END))
        fc = d["fixed_composition"]
        if ps and pe:
            print(f"  {direction}: pooled E1 {ps['E1']}->{pe['E1']} ({100*(pe['E1']/ps['E1']-1):+.1f}%)  "
                  f"E2 {ps['E2']}->{pe['E2']} ({100*(pe['E2']/ps['E2']-1):+.1f}%)  ref_avail {ps['ref_avail']}->{pe['ref_avail']}")
        if "E1_width_pp" in fc:
            print(f"    fixed-comp: Laspeyres {fc['Laspeyres']['E1']:+.1%} / Paasche {fc['Paasche']['E1']:+.1%}  width {fc['E1_width_pp']}pp")
        else:
            print(f"    fixed-comp: {fc.get('degenerate', 'n/a')}")
