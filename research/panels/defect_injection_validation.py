# -*- coding: utf-8 -*-
"""U3 independent performance validation of the three-state comparability criteria (2026-10-15).

Why this file exists
--------------------
The archived smoke test `research/panels/defect_injection.py` (kept untouched) hand-assigned
its four expected verdicts by reading the decision rule itself, ran one seed once, and had no
independent truth source, no harmless-perturbation control, no dose-response and no
false-acceptance/false-refusal accounting (read-only audit, 2026-10-15:
research/pulse_nc20261015/implementation_audit.md). This script re-does the exercise as a real
instrument performance measurement.

Design (fixed BEFORE running; no threshold was changed anywhere)
---------------------------------------------------------------
1. Independent truth source: synthetic worlds generated from the w x K x pi generative
   citation-allocation model of U1_formalization.md section 7 -- per source s a share of the
   citing paper pool, a per-paper citation budget K_s, and a per-reference cross-domain
   propensity pi_s, here instantiated per source by its two observable margins
   (e1 = expected target edges per paper, p = probability the paper cites the target domain
   at all; edges are a hurdle: 0 with prob 1-p, else 1 + Poisson(e1/p - 1), which reproduces
   the real corpus's clustering, where e1 > p for every source). Truth labels come from the
   GENERATOR (was an injection applied? at what dose?), never from a hand-written verdict map,
   and the instrument below is a pure function of the two per-source cell tables: it cannot
   read the injection parameters or the truth registry. Population (infinite-sample) statistics
   are computed analytically alongside every cell ("oracle") so that rule blindness is separated
   from sampling noise.
2. Independent fixed seeds and repeats: every (profile, scenario, dose, replicate) triple gets
   its own deterministic seed (own random stream, no shared stream across scenarios -- audit
   finding 4). Replicates are paired across scenarios through common random numbers (the same
   base world is reused for every scenario at a given replicate index). REPS = 200 per cell.
3. Perturbation families: harmless invariance perturbations (shuffled reference order,
   consistently shifted work IDs, appended non-target references, enlarged target pool,
   within-window year relabelling, a source absent from BOTH windows); source missing end
   window / partially missing ladders on a large and a small source; reference-list loss at
   5/10/20/30/50% in two raw flavours kept separate at the record layer -- missing field
   (referenced_works = null) vs explicit empty list -- plus start-window-only and both-window
   probes; target-edge thinning ladders q = 0.9/0.7/0.5/0.3/0.1/0.05/0.01 (loss
   10/30/50/70/90/95/99%), symmetric and end-window-only.
4. Two calibration profiles: "healthy" (well-powered synthetic regime) and "tight" (mirrors the
   measured real econ->psych panel; the population margins reproduce it: E2
   1.435% -> 4.480%, ref_avail 0.8721/0.9157, avg_edges_yr(end) 31.3, max per-margin gap 3e-5),
   so the criteria are measured both away from and on top of their own thresholds.
5. Scoring protocol (declared before running): positive truth = a defect was injected at dose
   > 0; predicted positive = the instrument withholds the "COMPARABLE" claim (verdict PARTIAL
   or REFUSE). TP/FN = defect detected/missed (FN = false acceptance), TN/FP = clean world
   passed/refused (FP = false refusal). Truth "void" worlds (no cross-domain signal exists at
   all) are UNKNOWN: they are excluded from FP/FN and scored separately as correct decline vs
   void false claim. The frozen criteria have no UNKNOWN state of their own; UNKNOWN exists only
   on the truth side. All verdicts are reported as raw counts so any reader can rescore under a
   different protocol. Because the criteria are a coverage/power gate rather than a general
   distortion detector, the scorecard additionally splits defect runs by the population-level
   level distortion induced by the injection (|bias| >= 5pp vs below) and lists every cell whose
   induced bias is material yet whose flag rate is below half.
6. Nothing is silently re-judged: cells where the frozen criteria reject a benign scenario, or
   fail to reject a defective one, are recorded as measured results together with the firing
   clause ("trigger") and the population-level (oracle) verdict. The misfit list in
   scoring.material_bias_missed_cells and the dose-response blind zones are results, not
   failures to be tuned away.

Provenance of the instrument: `frozen_classify` / `frozen_cells` below are verbatim ports of
research/panels/defect_injection.py (thresholds 1%, 5 edges/yr, n>=15, 2 sources, 0.6, 0.8,
gap>10%); `archived_fidelity_check()` re-runs the four archived scenarios through this port and
compares against the archived JSON, so "criteria unchanged" is attested, not asserted.

Paths are resolved from this file's location. Output:
research/panels/out/defect_injection_validation.json (new file; the archived
defect_injection.json is only read).

Run: python research/panels/defect_injection_validation.py
"""
import json
import math
import os
import random
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "out")
OUT_PATH = os.path.join(OUT_DIR, "defect_injection_validation.json")
ARCHIVED_PATH = os.path.join(OUT_DIR, "defect_injection.json")
DATA_DIR = os.path.join(HERE, "data")
SOURCES_PATH = os.path.join(HERE, "sources.json")

SEED_BASE = 20261015
REPS = 200         # replicates per cell, healthy/tight synthetic ladders
REPS_INV = 25      # replicates for the raw-record invariance path (heavier per run)
WINDOWS = {"start": (2011, 2013), "end": (2021, 2023)}
YRS = 3            # end-window span, as in the frozen criteria

# ----------------------------------------------------------------------------------
# 1. Frozen instrument -- verbatim port (see module docstring for provenance)
# ----------------------------------------------------------------------------------
def frozen_classify(A, B):
    """Exact port of defect_injection.py::classify (thresholds unchanged)."""
    nA = sum(v[0] for v in A.values()); nB = sum(v[0] for v in B.values())
    eA = sum(v[1] for v in A.values()); eB = sum(v[1] for v in B.values())
    pA = sum(v[2] for v in A.values()); pB = sum(v[2] for v in B.values())
    rA = sum(v[3] for v in A.values()); rB = sum(v[3] for v in B.values())
    E2A, E2B = pA / nA if nA else 0, pB / nB if nB else 0
    refA, refB = rA / nA if nA else 0, rB / nB if nB else 0
    stats = {"E2": [round(E2A, 5), round(E2B, 5)], "ref_avail": [round(refA, 4), round(refB, 4)],
             "avg_edges_yr": round(eB / YRS, 1)}
    srcs_ok = {s for s in set(A) | set(B)
               if A.get(s, [0])[0] >= 15 and B.get(s, [0])[0] >= 15}
    shareA = {s: A[s][0] / nA for s in A}
    gap = sum(shareA[s] for s in A if s not in B)
    stats.update(n_sources_ok=len(srcs_ok), support_gap=round(gap, 4))
    if E2A < 0.01 or E2B < 0.01 or eB / YRS < 5 or len(srcs_ok) < 2 or min(refA, refB) < 0.6:
        return "REFUSE", stats
    if len(set(A) | set(B)) < 2 or len(srcs_ok) < len(set(A) | set(B)) or gap > 0.10 or min(refA, refB) < 0.8:
        return "PARTIAL", stats
    return "COMPARABLE", stats


def frozen_classify_traced(A, B):
    """Same decision, same order, plus the firing clause (used to explain dose-response).

    Verdict equality with frozen_classify is asserted on every run in main().
    """
    nA = sum(v[0] for v in A.values()); nB = sum(v[0] for v in B.values())
    eA = sum(v[1] for v in A.values()); eB = sum(v[1] for v in B.values())
    pA = sum(v[2] for v in A.values()); pB = sum(v[2] for v in B.values())
    rA = sum(v[3] for v in A.values()); rB = sum(v[3] for v in B.values())
    E2A, E2B = pA / nA if nA else 0, pB / nB if nB else 0
    refA, refB = rA / nA if nA else 0, rB / nB if nB else 0
    stats = {"E2": [round(E2A, 5), round(E2B, 5)], "ref_avail": [round(refA, 4), round(refB, 4)],
             "avg_edges_yr": round(eB / YRS, 1)}
    srcs_ok = {s for s in set(A) | set(B)
               if A.get(s, [0])[0] >= 15 and B.get(s, [0])[0] >= 15}
    shareA = {s: A[s][0] / nA for s in A}
    gap = sum(shareA[s] for s in A if s not in B)
    stats.update(n_sources_ok=len(srcs_ok), support_gap=round(gap, 4))
    refused, partial = [], []
    if E2A < 0.01:
        refused.append("refuse:E2_start<1%")
    if E2B < 0.01:
        refused.append("refuse:E2_end<1%")
    if eB / YRS < 5:
        refused.append("refuse:avg_edges_yr<5")
    if len(srcs_ok) < 2:
        refused.append("refuse:qualified_sources<2")
    if min(refA, refB) < 0.6:
        refused.append("refuse:ref_avail<0.6")
    if len(set(A) | set(B)) < 2:
        partial.append("partial:single_source")
    if len(srcs_ok) < len(set(A) | set(B)):
        partial.append("partial:source_unqualified(n<15)")
    if gap > 0.10:
        partial.append("partial:support_gap>10%")
    if min(refA, refB) < 0.8:
        partial.append("partial:ref_avail<0.8")
    fired = refused if refused else partial
    verdict = "REFUSE" if refused else ("PARTIAL" if partial else "COMPARABLE")
    return verdict, stats, fired


def frozen_cells(papers, citing, target_ids, window):
    """Exact port of defect_injection.py::cells (raw-record path)."""
    c = defaultdict(lambda: [0, 0, 0, 0])  # src -> [n, edges, particip, papers_with_refs]
    for p in papers:
        if p["panel"] != citing or not (window[0] <= p["year"] <= window[1]):
            continue
        e = sum(1 for r in p["refs"] if r in target_ids)
        cc = c[p["src"]]
        cc[0] += 1
        cc[1] += e
        cc[2] += 1 if e else 0
        cc[3] += 1 if p["refs"] else 0
    return c


# ----------------------------------------------------------------------------------
# 2. Generative model (w x K x pi) and calibration profiles
# ----------------------------------------------------------------------------------
# "healthy": well-powered synthetic regime (population E2 ~3.3% -> 7.1%, ref_avail .88/.92).
# "tight":   population mirror of the REAL econ->psych panel measured 2026-10-15 (per-source
#            n, E1 = edges/paper and E2 = participation share taken from that read-only probe):
#            population E2 1.435% -> 4.480% and edges/yr(end) 31.3 reproduce the real panel.
# Each source carries (e1 = expected target edges per paper, p = probability the paper cites the
# target domain at all); the per-paper edge count is a hurdle: 0 with prob 1-p, else
# 1 + Poisson(nu) with nu = e1/p - 1. This matches BOTH real margins per source (a pure Poisson
# cannot: the real edges are clustered -- e1 > p for every source).
PROFILES = {
    "healthy": {
        "note": "well-powered regime; 5 sources incl. one small source (n=20, exercises n>=15 clause)",
        "sources": [
            {"name": "big", "n": (420, 430), "e1": (0.055, 0.185), "p": (0.045, 0.095), "k": (41.0, 54.0)},
            {"name": "s2", "n": (380, 360), "e1": (0.035, 0.132), "p": (0.032, 0.070), "k": (41.0, 54.0)},
            {"name": "s3", "n": (300, 320), "e1": (0.028, 0.105), "p": (0.026, 0.058), "k": (41.0, 54.0)},
            {"name": "s4", "n": (230, 220), "e1": (0.022, 0.085), "p": (0.021, 0.046), "k": (41.0, 54.0)},
            {"name": "small", "n": (20, 20), "e1": (0.016, 0.062), "p": (0.015, 0.035), "k": (41.0, 54.0)},
        ],
        "p_empty": (0.12, 0.08),
        "calibrated_to": "design target (not real data)",
    },
    "tight": {
        "note": "population mirror of the real econ->psych panel (per-source n, E1, E2 from the "
                "2026-10-15 read-only probe); E2 1.435%/4.480%, ref_avail 0.872/0.916, "
                "avg_edges_yr(end) 31.3",
        "sources": [
            {"name": "qje", "n": (152, 137), "e1": (0.0461, 0.2190), "p": (0.0395, 0.0949), "k": (41.2, 54.2)},
            {"name": "aer", "n": (819, 320), "e1": (0.0147, 0.0781), "p": (0.0147, 0.0437), "k": (41.2, 54.2)},
            {"name": "restud", "n": (191, 282), "e1": (0.0105, 0.0496), "p": (0.0105, 0.0390), "k": (41.2, 54.2)},
            {"name": "jpe", "n": (128, 306), "e1": (0.0156, 0.0392), "p": (0.0156, 0.0392), "k": (41.2, 54.2)},
            {"name": "ecma", "n": (243, 272), "e1": (0.0, 0.0478), "p": (0.0, 0.0331), "k": (41.2, 54.2)},
        ],
        "p_empty": (0.1279, 0.0843),
        "calibrated_to": "real econ->psych panel, 2026-10-15 probe",
    },
}


def poisson(rng, lam):
    """Knuth sampler for the 1 + Poisson(nu) hurdle tail (nu is small here)."""
    if lam <= 0:
        return 0
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1


def make_world(profile, rng):
    """-> {"start": [(src_idx, k_total, k_target, raw_null_bool), ...], "end": [...]}

    p is the OBSERVED participation share (as measured on the real corpus: a paper with an
    empty/unparsed reference list cannot participate), so the conditional participation rate
    used at the non-empty papers is p/(1-p_empty); nu = e1/p - 1 keeps E[edges] = n*e1 exactly.
    """
    world = {}
    for wi, wkey in enumerate(("start", "end")):
        papers = []
        p_empty = profile["p_empty"][wi]
        for si, s in enumerate(profile["sources"]):
            km, e1, p_obs = s["k"][wi], s["e1"][wi], s["p"][wi]
            p_cond = (p_obs / (1.0 - p_empty)) if p_obs > 0 else 0.0
            nu = (e1 / p_obs - 1.0) if p_obs > 0 else 0.0
            for _ in range(s["n"][wi]):
                if rng.random() < p_empty:
                    papers.append((si, 0, 0, False))       # legitimately empty ref list
                else:
                    k = max(5, int(round(rng.gauss(km, 0.4 * km))))
                    kg = 0
                    if p_cond > 0 and rng.random() < p_cond:
                        kg = 1 + poisson(rng, nu)
                    papers.append((si, k, min(kg, k), False))
        world[wkey] = papers
    return world


def cells_from_tuples(tuples):
    c = defaultdict(lambda: [0, 0, 0, 0])
    for src, k_total, k_target, _null in tuples:
        cc = c[src]
        cc[0] += 1
        cc[1] += k_target
        cc[2] += 1 if k_target else 0
        cc[3] += 1 if k_total else 0
    return c


# ----------------------------------------------------------------------------------
# 3. Injections (tuple path) and the analytic population oracle
# ----------------------------------------------------------------------------------
def apply_injection(world, inj, rng):
    """Order: drop -> blank (null|empty) -> thin -> pi_zero. Deterministic given rng."""
    out = {}
    for wi, wkey in enumerate(("start", "end")):
        papers = world[wkey]
        drop = inj.get("drop", {})
        if drop:
            kept = []
            for p in papers:
                f = drop.get((wi, p[0]))
                if f is None:
                    kept.append(p)
                elif f < 1.0 and rng.random() >= f:
                    kept.append(p)
            papers = kept
        b = inj.get("blank_frac", (0.0, 0.0))[wi]
        if b > 0:
            null_mode = inj.get("blank_mode") == "null"
            kept = []
            for p in papers:
                if rng.random() < b:
                    kept.append((p[0], 0, 0, null_mode))
                else:
                    kept.append(p)
            papers = kept
        q = inj.get("thin_q", (1.0, 1.0))[wi]
        if q < 1.0:
            kept = []
            for p in papers:
                if p[2]:
                    kg = 0
                    for _ in range(p[2]):
                        if rng.random() < q:
                            kg += 1
                    kept.append((p[0], p[1], kg, p[3]))
                else:
                    kept.append(p)
            papers = kept
        if inj.get("pi_zero"):
            papers = [(p[0], p[1], 0, p[3]) for p in papers]
        out[wkey] = papers
    return out


def participation_after_thinning(p, nu, q):
    """P(a paper still has >=1 target edge) after keeping each target edge w.p. q.

    Hurdle: 0 with prob 1-p, else N = 1 + Poisson(nu); E[(1-q)^N] = (1-q)*exp(-nu*q).
    """
    if p <= 0 or q <= 0:
        return 0.0
    return p * (1.0 - (1.0 - q) * math.exp(-nu * q))


def population_cells(profile, inj):
    """Analytic infinite-sample per-source cells under an injection (the oracle)."""
    cols = {}
    for wi, wkey in enumerate(("start", "end")):
        b = inj.get("blank_frac", (0.0, 0.0))[wi]
        q = inj.get("thin_q", (1.0, 1.0))[wi]
        cells = {}
        for si, s in enumerate(profile["sources"]):
            f = inj.get("drop", {}).get((wi, si), 0.0)
            e1 = 0.0 if inj.get("pi_zero") else s["e1"][wi]
            p = 0.0 if inj.get("pi_zero") else s["p"][wi]
            nu = (e1 / p - 1.0) if p > 0 else 0.0
            n = s["n"][wi] * (1.0 - f)
            if n <= 0:
                continue      # a source with no papers is not a key in that window's cells
            cells[si] = [
                n,
                n * (1.0 - b) * e1 * q,
                n * (1.0 - b) * participation_after_thinning(p, nu, q),
                n * (1.0 - profile["p_empty"][wi]) * (1.0 - b),
            ]
        cols[wkey] = cells
    return cols


def population_rates(profile, inj):
    """Population E1 per window and aggregate end-window power (for harm accounting)."""
    cols = population_cells(profile, inj)
    out = {}
    for wkey in ("start", "end"):
        c = cols[wkey]
        n = sum(v[0] for v in c.values())
        e = sum(v[1] for v in c.values())
        out[wkey] = {"n": n, "edges": e, "E1": e / n if n else 0.0}
    out["growth_clean_or_injected_pct"] = (
        (out["end"]["E1"] / out["start"]["E1"] - 1.0) * 100.0 if out["start"]["E1"] else None)
    return out


# ----------------------------------------------------------------------------------
# 4. Scenario cells
# ----------------------------------------------------------------------------------
def cell(profile, family, truth, cid, inj=None, dose=None, dose_unit=None, seed_key=None,
         stem=None):
    inj = inj or {}
    return {"id": f"{profile}|{cid}", "profile": profile, "family": family, "truth": truth,
            "inj": inj, "dose": dose, "dose_unit": dose_unit, "stem": stem or cid,
            "seed_key": seed_key if seed_key is not None else cid}


def build_cells():
    cells = []
    # clean baselines + panel-level invariance (a source absent from BOTH windows leaves a
    # consistently smaller panel: comparability across windows is not damaged -> truth clean)
    cells.append(cell("healthy", "clean", "clean", "clean_baseline"))
    cells.append(cell("tight", "clean", "clean", "clean_baseline"))
    cells.append(cell("healthy", "clean", "clean", "source_absent_both_windows",
                      inj={"drop": {(0, 0): 1.0, (1, 0): 1.0}}))
    cells.append(cell("tight", "clean", "clean", "source_absent_both_windows",
                      inj={"drop": {(0, 0): 1.0, (1, 0): 1.0}}))
    # symmetric partial source loss in BOTH windows: composition weight shifts, both windows
    # lose exactly the same papers -> cross-window comparability is preserved -> truth clean
    cells.append(cell("healthy", "clean", "clean", "source_partial_symmetric_30p_both",
                      inj={"drop": {(0, 0): 0.30, (1, 0): 0.30}}))
    # single-source citing panel: the U1 doc lists "single-source citing side -> PARTIAL", the
    # code evaluates len(srcs_ok)<2 (REFUSE) first -- probe which branch is reachable
    cells.append(cell("healthy", "source_loss", "defect", "single_source_panel",
                      inj={"drop": {(0, 1): 1.0, (0, 2): 1.0, (0, 3): 1.0, (0, 4): 1.0,
                                    (1, 1): 1.0, (1, 2): 1.0, (1, 3): 1.0, (1, 4): 1.0}},
                      dose=None, dose_unit="leaves 1 of 5 sources in both windows"))
    # void world: no cross-domain signal exists at all -> truth UNKNOWN (excluded from FP/FN)
    cells.append(cell("healthy", "void", "void", "void_no_cross_signal", inj={"pi_zero": True}))
    # reference-list loss ladders (missing field vs empty list, paired mirrors: same seed_key)
    for d in (5, 10, 20, 30, 50):
        for mode, tag in (("null", "refs_missing_field"), ("empty", "refs_empty_list")):
            cells.append(cell("healthy", "ref_loss", "defect", f"{tag}_{d}p_end",
                              inj={"blank_frac": (0.0, d / 100.0), "blank_mode": mode},
                              dose=d, dose_unit="% of end-window citing papers",
                              seed_key=f"ref_loss_{d}", stem=tag))
        cells.append(cell("tight", "ref_loss", "defect", f"refs_missing_field_{d}p_end",
                          inj={"blank_frac": (0.0, d / 100.0), "blank_mode": "null"},
                          dose=d, dose_unit="% of end-window citing papers",
                          seed_key=f"ref_loss_{d}", stem="refs_missing_field"))
    cells.append(cell("healthy", "ref_loss", "defect", "refs_missing_field_30p_start_only",
                      inj={"blank_frac": (0.30, 0.0), "blank_mode": "null"}, dose=30,
                      dose_unit="% of start-window citing papers", seed_key="ref_loss_30_start",
                      stem="refs_missing_field_start_only"))
    cells.append(cell("healthy", "ref_loss", "defect", "refs_missing_field_30p_both",
                      inj={"blank_frac": (0.30, 0.30), "blank_mode": "null"}, dose=30,
                      dose_unit="% of citing papers, both windows", seed_key="ref_loss_30_both",
                      stem="refs_missing_field_both_windows"))
    # source loss ladders (large source = index 0, small source = index 4)
    for d in (5, 10, 20, 30, 50, 100):
        cells.append(cell("healthy", "source_loss", "defect", f"source_partial_big_{d}p_end",
                          inj={"drop": {(1, 0): d / 100.0}}, dose=d,
                          dose_unit="% of large source's end-window papers",
                          seed_key=f"src_big_{d}", stem="source_partial_big"))
        cells.append(cell("healthy", "source_loss", "defect", f"source_partial_small_{d}p_end",
                          inj={"drop": {(1, 4): d / 100.0}}, dose=d,
                          dose_unit="% of small source's end-window papers",
                          seed_key=f"src_small_{d}", stem="source_partial_small"))
    cells.append(cell("tight", "source_loss", "defect", "source_missing_end_big",
                      inj={"drop": {(1, 0): 1.0}}, dose=100,
                      dose_unit="% of large source's end-window papers", seed_key="src_big_100",
                      stem="source_partial_big"))
    # target-edge thinning ladders (loss = 1 - q); symmetric and end-window-only
    for loss in (10, 30, 50, 70, 90, 95, 99):
        q = 1.0 - loss / 100.0
        cells.append(cell("healthy", "edge_loss", "defect", f"edge_thinning_loss_{loss}p",
                          inj={"thin_q": (q, q)}, dose=loss, dose_unit="% of target edges removed",
                          seed_key=f"thin_{loss}", stem="edge_thinning"))
        cells.append(cell("tight", "edge_loss", "defect", f"edge_thinning_loss_{loss}p",
                          inj={"thin_q": (q, q)}, dose=loss, dose_unit="% of target edges removed",
                          seed_key=f"thin_{loss}", stem="edge_thinning"))
    for loss in (50, 90, 99):
        q = 1.0 - loss / 100.0
        cells.append(cell("healthy", "edge_loss", "defect", f"edge_thinning_end_only_loss_{loss}p",
                          inj={"thin_q": (1.0, q)}, dose=loss,
                          dose_unit="% of end-window target edges removed",
                          seed_key=f"thin_end_{loss}", stem="edge_thinning_end_only"))
    return cells


INVARIANCE = [
    ("identity", "none (baseline)"),
    ("refs_shuffled", "reference order shuffled within every paper"),
    ("ids_shifted", "all work IDs shifted by a constant (consistent bijection)"),
    ("nontarget_refs_appended", "3 distinct non-target references appended to every paper with refs"),
    ("target_pool_extended", "500 never-cited works added to the cited-side pool"),
    ("year_relabel_within_window", "publication years permuted within each window"),
]


# ----------------------------------------------------------------------------------
# 5. Raw-record path (invariance + missing-field vs empty-list separability at source)
# ----------------------------------------------------------------------------------
def world_to_records(world, rng):
    """Rebuild raw records (production shape) from tuple papers, for the frozen raw cells()."""
    recs = []
    for wkey in ("start", "end"):
        y0 = WINDOWS[wkey][0]
        for i, (src, k_total, k_target, null) in enumerate(world[wkey]):
            if null:
                refs = None                      # missing field
            elif k_total == 0:
                refs = []                        # explicit empty list
            else:
                refs = list(rng.sample(range(0, 2000), k_target)) if k_target else []
                refs += list(rng.sample(range(100000, 105000), k_total - k_target))
            recs.append({"panel": "citing", "src": f"S{src}", "year": y0 + i % YRS,
                         "wid": 900000 + len(recs), "refs": refs, "window": wkey})
    return recs


def copy_records(recs):
    return [dict(r, refs=(None if r["refs"] is None else list(r["refs"]))) for r in recs]


def pert_identity(recs, target_ids, rng):
    return recs, target_ids


def pert_refs_shuffled(recs, target_ids, rng):
    for r in recs:
        if r["refs"]:
            rng.shuffle(r["refs"])
    return recs, target_ids


def pert_ids_shifted(recs, target_ids, rng):
    shift = 7_000_000
    for r in recs:
        r["wid"] += shift
        if r["refs"]:
            r["refs"] = [x + shift for x in r["refs"]]
    return recs, {t + shift for t in target_ids}


def pert_nontarget_refs_appended(recs, target_ids, rng):
    for r in recs:
        if r["refs"]:
            r["refs"] = r["refs"] + rng.sample(range(200000, 205000), 3)
    return recs, target_ids


def pert_target_pool_extended(recs, target_ids, rng):
    return recs, set(target_ids) | set(range(2_500_000, 2_500_500))


def pert_year_relabel_within_window(recs, target_ids, rng):
    for wkey in ("start", "end"):
        idx = [i for i, r in enumerate(recs) if r["window"] == wkey]
        yrs = [recs[i]["year"] for i in idx]
        rng.shuffle(yrs)
        for i, y in zip(idx, yrs):
            recs[i]["year"] = y
    return recs, target_ids


PERTURBATIONS = {"identity": pert_identity, "refs_shuffled": pert_refs_shuffled,
                 "ids_shifted": pert_ids_shifted,
                 "nontarget_refs_appended": pert_nontarget_refs_appended,
                 "target_pool_extended": pert_target_pool_extended,
                 "year_relabel_within_window": pert_year_relabel_within_window}


def cells_equal(A, B):
    keys = set(A) | set(B)
    return all(list(A.get(k, [0, 0, 0, 0])) == list(B.get(k, [0, 0, 0, 0])) for k in keys)


def raw_path_invariance(base_worlds):
    """Harmless perturbations through the full raw pipeline (frozen cells()); the claim is
    exact invariance of the four per-source statistics, checked replicate by replicate."""
    report = {k: {"desc": d, "runs": 0, "exact_matches": 0, "mismatch_sources": [],
                  "verdict_identical": True} for k, d in INVARIANCE}
    null_vs_empty = {"frac": 0.30, "runs": 0, "cells_identical": 0, "null_counts": [],
                     "empty_counts": [], "verdicts": {"empty": None, "null": None},
                     "note": ("missing field (referenced_works -> None) vs explicit empty list, "
                              "paired on the same seed; raw provenance is separable at the record "
                              "layer, the frozen statistics are not")}
    for rep in range(REPS_INV):
        rng_world = random.Random(SEED_BASE + 300007 * rep)
        world = base_worlds["healthy"][rep]
        recs = world_to_records(world, rng_world)
        target_ids = set(range(0, 2000))
        baseA = frozen_cells(recs, "citing", target_ids, WINDOWS["start"])
        baseB = frozen_cells(recs, "citing", target_ids, WINDOWS["end"])
        base_v = frozen_classify(baseA, baseB)[0]
        for name, _desc in INVARIANCE:
            rng = random.Random(SEED_BASE + 600011 * rep + 7919 * (hash_stable(name) % 100000))
            work, tids = PERTURBATIONS[name](copy_records(recs), set(target_ids), rng)
            A = frozen_cells(work, "citing", tids, WINDOWS["start"])
            B = frozen_cells(work, "citing", tids, WINDOWS["end"])
            ok = cells_equal(A, baseA) and cells_equal(B, baseB)
            r = report[name]
            r["runs"] += 1
            if ok:
                r["exact_matches"] += 1
            else:
                r["mismatch_sources"].append([rep, sorted(set(A) | set(B))])
            if frozen_classify(A, B)[0] != base_v:
                r["verdict_identical"] = False
        # missing-field vs empty-list: same seed -> same papers affected, different raw provenance
        pair_cells = {}
        for mode in ("empty", "null"):
            rng = random.Random(SEED_BASE + 900001 * rep)
            work = copy_records(recs)
            for r in work:
                if r["window"] == "end" and rng.random() < null_vs_empty["frac"]:
                    r["refs"] = [] if mode == "empty" else None
            nulls = sum(1 for r in work if r["refs"] is None)
            empties = sum(1 for r in work if r["refs"] == [])
            if mode == "empty":
                null_vs_empty["empty_counts"].append(empties)
            else:
                null_vs_empty["null_counts"].append(nulls)
            folded = [dict(r, refs=(r["refs"] or [])) for r in work]   # production fold
            A = frozen_cells(folded, "citing", target_ids, WINDOWS["start"])
            B = frozen_cells(folded, "citing", target_ids, WINDOWS["end"])
            null_vs_empty["verdicts"][mode] = frozen_classify(A, B)[0]
            pair_cells[mode] = (A, B)
        if cells_equal(pair_cells["empty"][1], pair_cells["null"][1]) and \
                cells_equal(pair_cells["empty"][0], pair_cells["null"][0]):
            null_vs_empty["cells_identical"] += 1
        null_vs_empty["runs"] += 1
    return report, null_vs_empty


def hash_stable(s):
    h = 0
    for ch in s:
        h = (h * 131 + ord(ch)) % 1000003
    return h


# ----------------------------------------------------------------------------------
# 6. Real-data anchor + archived-criteria fidelity
# ----------------------------------------------------------------------------------
def load_real_papers():
    if not (os.path.exists(SOURCES_PATH) and os.path.isdir(DATA_DIR)):
        return None, None
    spec = json.load(open(SOURCES_PATH, encoding="utf-8"))
    papers = []
    for s in spec["sources"]:
        path = os.path.join(DATA_DIR, f"{s['field']}__{s['sid']}.jsonl")
        if not os.path.exists(path):
            return None, None
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if r.get("type") != "article" or not r.get("id") or not r.get("publication_year"):
                    continue
                papers.append({"panel": s["field"], "src": s["sid"], "year": r["publication_year"],
                               "wid": r["id"], "refs": r.get("referenced_works") or []})
    return papers, spec


def real_anchor(papers):
    psych_ids = {p["wid"] for p in papers if p["panel"] == "psychology"}
    A = frozen_cells(papers, "economics", psych_ids, WINDOWS["start"])
    B = frozen_cells(papers, "economics", psych_ids, WINDOWS["end"])
    verdict, stats, fired = frozen_classify_traced(A, B)
    per_src = {}
    for tag, c in (("start", A), ("end", B)):
        per_src[tag] = {s: {"n": c[s][0], "edges": c[s][1], "particip": c[s][2],
                            "ref_avail": round(c[s][3] / c[s][0], 4) if c[s][0] else None}
                        for s in sorted(c)}
    return {"truth": "clean (no injection; real corpus)", "verdict": verdict, "fired": fired,
            "stats": stats, "per_source": per_src,
            "note": "anchor only -- this is the corpus the criteria were built on; it is not evidence"}


def archived_fidelity_check(papers):
    """Re-run the four archived scenarios verbatim through this port and diff the archived JSON."""
    if papers is None or not os.path.exists(ARCHIVED_PATH):
        return {"available": False}
    psych_ids = {p["wid"] for p in papers if p["panel"] == "psychology"}
    MAIN = (WINDOWS["start"], WINDOWS["end"])
    out = {}

    def run(cellsA, cellsB):
        v, st = frozen_classify(cellsA, cellsB)
        return {"verdict": v, "stats": st}

    out["clean"] = run(frozen_cells(papers, "economics", psych_ids, MAIN[0]),
                       frozen_cells(papers, "economics", psych_ids, MAIN[1]))
    masked = [p for p in papers if not (p["panel"] == "economics" and p["src"] == "S203860005"
                                        and p["year"] >= MAIN[1][0])]
    out["source_masked"] = run(frozen_cells(masked, "economics", psych_ids, MAIN[0]),
                               frozen_cells(masked, "economics", psych_ids, MAIN[1]))
    rng = random.Random(20261015)
    blanked = []
    for p in papers:
        q = dict(p)
        if q["panel"] == "economics" and q["year"] >= MAIN[1][0] and rng.random() < 0.30:
            q["refs"] = []
        blanked.append(q)
    out["refs_missing_30p"] = run(frozen_cells(blanked, "economics", psych_ids, MAIN[0]),
                                  frozen_cells(blanked, "economics", psych_ids, MAIN[1]))
    dec = []
    for p in papers:
        q = dict(p)
        if q["panel"] == "economics":
            q["refs"] = [r for r in q["refs"] if (r not in psych_ids) or rng.random() < 0.1]
        dec.append(q)
    out["edges_decimated"] = run(frozen_cells(dec, "economics", psych_ids, MAIN[0]),
                                 frozen_cells(dec, "economics", psych_ids, MAIN[1]))
    archived = json.load(open(ARCHIVED_PATH, encoding="utf-8"))
    diff = {}
    for k in out:
        a = archived["detail"][k]
        same_v = a["verdict"] == out[k]["verdict"]
        same_s = all(a["stats"].get(m) == out[k]["stats"].get(m) for m in a["stats"])
        diff[k] = {"archived_verdict": a["verdict"], "reproduced_verdict": out[k]["verdict"],
                   "verdict_match": same_v, "stats_match": same_s}
    return {"available": True, "source": "research/panels/out/defect_injection.json (read-only)",
            "reproduced": out, "diff": diff, "all_match": all(d["verdict_match"] and d["stats_match"]
                                                             for d in diff.values())}


# ----------------------------------------------------------------------------------
# 7. Runner + scoring
# ----------------------------------------------------------------------------------
def run_cells(cells, base_worlds):
    runs, cell_records = [], {}
    for spec in cells:
        cnt = Counter()
        triggers = Counter()
        stats_acc = defaultdict(list)
        oracleA, oracleB = None, None
        for rep in range(REPS):
            rng = random.Random(SEED_BASE + 7919 * rep + 104729 * hash_stable(f"{spec['profile']}|{spec['seed_key']}"))
            world = apply_injection(base_worlds[spec["profile"]][rep], spec["inj"], rng)
            A = cells_from_tuples(world["start"])
            B = cells_from_tuples(world["end"])
            v1 = frozen_classify(A, B)[0]
            verdict, stats, fired = frozen_classify_traced(A, B)
            assert v1 == verdict, "traced classifier diverged from frozen classifier"
            cnt[verdict] += 1
            for f in fired:
                triggers[f] += 1
            stats_acc["E2_start"].append(stats["E2"][0])
            stats_acc["E2_end"].append(stats["E2"][1])
            stats_acc["ref_avail_start"].append(stats["ref_avail"][0])
            stats_acc["ref_avail_end"].append(stats["ref_avail"][1])
            stats_acc["avg_edges_yr"].append(stats["avg_edges_yr"])
            stats_acc["n_sources_ok"].append(stats["n_sources_ok"])
            runs.append({"cell": spec["id"], "family": spec["family"], "profile": spec["profile"],
                         "truth": spec["truth"], "dose": spec["dose"], "verdict": verdict})
        pc = population_cells(PROFILES[spec["profile"]], spec["inj"])
        oracleA = {s: v for s, v in pc["start"].items()}
        oracleB = {s: v for s, v in pc["end"].items()}
        ov, ostats, ofired = frozen_classify_traced(oracleA, oracleB)
        clean_rates = population_rates(PROFILES[spec["profile"]], {})
        inj_rates = population_rates(PROFILES[spec["profile"]], spec["inj"])
        bias = None
        if clean_rates["growth_clean_or_injected_pct"] is not None and \
                inj_rates["growth_clean_or_injected_pct"] is not None:
            bias = inj_rates["growth_clean_or_injected_pct"] - clean_rates["growth_clean_or_injected_pct"]
        cell_records[spec["id"]] = {
            "profile": spec["profile"], "family": spec["family"], "truth": spec["truth"],
            "dose": spec["dose"], "dose_unit": spec["dose_unit"],
            "injection": render_inj(spec["inj"]), "reps": REPS,
            "verdicts": {k: cnt.get(k, 0) for k in ("COMPARABLE", "PARTIAL", "REFUSE")},
            "flag_rate": round((REPS - cnt.get("COMPARABLE", 0)) / REPS, 4),
            "triggers": dict(triggers),
            "sample_median": {k: (q(v, 0.5) if k == "n_sources_ok" else round(q(v, 0.5), 4))
                              for k, v in stats_acc.items()},
            "oracle": {"verdict": ov, "fired": ofired, "stats": ostats},
            "population": {"growth_pct": (round(inj_rates["growth_clean_or_injected_pct"], 3)
                                          if inj_rates["growth_clean_or_injected_pct"] is not None else None),
                           "clean_growth_pct": (round(clean_rates["growth_clean_or_injected_pct"], 3)
                                                if clean_rates["growth_clean_or_injected_pct"] is not None else None),
                           "induced_bias_pp": round(bias, 3) if bias is not None else None,
                           "edges_end": round(inj_rates["end"]["edges"], 1),
                           "ref_avail_end": round(sum(v[3] for v in oracleB.values()) /
                                                  sum(v[0] for v in oracleB.values()), 4)
                           if sum(v[0] for v in oracleB.values()) else None,
                           "E2_end": round(sum(v[2] for v in oracleB.values()) /
                                           sum(v[0] for v in oracleB.values()), 5)
                           if sum(v[0] for v in oracleB.values()) else None},
        }
    return runs, cell_records


def render_inj(inj):
    parts = []
    if inj.get("blank_frac", (0.0, 0.0)) != (0.0, 0.0):
        parts.append("blank_refs(start=%.2f,end=%.2f,mode=%s)" % (inj["blank_frac"][0],
                                                                  inj["blank_frac"][1],
                                                                  inj.get("blank_mode", "empty")))
    if inj.get("thin_q", (1.0, 1.0)) != (1.0, 1.0):
        parts.append("thin_target_edges(q_start=%.2f,q_end=%.2f)" % inj["thin_q"])
    for (wi, s), f in sorted(inj.get("drop", {}).items()):
        parts.append("drop_source(src=%d,window=%s,frac=%.2f)" % (s, "start" if wi == 0 else "end", f))
    if inj.get("pi_zero"):
        parts.append("pi_zero(all sources)")
    return "; ".join(parts) if parts else "none"


def q(xs, p):
    if not xs:
        return None
    ys = sorted(xs)
    i = min(len(ys) - 1, max(0, int(round(p * (len(ys) - 1)))))
    return ys[i]


def score(runs, cell_records=None):
    def blank():
        return {"TP": 0, "TN": 0, "FP": 0, "FN": 0, "UNKNOWN_truth_void": 0,
                "void_correct_decline": 0, "void_false_claim": 0}
    total = blank()
    by_family, by_profile, by_family_profile = {}, {}, {}
    by_bias_class = {}
    matrix = {t: {v: 0 for v in ("COMPARABLE", "PARTIAL", "REFUSE")}
              for t in ("clean", "defect", "void")}
    cell_records = cell_records or {}

    def bias_class(cid):
        b = (cell_records.get(cid) or {}).get("population", {}).get("induced_bias_pp")
        if b is None:
            return "bias:unknown"
        return "bias:material(|pp|>=5)" if abs(b) >= 5 else "bias:minor(|pp|<5)"

    for r in runs:
        flagged = r["verdict"] != "COMPARABLE"
        matrix[r["truth"]][r["verdict"]] += 1
        buckets = [total,
                   by_family.setdefault(r["family"], blank()),
                   by_profile.setdefault(r["profile"], blank()),
                   by_family_profile.setdefault(f"{r['profile']}/{r['family']}", blank())]
        if r["truth"] == "defect":
            buckets.append(by_bias_class.setdefault(bias_class(r["cell"]), blank()))
        for bucket in buckets:
            if r["truth"] == "defect":
                bucket["TP" if flagged else "FN"] += 1
            elif r["truth"] == "clean":
                bucket["FP" if flagged else "TN"] += 1
            else:
                bucket["UNKNOWN_truth_void"] += 1
                if flagged:
                    bucket["void_correct_decline"] += 1
                else:
                    bucket["void_false_claim"] += 1

    def rates(b):
        pos = b["TP"] + b["FN"]; neg = b["TN"] + b["FP"]
        return {"detection_rate(TPR)": round(b["TP"] / pos, 4) if pos else None,
                "false_acceptance_rate(FNR)": round(b["FN"] / pos, 4) if pos else None,
                "specificity(TNR)": round(b["TN"] / neg, 4) if neg else None,
                "false_refusal_rate(FPR)": round(b["FP"] / neg, 4) if neg else None,
                "n_defect_runs": pos, "n_clean_runs": neg}

    material_missed = []
    for cid, rec in cell_records.items():
        if rec["truth"] != "defect":
            continue
        b = rec["population"]["induced_bias_pp"]
        if b is not None and abs(b) >= 5.0 and rec["flag_rate"] < 0.5:
            material_missed.append({"cell": cid, "induced_bias_pp": b, "flag_rate": rec["flag_rate"],
                                    "verdicts": rec["verdicts"], "oracle_verdict": rec["oracle"]["verdict"],
                                    "oracle_fired": rec["oracle"]["fired"],
                                    "population_edges_end": rec["population"]["edges_end"]})
    material_missed.sort(key=lambda x: -abs(x["induced_bias_pp"]))
    return {"protocol": ("positive truth = defect injected (dose>0); predicted positive = "
                         "instrument withholds COMPARABLE (PARTIAL or REFUSE); FN = false "
                         "acceptance, FP = false refusal; truth 'void' worlds are UNKNOWN and "
                         "excluded from FP/FN. 'bias' classes condition on the population-level "
                         "level distortion induced by the injection (see cells.*.population): "
                         "the criteria are a coverage/power gate, so cells whose induced bias is "
                         "material but whose coverage margins survive are the informative misses."),
            "confusion_all": total, "rates_all": rates(total), "truth_x_verdict": matrix,
            "by_family": by_family, "rates_by_family": {k: rates(v) for k, v in by_family.items()},
            "by_profile": by_profile, "rates_by_profile": {k: rates(v) for k, v in by_profile.items()},
            "by_bias_class": {k: rates(v) for k, v in by_bias_class.items()},
            "material_bias_missed_cells": material_missed}


def dose_response(cell_records, cell_stems):
    ladders = {}
    for cid, rec in cell_records.items():
        if rec["dose"] is None:
            continue
        key = f"{rec['profile']}/{rec['family']}/{cell_stems[cid]}"
        ladders.setdefault(key, []).append(rec)
    out = {}
    for key, recs in ladders.items():
        recs = sorted(recs, key=lambda r: r["dose"])
        doses = [r["dose"] for r in recs]
        flags = [r["flag_rate"] for r in recs]
        profile = recs[0]["profile"]
        clean = cell_records.get(f"{profile}|clean_baseline", {})
        out[key] = {
            "unit": recs[0]["dose_unit"],
            "clean_baseline_flag_rate": clean.get("flag_rate"),
            "clean_baseline_verdicts": clean.get("verdicts"),
            "dose": doses,
            "flag_rate": flags,
            "verdict_dist": [r["verdicts"] for r in recs],
            "oracle_verdict": [r["oracle"]["verdict"] for r in recs],
            "oracle_fired": [r["oracle"]["fired"] for r in recs],
            "sample_oracle_agreement": round(sum(
                1 for r in recs if ((r["flag_rate"] >= 0.5) == (r["oracle"]["verdict"] != "COMPARABLE"))
            ) / len(recs), 3),
            "median_E2_end": [r["sample_median"]["E2_end"] for r in recs],
            "median_ref_avail_end": [r["sample_median"]["ref_avail_end"] for r in recs],
            "median_avg_edges_yr": [r["sample_median"]["avg_edges_yr"] for r in recs],
            "induced_bias_pp": [r["population"]["induced_bias_pp"] for r in recs],
            "population_edges_end": [r["population"]["edges_end"] for r in recs],
            "first_flagged_dose": next((d for d, f in zip(doses, flags) if f >= 0.5), None),
            "blind_zone_upto_dose": max([d for d, f in zip(doses, flags) if f == 0.0], default=None),
        }
    return out


# ----------------------------------------------------------------------------------
# 8. Main
# ----------------------------------------------------------------------------------
def main():
    t0 = time.time()
    result = {"meta": {
        "title": "U3 independent performance validation of the three-state comparability criteria",
        "date": "2026-10-15",
        "instrument": "verbatim port of research/panels/defect_injection.py (frozen thresholds; "
                      "the archived file is read-only here and this script writes a NEW output)",
        "truth_source": "synthetic w x K x pi generative worlds (U1_formalization.md section 7); "
                        "truth labels come from the generator, never from the instrument",
        "seeds": {"base": SEED_BASE, "reps": REPS, "reps_invariance_raw_path": REPS_INV,
                  "scheme": "cell seed = base + 7919*rep + 104729*hash_stable(profile|seed_key); "
                            "base worlds = base + 100003*rep (healthy) / +1000003 (tight); "
                            "paired common random numbers across scenarios"},
        "scoring_protocol": "see scoring.protocol",
        "output": "research/panels/out/defect_injection_validation.json",
    }}

    base_worlds = {}
    for pname, profile in PROFILES.items():
        off = 100003 if pname == "healthy" else 1000003
        base_worlds[pname] = [make_world(profile, random.Random(SEED_BASE + off * rep))
                              for rep in range(REPS)]
    result["dgp"] = {
        "profiles": {p: {"note": v["note"], "calibrated_to": v["calibrated_to"],
                         "sources": v["sources"], "p_empty": v["p_empty"]}
                     for p, v in PROFILES.items()},
        "population_baseline": {},
    }
    for pname, profile in PROFILES.items():
        pc = population_cells(profile, {})
        ov, ostats, ofired = frozen_classify_traced({s: c for s, c in pc["start"].items()},
                                                    {s: c for s, c in pc["end"].items()})
        result["dgp"]["population_baseline"][pname] = {
            "rates": population_rates(profile, {}), "oracle_verdict": ov,
            "oracle_fired": ofired, "oracle_stats": ostats}

    cells = build_cells()
    runs, cell_records = run_cells(cells, base_worlds)
    cell_stems = {c["id"]: c["stem"] for c in cells}
    result["cells"] = cell_records
    result["scoring"] = score(runs, cell_records)
    result["dose_response"] = dose_response(cell_records, cell_stems)

    # mirror check: missing field vs empty list must be statistic-for-statistic identical
    mirror = {}
    for d in (5, 10, 20, 30, 50):
        a = cell_records.get(f"healthy|refs_missing_field_{d}p_end")
        b = cell_records.get(f"healthy|refs_empty_list_{d}p_end")
        mirror[f"{d}p"] = {"identical_verdicts": a["verdicts"] == b["verdicts"],
                           "identical_medians": a["sample_median"] == b["sample_median"],
                           "note": "paired mirror (same seed): the frozen statistics have no "
                                   "channel separating a missing field from an empty list"}
    result["missing_field_vs_empty_list"] = mirror

    inv_report, null_vs_empty = raw_path_invariance(base_worlds)
    result["invariance"] = {"raw_pipeline": inv_report,
                            "all_exact": all(v["exact_matches"] == v["runs"] for v in inv_report.values()),
                            "all_verdicts_identical": all(v["verdict_identical"] for v in inv_report.values()),
                            "null_vs_empty_raw_path": null_vs_empty}

    papers, _spec = load_real_papers()
    result["real_anchor"] = real_anchor(papers) if papers else {"available": False}
    result["archived_fidelity"] = archived_fidelity_check(papers)

    # calibration check: does the tight population mirror reproduce the real panel margins?
    tight_pop = result["dgp"]["population_baseline"]["tight"]["oracle_stats"]
    if result["real_anchor"].get("stats"):
        real = result["real_anchor"]["stats"]
        result["calibration_check"] = {
            "note": "population (infinite-sample) margins of the tight synthetic profile vs the "
                    "measured real econ->psych panel under the same windows",
            "E2_real_vs_tight": {"real": real["E2"], "tight_population": tight_pop["E2"]},
            "ref_avail_real_vs_tight": {"real": real["ref_avail"], "tight_population": tight_pop["ref_avail"]},
            "avg_edges_yr_real_vs_tight": {"real": real["avg_edges_yr"], "tight_population": tight_pop["avg_edges_yr"]},
            "max_abs_gap": max(abs(a - b) for a, b in zip(real["E2"] + real["ref_avail"],
                                                          tight_pop["E2"] + tight_pop["ref_avail"])),
        }
    # two structural probes worth naming explicitly (both are measured results, no rule touched)
    ssp = cell_records["healthy|single_source_panel"]
    both = cell_records["healthy|source_absent_both_windows"]
    result["probes"] = {
        "single_source_panel": {
            "cell": "healthy|single_source_panel", "verdicts": ssp["verdicts"],
            "trigger": ssp["triggers"],
            "note": ("U1_formalization.md section 4 documents 'single-source citing side -> "
                     "PARTIAL'; in the frozen order the REFUSE clause qualified_sources<2 is "
                     "evaluated first, so the PARTIAL single-source branch is shadowed. Recorded "
                     "as measured (audit finding 2 confirmed); no threshold was modified."),
        },
        "source_absent_both_windows": {
            "cell": "healthy|source_absent_both_windows", "verdicts": both["verdicts"],
            "note": ("a source silently absent from BOTH windows leaves a consistently smaller "
                     "panel; cross-window comparability is unaffected (no support gap), so a "
                     "COMPARABLE verdict here is correct and panel-completeness is outside the "
                     "criteria's contract."),
        },
    }
    result["limits"] = [
        "Synthetic DGP calibrated to / mirrored on one direction (econ->psych); cross-direction "
        "performance is not measured.",
        "Per-source DGP is a hurdle (0 with prob 1-p, else 1+Poisson(e1/p-1)) matched to two "
        "observable margins (e1, p); it does not reproduce the full edge-count tail or any "
        "correlation between reference-list length and target propensity.",
        "Defects are injected at the table level; real acquisition failure modes (ID resolution "
        "errors, deduplication, per-source coverage windows) are not simulated.",
        "Truth labels are generative (an injection was applied); they are not an external "
        "adjudication of which doses *scientifically* matter.",
        "Real-data anchor is the corpus the criteria were built on and is reported as an anchor, "
        "not as evidence.",
        "UNKNOWN exists only on the truth side (void worlds); the frozen criteria themselves have "
        "no UNKNOWN output state.",
    ]
    result["meta"]["runtime_sec"] = round(time.time() - t0, 1)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    sc = result["scoring"]
    print("confusion:", json.dumps(sc["confusion_all"], ensure_ascii=False))
    print("rates:", json.dumps(sc["rates_all"], ensure_ascii=False))
    print("truth x verdict:", json.dumps(sc["truth_x_verdict"], ensure_ascii=False))
    print("invariance exact:", result["invariance"]["all_exact"],
          "verdicts identical:", result["invariance"]["all_verdicts_identical"])
    print("archived fidelity:", result["archived_fidelity"].get("all_match"))
    print("real anchor:", result["real_anchor"].get("verdict"),
          json.dumps(result["real_anchor"].get("stats", {}), ensure_ascii=False))
    print("\ndose-response ladders:")
    for k, v in sorted(result["dose_response"].items()):
        print(" ", k, "| dose", v["dose"], "| flag", v["flag_rate"], "| oracle", v["oracle_verdict"],
              "| first_flag", v["first_flagged_dose"], "| blind<=dose", v["blind_zone_upto_dose"])
    print("\nwrote", OUT_PATH, "in", result["meta"]["runtime_sec"], "s")
    return result


if __name__ == "__main__":
    main()
