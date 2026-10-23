# -*- coding: utf-8 -*-
"""Minimal sensitivity analysis for the bidirectional asymmetry (2026-10-16).

Read-only downstream analysis. The database is opened through ecdb.raw_sql
(SQLite read-only URI, no writes of any kind). Exactly two SELECTs touch the
database: the same full-table extractions used by the paper-level resampling
script (research/nature/paper_bootstrap_asymmetry.py, imported below for its
locked CANON / STABLE8 definitions and helpers). The extraction is extended in
the same pass with the diagnostic columns this analysis needs, so no scenario
triggers an extra full-database query; all analyses use one in-memory paper table.

Paper-level extraction (reused, side-effect-free import):
  * meta  : accession_no / pub_year / source / label / tier / confidence
            per paper  (+ p.num_references = EI-declared reference count);
  * refs  : per citing paper, edges into EC / NON_EC (distinct cited in-corpus
            papers), distinct DOI references, and -- added here -- edges into
            low-confidence queue papers, total reference rows, DOI-resolved
            reference rows.  paper_cit_edges is NOT used (docs/DATA_USAGE.md
            note 10); the E3 denominator is COUNT(DISTINCT cited_doi), matching
            stable8_merged.py / paper_bootstrap_asymmetry.py.

Locked definitions (identical to the paper-level resampling and bidirectional analysis scripts):
  * canonical merged source names (CANON) restricted to the frozen STABLE8 set;
  * directions: forward pool = NON_EC-labeled citing papers, target EC;
    reverse pool = EC-labeled citing papers, target NON_EC;
  * E1 = mean target edges per citing paper; E2 = share of papers with >= 1
    target edge; E3 = mean share of DOI-resolved references pointing at the
    target (zero-DOI-reference papers contribute 0.0 and stay in the E1/E2/E3
    denominators);
  * gap_pp = 100 * (reverse relative change - forward relative change);
    forward/reverse pools are non-paired;
  * support = canonical source with a non-empty paper pool in every required
    year in BOTH directions (rule stated per analysis);
  * 2025 is the final collection year (right censoring).

Analyses (all point estimates, no new uncertainty intervals):
  S1  paper-level resampling consistency check on the extended extraction;
  S2  low-confidence label queue retained vs excluded
      (predicate: tier='llm' AND confidence<0.75), 2021 base, endpoints
      2024/2025, E1/E2/E3; two exclusion variants (units only / units + target
      edges deleted);
  S3  common-source leave-one-source-out gap (all 7 support sources, focus
      on IEEE Transactions on Fuzzy Systems), base years 2019/2021/2024,
      endpoints 2024/2025, E1/E2/E3; each dropped source is removed from both
      direction pools and weights are renormalised separately;
  S4  2024/2025 endpoint x 2019/2021/2024 composition-base summary (the frozen
      18-cell matrix, recomputed at paper level with sample sizes);
  S5  reference-DOI availability and reference-denominator coverage diagnostic
      (descriptive coverage only; explicitly NOT a correction).

Output: research/nature/out/asymmetry_sensitivity.json (new file; the frozen
outputs paper_bootstrap_asymmetry.json / stable8_merged.json /
bidirectional_asymmetry.json are read-only cross-check inputs and are never
written).

Usage:
  python research/nature/asymmetry_sensitivity.py              # full run + write
  python research/nature/asymmetry_sensitivity.py --no-write   # run, print, no JSON
"""
import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ecdb
import paper_bootstrap_asymmetry as pb  # locked definitions; import is side-effect free

OUT = os.path.join(HERE, "out", "asymmetry_sensitivity.json")
FROZEN_BOOTSTRAP = os.path.join(HERE, "out", "paper_bootstrap_asymmetry.json")
FROZEN_STABLE8 = os.path.join(HERE, "out", "stable8_merged.json")
FROZEN_GAP = os.path.join(HERE, "out", "bidirectional_asymmetry.json")

CANON = pb.CANON            # reuse the frozen merged-name map
STABLE8 = pb.STABLE8        # reuse the frozen 8-source set
SEED = pb.SEED              # seed constant retained for provenance; no resampling here

DIRECTIONS = ("forward", "reverse")
METRICS = ("E1", "E2", "E3")
M_IDX = {m: i for i, m in enumerate(METRICS)}
START_YEAR = 2021
WINDOW_ENDS = (2024, 2025)
BASE_YEARS = (2019, 2021, 2024)
SCOPE_YEARS = (2019, 2021, 2024, 2025)   # 2019 needed for the 2019 composition base
GATE1_YEARS = (2021, 2024, 2025)         # paper-level support-rule years
BIDI_YEARS = (2019, 2021, 2024, 2025)    # bidirectional support-rule years
CENSORED_YEARS = (2025,)
LOWCONF_TIER = "llm"
LOWCONF_THRESHOLD = 0.75
LOWCONF_QUEUE_FILE = "archive/labeling/low_confidence_review.csv"  # pre-registered queue (reference only, never re-read)

# --- extraction: paper-level queries plus diagnostics in one pass ------------
META_SQL = (
    "SELECT p.accession_no AS acc, p.pub_year AS y, p.source AS src, "
    "d.label AS lab, d.tier AS tier, d.confidence AS conf, "
    "p.num_references AS nrefs_declared "
    "FROM papers p JOIN paper_domain d ON d.accession_no = p.accession_no"
)
REFS_SQL = (
    "SELECT r.accession_no AS acc, "
    "COUNT(DISTINCT CASE WHEN d.label='EC' THEN pc.accession_no END) AS n_ec, "
    "COUNT(DISTINCT CASE WHEN d.label='NON_EC' THEN pc.accession_no END) AS n_non, "
    "COUNT(DISTINCT CASE WHEN d.label='EC' AND d.tier='llm' AND d.confidence<0.75 "
    "THEN pc.accession_no END) AS n_ec_lowconf, "
    "COUNT(DISTINCT CASE WHEN d.label='NON_EC' AND d.tier='llm' AND d.confidence<0.75 "
    "THEN pc.accession_no END) AS n_non_lowconf, "
    "COUNT(DISTINCT r.cited_doi) AS n_refs_doi, "
    "COUNT(*) AS n_rows_all, "
    "COUNT(r.cited_doi) AS n_rows_doi "
    "FROM paper_refs_out r "
    "LEFT JOIN papers pc ON pc.doi = r.cited_doi "
    "LEFT JOIN paper_domain d ON d.accession_no = pc.accession_no "
    "GROUP BY r.accession_no"
)
# NOTE: the paper-level resampling query carried "WHERE r.cited_doi IS NOT NULL"; it is dropped
# here because n_rows_all must include reference rows without a DOI.  NULL rows
# cannot match pc (pc.doi = NULL is never true), so all edge counts and the
# distinct-DOI denominator are unchanged -- verified cell by cell against the
# locked paper-level output in the gate1_strata consistency block.

# entry tuple layout
E_ACC, E_EDGES, E_PART, E_E3 = 0, 1, 2, 3
E_EDGES_LC, E_PART_LC, E_E3_LC = 4, 5, 6        # edge counts after queue-target deletion
E_NREFS, E_ROWS_ALL, E_ROWS_DOI, E_DECLARED = 7, 8, 9, 10
E_LOWCONF, E_CONF, E_TIER = 11, 12, 13


def r6(x):
    return None if x is None else round(float(x), 6)


def r4(x):
    return None if x is None else round(float(x), 4)


def load_cells():
    """Two SELECTs -> canonical in-scope cells.  (d, y, s) -> [entry tuples]."""
    meta = {}
    for r in ecdb.raw_sql(META_SQL, max_rows=200000)["rows"]:
        meta[r["acc"]] = (r["y"], r["src"], r["lab"], r["tier"], r["conf"], r["nrefs_declared"])
    agg = {}
    for r in ecdb.raw_sql(REFS_SQL, max_rows=400000)["rows"]:
        agg[r["acc"]] = (int(r["n_ec"]), int(r["n_non"]), int(r["n_ec_lowconf"]),
                         int(r["n_non_lowconf"]), int(r["n_refs_doi"]),
                         int(r["n_rows_all"]), int(r["n_rows_doi"]))
    cells = defaultdict(list)
    n_scope = 0
    for acc, (y, src_raw, lab, tier, conf, declared) in meta.items():
        if y not in SCOPE_YEARS:
            continue
        src = CANON.get(src_raw, src_raw)
        if src not in STABLE8:
            continue
        n_scope += 1
        n_ec, n_non, n_ec_lc, n_non_lc, n_refs, rows_all, rows_doi = agg.get(acc, (0,) * 7)
        d = "forward" if lab == "NON_EC" else "reverse"
        edges = n_ec if d == "forward" else n_non
        edges_lc = n_ec_lc if d == "forward" else n_non_lc
        edges_after = edges - edges_lc
        conf_f = None if conf is None else float(conf)
        lowconf = (tier == LOWCONF_TIER and conf_f is not None and conf_f < LOWCONF_THRESHOLD)
        entry = (acc, float(edges), 1.0 if edges else 0.0,
                 (edges / n_refs) if n_refs else 0.0,
                 float(edges_after), 1.0 if edges_after > 0 else 0.0,
                 (edges_after / n_refs) if n_refs else 0.0,
                 n_refs, rows_all, rows_doi,
                 None if declared is None else int(declared), 1 if lowconf else 0,
                 conf_f, tier)
        cells[(d, y, src)].append(entry)
    for k in cells:
        cells[k].sort(key=lambda e: e[E_ACC])   # deterministic order
    return cells, len(meta), len(agg), n_scope


def kept_entries(entries, mode):
    """mode: 'full' keeps every paper; 'unit_excluded' / 'full_excluded' drop the
    tier='llm' & confidence<0.75 queue papers as citing units.  'full_excluded'
    additionally deletes, for retained papers, edges whose TARGET is a queue
    paper (a deletion, not a relabel: see limitations)."""
    if mode == "full":
        return entries
    return [e for e in entries if not e[E_LOWCONF]]


def cell_values(entries, mode):
    """Per-cell (n, sum_e1, sum_e2, sum_e3) under a mode."""
    sel = kept_entries(entries, mode)
    n = len(sel)
    if mode == "full_excluded":
        return n, (sum(e[E_EDGES_LC] for e in sel),
                   sum(e[E_PART_LC] for e in sel),
                   sum(e[E_E3_LC] for e in sel))
    return n, (sum(e[E_EDGES] for e in sel), sum(e[E_PART] for e in sel),
               sum(e[E_E3] for e in sel))


def build_tables(cells, mode):
    """counts[(d,y,s)] and means[(d,y,s)] = (E1,E2,E3) means, under a mode."""
    counts, means = {}, {}
    for key, entries in cells.items():
        n, sums = cell_values(entries, mode)
        counts[key] = n
        means[key] = tuple((s / n if n else None) for s in sums)
    return counts, means


def derive_support(counts, rule_years, directions=DIRECTIONS):
    srcs = {k[2] for k in counts}
    return sorted({s for s in srcs
                   if all(counts.get((dd, yy, s), 0) > 0 for dd in directions for yy in rule_years)})


def base_weights(counts, direction, base_year, support):
    c = {s: counts.get((direction, base_year, s), 0) for s in support}
    tot = sum(c.values())
    if not tot:
        return {}, 0
    return {s: c[s] / tot for s in support}, tot


def aggregate(means, weights, direction, year, metric):
    """Weighted mean over available strata with weight renormalisation,
    mirroring bidirectional_asymmetry.py."""
    i = M_IDX[metric]
    num, wsum = 0.0, 0.0
    for s, w in weights.items():
        m = means.get((direction, year, s))
        if m is None or m[i] is None:
            continue
        num += w * m[i]
        wsum += w
    if wsum <= 0:
        return None, wsum
    return num / wsum, wsum


def gap_for(base_year, end_year, metric, support, w_counts, v_means):
    """Gap under composition base_year.  w_counts supplies the base-year source
    weights (which table the weights come from is explicit); v_means supplies
    the per-cell metric means (which may be an exclusion variant of the same
    weights table)."""
    out = {"forward": None, "reverse": None, "gap_pp": None,
           "n_base": {}, "weight_sum_start": {}, "weight_sum_end": {}}
    rels = {}
    for d in DIRECTIONS:
        w, n_base = base_weights(w_counts, d, base_year, support)
        out["n_base"][d] = n_base
        if not w:
            continue
        start, ws = aggregate(v_means, w, d, START_YEAR, metric)
        end, we = aggregate(v_means, w, d, end_year, metric)
        out["weight_sum_start"][d] = r6(ws)
        out["weight_sum_end"][d] = r6(we)
        if start in (None, 0) or end is None:
            continue
        rel = end / start - 1.0
        rels[d] = rel
        out[d] = {"start": r6(start), "end": r6(end), "rel_change": r6(rel)}
    if "forward" in rels and "reverse" in rels:
        out["gap_pp"] = r6(100.0 * (rels["reverse"] - rels["forward"]))
    return out


def main():
    ap = argparse.ArgumentParser(description="Minimal sensitivity analysis package")
    ap.add_argument("--no-write", action="store_true", help="run and print, write no JSON")
    args = ap.parse_args()
    t_start = time.time()

    # ---- extraction (two SELECTs, one in-memory per-paper table) -------------
    t0 = time.time()
    cells, n_meta, n_agg, n_scope = load_cells()
    print(f"[1/6] extraction: meta rows {n_meta}, refs-aggregate rows {n_agg}, "
          f"in-scope papers {n_scope}  ({time.time()-t0:.1f}s)", flush=True)

    tables = {mode: build_tables(cells, mode)
              for mode in ("full", "unit_excluded", "full_excluded")}
    counts_full, means_full = tables["full"]

    support_g1 = derive_support(counts_full, GATE1_YEARS)
    support_bidi = derive_support(counts_full, BIDI_YEARS)
    print(f"[2/6] support (paper-level rule {GATE1_YEARS}): {support_g1}", flush=True)
    print(f"      support (bidirectional rule {BIDI_YEARS}): {support_bidi} "
          f"(identical: {support_g1 == support_bidi})", flush=True)

    # ---- S1: paper-level consistency check (fixed 2021 weights) ---------------
    w1_full = {d: base_weights(counts_full, d, START_YEAR, support_g1)[0] for d in DIRECTIONS}
    s1 = {"support": support_g1,
          "rule": f"sources non-empty in {GATE1_YEARS} in both directions",
          "weights_2021": {d: {s: r6(v) for s, v in w1_full[d].items()} for d in DIRECTIONS},
          "n_base_2021": {d: sum(counts_full.get((d, START_YEAR, s), 0) for s in support_g1)
                          for d in DIRECTIONS},
          "point_estimates": {}}
    for Y in WINDOW_ENDS:
        win = f"{START_YEAR}->{Y}"
        s1["point_estimates"][win] = {}
        for m in METRICS:
            g = gap_for(START_YEAR, Y, m, support_g1, counts_full, means_full)
            s1["point_estimates"][win][m] = {
                "forward_rel_change": r4(g["forward"]["rel_change"]),
                "reverse_rel_change": r4(g["reverse"]["rel_change"]),
                "gap_pp": r4(g["gap_pp"])}

    # ---- S2: low-confidence label queue ---------------------------------------
    inv = {d: {"total": 0, "per_year": {}, "conf_values": {}, "out_of_support": 0}
           for d in DIRECTIONS}
    for (d, y, s), entries in sorted(cells.items()):
        if y not in GATE1_YEARS:
            continue
        q = [e for e in entries if e[E_LOWCONF]]
        if s not in support_g1:
            if q:
                inv[d]["out_of_support"] += len(q)
            continue
        per_y = inv[d]["per_year"].setdefault(str(y), {"n": 0, "per_source": {}, "pool_n": 0})
        per_y["pool_n"] += len(entries)
        if q:
            per_y["n"] += len(q)
            per_y["per_source"][s] = len(q)
            inv[d]["total"] += len(q)
            for e in q:
                key = str(e[E_CONF])
                inv[d]["conf_values"][key] = inv[d]["conf_values"].get(key, 0) + 1
    for d in DIRECTIONS:
        for per_y in inv[d]["per_year"].values():
            per_y["share_of_pool"] = r6(per_y["n"] / per_y["pool_n"]) if per_y["pool_n"] else None
        pool_tot = sum(v["pool_n"] for v in inv[d]["per_year"].values())
        inv[d]["share_of_pool_2021_24_25"] = r6(inv[d]["total"] / pool_tot) if pool_tot else None

    queue_own = {}
    for d in DIRECTIONS:
        sel = [e for k, entries in cells.items()
               if k[0] == d and k[1] in GATE1_YEARS and k[2] in support_g1
               for e in entries if e[E_LOWCONF]]
        n = len(sel)
        edges_into_queue = int(sum(e[E_EDGES_LC] for k, entries in cells.items()
                                   if k[0] == d and k[1] in GATE1_YEARS and k[2] in support_g1
                                   for e in entries))
        citing_affected = sum(1 for k, entries in cells.items()
                              if k[0] == d and k[1] in GATE1_YEARS and k[2] in support_g1
                              for e in entries if e[E_EDGES_LC] > 0)
        queue_own[d] = {
            "n": n,
            "n_edges": int(sum(e[E_EDGES] for e in sel)),
            "E1": r6(sum(e[E_EDGES] for e in sel) / n) if n else None,
            "E2": r6(sum(e[E_PART] for e in sel) / n) if n else None,
            "E3": r6(sum(e[E_E3] for e in sel) / n) if n else None,
            "n_refs_doi": int(sum(e[E_NREFS] for e in sel)),
            "n_edges_with_queue_paper_as_target": edges_into_queue,
            "n_citing_papers_with_queue_target_edge": citing_affected,
        }

    s2 = {"queue": {"predicate": f"tier='{LOWCONF_TIER}' AND confidence<{LOWCONF_THRESHOLD}",
                    "source_field": "paper_domain.tier / paper_domain.confidence",
                    "pre_registered_queue": LOWCONF_QUEUE_FILE,
                    "inventory": inv,
                    "queue_own_record_levels": queue_own,
                    "note": ("queue_own_record_levels are the queue papers' own E1/E2/E3 levels in "
                             "their pool (descriptive mechanism read), not additive decompositions "
                             "of the gap change; the queue sits far above its pool's target-edge "
                             "levels, which is consistent with borderline labels but is not a labeling "
                             "verdict (the queue is not manually reviewed here); 'out_of_support' "
                             "counts queue papers in in-scope years that sit in a STABLE8 source "
                             "outside the frozen support (Computers and Industrial Engineering 2021) "
                             "and are not in the analysis pool.")},
          "variants": {}}

    for mode, label in (
            ("unit_excluded", "queue removed as citing units only"),
            ("full_excluded", "queue removed as citing units AND as edge targets (deleted, not relabelled)")):
        counts_m, means_m = tables[mode]
        support_m = derive_support(counts_m, GATE1_YEARS)
        w_m = {d: base_weights(counts_m, d, START_YEAR, support_m)[0] for d in DIRECTIONS}
        block = {"label": label, "support": support_m,
                 "support_unchanged_vs_full": support_m == support_g1,
                 "n_base_2021": {d: sum(counts_m.get((d, START_YEAR, s), 0) for s in support_m)
                                 for d in DIRECTIONS},
                 "weights_2021": {d: {s: r6(v) for s, v in w_m[d].items()} for d in DIRECTIONS},
                 "point_estimates": {}, "point_estimates_frozen_2021_weights": {},
                 "delta_vs_full_pp": {}}
        for Y in WINDOW_ENDS:
            win = f"{START_YEAR}->{Y}"
            block["point_estimates"][win] = {}
            block["point_estimates_frozen_2021_weights"][win] = {}
            block["delta_vs_full_pp"][win] = {}
            for m in METRICS:
                g_m = gap_for(START_YEAR, Y, m, support_m, counts_m, means_m)
                block["point_estimates"][win][m] = {
                    "forward_rel_change": r4(g_m["forward"]["rel_change"]),
                    "reverse_rel_change": r4(g_m["reverse"]["rel_change"]),
                    "gap_pp": r4(g_m["gap_pp"])}
                g_f = gap_for(START_YEAR, Y, m, support_g1, counts_full, means_m)
                block["point_estimates_frozen_2021_weights"][win][m] = {
                    "forward_rel_change": r4(g_f["forward"]["rel_change"]),
                    "reverse_rel_change": r4(g_f["reverse"]["rel_change"]),
                    "gap_pp": r4(g_f["gap_pp"])}
                g_full = gap_for(START_YEAR, Y, m, support_g1, counts_full, means_full)
                block["delta_vs_full_pp"][win][m] = r4(g_m["gap_pp"] - g_full["gap_pp"])
        s2["variants"][mode] = block

    # ---- S3: common-source leave-one-source-out -------------------------------
    full_cells = {}
    for BY in BASE_YEARS:
        for Y in WINDOW_ENDS:
            for m in METRICS:
                full_cells[f"{BY}|{START_YEAR}->{Y}|{m}"] = gap_for(
                    BY, Y, m, support_bidi, counts_full, means_full)

    rev_loo = {}
    for dropped in support_bidi:
        kept = [s for s in support_bidi if s != dropped]
        per_source = {}
        for BY in BASE_YEARS:
            for Y in WINDOW_ENDS:
                for m in METRICS:
                    g = gap_for(BY, Y, m, kept, counts_full, means_full)
                    per_source[f"{BY}|{START_YEAR}->{Y}|{m}"] = {
                        "gap_pp": r6(g["gap_pp"]),
                        "reverse_rel_change": r6(g["reverse"]["rel_change"]),
                        "reverse_n_base": g["n_base"]["reverse"],
                        "delta_vs_full_pp": r6(g["gap_pp"] - full_cells[f"{BY}|{START_YEAR}->{Y}|{m}"]["gap_pp"]),
                    }
        gaps = [v["gap_pp"] for v in per_source.values() if v["gap_pp"] is not None]
        rev_loo[dropped] = {
            "cells": per_source,
            "gap_min_pp": r6(min(gaps)) if gaps else None,
            "gap_max_pp": r6(max(gaps)) if gaps else None,
            "all_gaps_positive": all(g > 0 for g in gaps) if gaps else None,
            "reverse_n_by_year": {str(y): counts_full.get(("reverse", y, dropped), 0)
                                  for y in SCOPE_YEARS},
        }

    tfs = "IEEE Transactions on Fuzzy Systems"
    s3 = {"support": support_bidi,
          "rule": f"sources non-empty in {BIDI_YEARS} in both directions",
          "direction_note": ("Common-source LOO: the dropped source is removed from both the "
                             "forward and reverse support pools, and base-year weights are "
                             "recomputed and renormalised separately in each direction."),
          "full_reference": {k: {"gap_pp": r6(v["gap_pp"]),
                                 "forward_rel_change": r6(v["forward"]["rel_change"]),
                                 "reverse_rel_change": r6(v["reverse"]["rel_change"]),
                                 "n_base": v["n_base"]} for k, v in full_cells.items()},
          "by_source": rev_loo,
          "focus_tfs": {
              "source": tfs,
              "reverse_n_by_year": rev_loo[tfs]["reverse_n_by_year"],
              "cells": rev_loo[tfs]["cells"],
              "gap_min_pp": rev_loo[tfs]["gap_min_pp"],
              "gap_max_pp": rev_loo[tfs]["gap_max_pp"],
              "all_gaps_positive": rev_loo[tfs]["all_gaps_positive"],
              "note": ("TFS reverse pools are tiny (n per year above), so both the full and the "
                       "dropped variant rest on a handful of extreme papers; this LOO quantifies "
                       "weight leverage of a small extreme source, not estimate stability."),
          },
          "both_direction_loo": "recomputed only inside cross_check.frozen_loo_126 (read-only check; not re-emitted)"}

    # both-direction LOO recomputed purely as a read-only cross-check of the
    # frozen bidirectional output
    both_loo = {}
    for dropped in support_bidi:
        kept = [s for s in support_bidi if s != dropped]
        for BY in BASE_YEARS:
            for Y in WINDOW_ENDS:
                for m in METRICS:
                    both_loo[f"{dropped}|{BY}|{START_YEAR}->{Y}|{m}"] = \
                        gap_for(BY, Y, m, kept, counts_full, means_full)["gap_pp"]

    # ---- S4: base-period x endpoint summary -----------------------------------
    s4 = {"support": support_bidi,
          "spec": {"base_years": list(BASE_YEARS), "window_start_year": START_YEAR,
                   "end_years": list(WINDOW_ENDS),
                   "base_year_role": ("the base year fixes the composition weights; the compared "
                                      "levels are always 2021 vs the endpoint (identical to the "
                                      "frozen bidirectional matrix spec)")},
          "cells": {}, "endpoint_gap_delta_pp": {}}
    for BY in BASE_YEARS:
        for Y in WINDOW_ENDS:
            for m in METRICS:
                v = full_cells[f"{BY}|{START_YEAR}->{Y}|{m}"]
                s4["cells"][f"{BY}|{START_YEAR}->{Y}|{m}"] = {
                    "forward_rel_change": r6(v["forward"]["rel_change"]),
                    "reverse_rel_change": r6(v["reverse"]["rel_change"]),
                    "gap_pp": r6(v["gap_pp"]),
                    "right_censored_endpoint": Y in CENSORED_YEARS,
                    "n_base": v["n_base"],
                    "weight_sum_start": v["weight_sum_start"],
                    "weight_sum_end": v["weight_sum_end"]}
    for BY in BASE_YEARS:
        for m in METRICS:
            g24 = full_cells[f"{BY}|{START_YEAR}->2024|{m}"]["gap_pp"]
            g25 = full_cells[f"{BY}|{START_YEAR}->2025|{m}"]["gap_pp"]
            s4["endpoint_gap_delta_pp"][f"{BY}|{m}"] = r6(g25 - g24)
    gaps_all = [v["gap_pp"] for v in s4["cells"].values() if v["gap_pp"] is not None]
    s4["summary"] = {
        "n_cells": len(s4["cells"]),
        "gap_min_pp": r6(min(gaps_all)) if gaps_all else None,
        "gap_max_pp": r6(max(gaps_all)) if gaps_all else None,
        "all_gaps_positive": all(g > 0 for g in gaps_all) if gaps_all else None,
        "censored_endpoints": list(CENSORED_YEARS),
        "censoring_note": ("2025 is the final collection year (right censoring); every 2025 number "
                           "mixes trend with truncation and must be read next to its 2024 "
                           "counterpart. endpoint_gap_delta_pp = gap(2021->2025) - gap(2021->2024) "
                           "per base year and metric."),
    }

    # ---- S5: reference-DOI availability / denominator coverage ----------------
    diag_cells = {}
    for (d, y, s), entries in sorted(cells.items()):
        n = len(entries)
        n_zero = sum(1 for e in entries if e[E_NREFS] == 0)
        n_no_rows = sum(1 for e in entries if e[E_ROWS_ALL] == 0)
        rows_all = sum(e[E_ROWS_ALL] for e in entries)
        rows_doi = sum(e[E_ROWS_DOI] for e in entries)
        nrefs = sum(e[E_NREFS] for e in entries)
        n_decl = sum(1 for e in entries if e[E_DECLARED] is not None)
        decl_sum = sum(e[E_DECLARED] for e in entries if e[E_DECLARED] is not None)
        edges = int(sum(e[E_EDGES] for e in entries))
        edges_zero = int(sum(e[E_EDGES] for e in entries if e[E_NREFS] == 0))
        diag_cells[f"{d}|{y}|{s}"] = {
            "in_frozen_support": s in support_bidi,
            "n_papers": n,
            "n_papers_no_ref_rows": n_no_rows,
            "n_papers_zero_doi_refs": n_zero,
            "share_papers_with_doi_ref": r6(1 - n_zero / n) if n else None,
            "ref_rows_total": rows_all,
            "ref_rows_doi": rows_doi,
            "doi_row_rate": r6(rows_doi / rows_all) if rows_all else None,
            "distinct_doi_refs": nrefs,
            "mean_distinct_doi_per_paper": r6(nrefs / n) if n else None,
            "n_papers_declared_refs": n_decl,
            "declared_refs_sum": decl_sum,
            "distinct_doi_over_declared": r6(nrefs / decl_sum) if decl_sum else None,
            "edges": edges,
            "edges_in_zero_doi_papers": edges_zero,
            "edge_share_in_zero_doi_papers": r6(edges_zero / edges) if edges else None,
        }
    pooled = {}
    for d in DIRECTIONS:
        for y in SCOPE_YEARS:
            sel = [e for k, entries in cells.items()
                   if k[0] == d and k[1] == y and k[2] in support_bidi for e in entries]
            n = len(sel)
            if not n:
                continue
            n_zero = sum(1 for e in sel if e[E_NREFS] == 0)
            rows_all = sum(e[E_ROWS_ALL] for e in sel)
            rows_doi = sum(e[E_ROWS_DOI] for e in sel)
            nrefs = sum(e[E_NREFS] for e in sel)
            decl_sum = sum(e[E_DECLARED] for e in sel if e[E_DECLARED] is not None)
            edges = int(sum(e[E_EDGES] for e in sel))
            edges_zero = int(sum(e[E_EDGES] for e in sel if e[E_NREFS] == 0))
            pooled[f"{d}|{y}"] = {
                "n_papers": n,
                "n_papers_zero_doi_refs": n_zero,
                "share_papers_with_doi_ref": r6(1 - n_zero / n) if n else None,
                "doi_row_rate": r6(rows_doi / rows_all) if rows_all else None,
                "mean_distinct_doi_per_paper": r6(nrefs / n) if n else None,
                "distinct_doi_over_declared": r6(nrefs / decl_sum) if decl_sum else None,
                "edges": edges,
                "edges_in_zero_doi_papers": edges_zero,
            }
    s5 = {
        "cells": diag_cells,
        "pooled_by_direction_year_support_only": pooled,
        "pooled_observation": {
            "forward_doi_row_rate_by_year": {str(y): pooled.get(f"forward|{y}", {}).get("doi_row_rate")
                                             for y in SCOPE_YEARS},
            "reverse_doi_row_rate_by_year": {str(y): pooled.get(f"reverse|{y}", {}).get("doi_row_rate")
                                             for y in SCOPE_YEARS},
            "note": ("Observed pattern: the reverse pool parses at a HIGHER rate than the forward pool "
                     "in every scope year, and the two pools' rates do not move together (forward falls "
                     "from 2021 to 2025, reverse rises). Because a target edge is only counted when the "
                     "cited reference carries a DOI matching an in-corpus paper, this is a shared "
                     "exposure of E1/E2/E3 and a plausible confound direction for the measured gap. It "
                     "still does NOT license a correction: the target mix of the unparsed references is "
                     "unobserved, so the diagnostic cannot sign or bound the resulting bias, and no "
                     "rescaling is applied anywhere in this package."),
        },
        "definitions": {
            "doi_row_rate": "rows with non-null cited_doi / all reference rows in paper_refs_out (per direction/year/source cell)",
            "share_papers_with_doi_ref": "citing papers with >= 1 distinct DOI reference (E3 denominator > 0)",
            "distinct_doi_over_declared": "distinct DOI references / EI-declared num_references (papers with a declared count only)",
            "edges_in_zero_doi_papers": ("structurally expected to be 0: an edge is counted only when "
                                         "the cited reference has a DOI that matches an in-corpus paper "
                                         "DOI, so E1/E2 also depend on reference-DOI availability"),
        },
        "interpretation": {
            "role": "descriptive coverage diagnostic only",
            "zh": ("本诊断只描述参考文献 DOI 可用率与 E3 分母覆盖（多少施引论文有可解析的参考文献分母）。"
                   "它不是校正：没有插补、没有重加权、没有按解析率外推；缺 DOI 的参考文献并非随机缺失"
                   "（随年份、期刊、语料来源与存缴习惯变化），任何把观测值除以解析率或按解析率放大的做法都"
                   "预设了缺失机制，本包不做这种假设，也不给出偏差方向或大小的界限。E3 是三估计量中唯一"
                   "以 DOI 解析为分母的读数；E1/E2 的边也要求被引侧 DOI 能匹配库内论文，因此解析可用率"
                   "是全部三估计量的共同暴露面，但本诊断不能把这种暴露换算成校正。"),
            "en": ("This diagnostic only describes reference-DOI availability and E3 denominator "
                   "coverage (how many citing papers have a resolvable reference denominator). It is "
                   "NOT a correction: no imputation, no reweighting, no division/extrapolation by the "
                   "observed parse rate. References without a DOI are not missing at random (they vary "
                   "by year, source and venue deposit practice), so scaling by the observed rate would "
                   "assume the missingness mechanism; this package makes no such assumption and offers "
                   "no bias bound. E3 is the only estimator whose denominator is DOI-resolved "
                   "references; E1/E2 edges also require the cited side's DOI to match an in-corpus "
                   "paper, so parse availability is a shared exposure of all three estimators -- which "
                   "this diagnostic cannot convert into a correction."),
            "must_not": [
                "must not be used to rescale or correct E3 (or any other estimate)",
                "must not be read as an upper or lower bound on the true cross-domain citation share",
                "must not be read as evidence that E1/E2 are parse-rate immune",
            ],
        },
    }

    # ---- cross-checks against frozen outputs (read-only) ----------------------
    # Tolerances: the frozen stable8/bidirectional numbers are built from source
    # means rounded to 6 decimals (r6).  E3 source means are small (~0.01-0.02),
    # so a 5e-7 rounding error is amplified by 1/start (~50x) in the relative
    # change and by 100x more on the pp scale: E3 therefore needs a wider
    # tolerance than E1/E2.  This recomputation is the UNROUNDED paper-level
    # value.
    TOL = {"E1": {"gap": 5e-4, "rel": 1e-5},
           "E2": {"gap": 5e-4, "rel": 1e-5},
           "E3": {"gap": 5e-3, "rel": 1e-4}}
    cross = {
        "tolerance_note": ("tolerances: E1/E2 gap 5e-4 pp / rel 1e-5; E3 gap 5e-3 pp / rel 1e-4, "
                           "because frozen source means are r6-rounded and E3's small base amplifies "
                           "the rounding"),
        "gate1_point_estimates": {"checked": 0, "mismatch": []},
        "gate1_strata": {"checked": 0, "mismatch": []},
        "frozen_matrix_18": {"checked": 0, "mismatch": []},
        "frozen_loo_126": {"checked": 0, "mismatch": []},
        "stable8_2019_cells": {"checked": 0, "mismatch": []},
        "support_lists": {"checked": 0, "mismatch": []},
    }
    if os.path.exists(FROZEN_BOOTSTRAP):
        with open(FROZEN_BOOTSTRAP, encoding="utf-8") as fh:
            fb = json.load(fh)
        for Y in WINDOW_ENDS:
            win = f"{START_YEAR}->{Y}"
            for m in METRICS:
                mine = s1["point_estimates"][win][m]
                theirs = fb["point_estimates"][win][m]
                for field in ("forward_rel_change", "reverse_rel_change", "gap_pp"):
                    cross["gate1_point_estimates"]["checked"] += 1
                    a, b = mine[field], theirs[field]
                    if a is None or b is None or abs(a - b) > 5e-5:
                        cross["gate1_point_estimates"]["mismatch"].append([win, m, field, a, b])
        for key, blk in fb["strata"].items():
            d, y, s = key.split("|")
            y = int(y)
            entries = cells.get((d, y, s), [])
            n, sums = cell_values(entries, "full")
            my_e = [r6(sums[0] / n) if n else None, r6(sums[1] / n) if n else None,
                    r6(sums[2] / n) if n else None]
            my_nrefs = sum(e[E_NREFS] for e in entries)
            my_tiers = dict(sorted(Counter(e[E_TIER] for e in entries).items()))
            my_minconf = min((e[E_CONF] for e in entries if e[E_CONF] is not None), default=None)
            cross["gate1_strata"]["checked"] += 1
            ok = (blk["n"] == n
                  and blk["n_edges"] == int(sums[0])
                  and blk["n_participating"] == int(sums[1])
                  and blk["n_refs_doi"] == my_nrefs
                  and abs(blk["sum_share_of_refs"] - sums[2]) <= 1e-6
                  and all(abs((blk[m] if blk[m] is not None else -1)
                              - (my_e[i] if my_e[i] is not None else -2)) <= 1e-6
                          for i, m in enumerate(METRICS))
                  and blk["tier_counts"] == my_tiers
                  and (blk["min_confidence"] is None) == (my_minconf is None)
                  and (blk["min_confidence"] is None
                       or abs(blk["min_confidence"] - my_minconf) <= 5e-5))
            if not ok:
                cross["gate1_strata"]["mismatch"].append(
                    [key, {"n": n, "n_edges": int(sums[0]), "n_participating": int(sums[1]),
                           "n_refs_doi": my_nrefs, "sum_share_of_refs": r6(sums[2]),
                           "means": my_e, "tier_counts": my_tiers, "min_confidence": r4(my_minconf)},
                     {"n": blk["n"], "n_edges": blk["n_edges"],
                      "n_participating": blk["n_participating"], "n_refs_doi": blk["n_refs_doi"],
                      "sum_share_of_refs": blk["sum_share_of_refs"], "means": [blk[m] for m in METRICS],
                      "tier_counts": blk["tier_counts"], "min_confidence": blk["min_confidence"]}])
    if os.path.exists(FROZEN_STABLE8):
        with open(FROZEN_STABLE8, encoding="utf-8") as fh:
            fs = json.load(fh)
        for s in support_bidi:
            for d, table, fields in (("forward", fs["per_source_e1"], ("n_non", "E1", "E2", "E3")),
                                     ("reverse", fs["per_source_e1_reverse"],
                                      ("n_ec", "E1_to_non", "E2_to_non", "E3_to_non"))):
                key = f"2019|{s}"
                ref = table.get(key)
                cross["stable8_2019_cells"]["checked"] += 1
                entries = cells.get((d, 2019, s), [])
                n, sums = cell_values(entries, "full")
                mine = [n, r6(sums[0] / n) if n else None, r6(sums[1] / n) if n else None,
                        r6(sums[2] / n) if n else None]
                if ref is None:
                    cross["stable8_2019_cells"]["mismatch"].append([f"{d}|2019|{s}", mine, "missing in frozen"])
                    continue
                theirs = [ref[fields[0]], ref[fields[1]], ref[fields[2]], ref[fields[3]]]
                if mine[0] != theirs[0] or any(abs((a if a is not None else -1)
                                                   - (b if b is not None else -2)) > 1e-6
                                               for a, b in zip(mine[1:], theirs[1:])):
                    cross["stable8_2019_cells"]["mismatch"].append([f"{d}|2019|{s}", mine, theirs])
    if os.path.exists(FROZEN_GAP):
        with open(FROZEN_GAP, encoding="utf-8") as fh:
            fg = json.load(fh)
        for BY in BASE_YEARS:
            for Y in WINDOW_ENDS:
                for m in METRICS:
                    key = f"{BY}|{START_YEAR}->{Y}|{m}"
                    ref = fg["matrix"].get(key)
                    cross["frozen_matrix_18"]["checked"] += 1
                    if ref is None:
                        cross["frozen_matrix_18"]["mismatch"].append([key, "missing in frozen"])
                        continue
                    mine = full_cells[key]
                    if (abs(mine["gap_pp"] - ref["gap_pp"]) > TOL[m]["gap"]
                            or abs(mine["forward"]["rel_change"] - ref["forward"]["rel_change"]) > TOL[m]["rel"]
                            or abs(mine["reverse"]["rel_change"] - ref["reverse"]["rel_change"]) > TOL[m]["rel"]):
                        cross["frozen_matrix_18"]["mismatch"].append(
                            [key, [r6(mine["gap_pp"]), r6(mine["forward"]["rel_change"]),
                                   r6(mine["reverse"]["rel_change"])],
                             [r6(ref["gap_pp"]), r6(ref["forward"]["rel_change"]),
                              r6(ref["reverse"]["rel_change"])]])
        for key, ref in fg["loo"].items():
            mine = both_loo.get(key)
            metric = key.rsplit("|", 1)[-1]
            cross["frozen_loo_126"]["checked"] += 1
            if mine is None or ref is None:
                cross["frozen_loo_126"]["mismatch"].append(
                    [key, r6(mine) if mine is not None else None, r6(ref["gap_pp"]) if ref else None])
                continue
            if abs(mine - ref["gap_pp"]) > TOL[metric]["gap"]:
                cross["frozen_loo_126"]["mismatch"].append([key, r6(mine), r6(ref["gap_pp"])])
        cross["support_lists"]["checked"] += 3
        if sorted(fg["support"]) != support_bidi:
            cross["support_lists"]["mismatch"].append(["bidirectional_support", support_bidi, fg["support"]])
        if sorted(fg["support"]) != support_g1:
            cross["support_lists"]["mismatch"].append(["support_rules_disagree", support_g1, fg["support"]])
        if os.path.exists(FROZEN_BOOTSTRAP):
            with open(FROZEN_BOOTSTRAP, encoding="utf-8") as fh:
                fb2 = json.load(fh)
            if sorted(fb2["support"]["sources"]) != support_g1:
                cross["support_lists"]["mismatch"].append(
                    ["gate1_support", support_g1, fb2["support"]["sources"]])
    for name, blk in cross.items():
        if not isinstance(blk, dict):
            continue
        print(f"      cross-check {name}: checked={blk['checked']} mismatches={len(blk['mismatch'])}",
              flush=True)
        for item in blk["mismatch"][:5]:
            print(f"        mismatch: {json.dumps(item, ensure_ascii=False, default=str)[:400]}",
                  flush=True)

    # ---- output ----------------------------------------------------------------
    result = {
        "task": "Minimal sensitivity analysis for the bidirectional asymmetry",
        "script": "research/nature/asymmetry_sensitivity.py",
        "input": {
            "database": os.path.relpath(ecdb.db_path(), ROOT).replace(os.sep, "/"),
            "access": "SQLite read-only URI (ecdb.raw_sql default); no writes",
            "meta_sql": " ".join(META_SQL.split()),
            "refs_sql": " ".join(REFS_SQL.split()),
            "paper_cit_edges_used": False,
            "reused_from": ("research/nature/paper_bootstrap_asymmetry.py (imported for CANON, "
                            "STABLE8, SEED and helpers; its two extraction SELECTs are extended in "
                            "the same single pass, so no extra full-DB queries)"),
            "frozen_cross_check_inputs": [
                "research/nature/out/paper_bootstrap_asymmetry.json (read-only)",
                "research/nature/out/stable8_merged.json (read-only)",
                "research/nature/out/bidirectional_asymmetry.json (read-only)",
            ],
        },
        "disclaimer": {
            "zh": ("本包是最小敏感性分析组，全部为按已锁定估计规范进行的只读点估计重算，不新增不确定性区间，"
                   "不改变论文级分层重抽的结论表述。低置信队列对比是标签队列稳健性检查（不是校正）；"
                   "共同来源留一是来源构成敏感性（TFS 反向样本量极小，其读数本身不稳定）；解析率诊断是描述性覆盖"
                   "检查，不能当成校正；2025 为右删失端点，须与 2024 并读；gap 为非配对描述性比较。"),
            "en": ("Minimal sensitivity analysis: read-only point-estimate recomputations under locked "
                   "definitions only; no new uncertainty intervals and no change to the paper-level "
                   "resampling statements. The low-confidence queue contrast is a "
                   "label-queue robustness check (not a correction); the common-source leave-one-out "
                   "is a source-composition sensitivity (TFS reverse pools are tiny and individually "
                   "unstable); the parse-rate diagnostic is a descriptive coverage check and must not "
                   "be used as a correction; 2025 is right-censored and must be read next to 2024; the "
                   "gap is a non-paired descriptive comparison."),
        },
        "spec": {
            "scope_years": list(SCOPE_YEARS),
            "gate1_support_years": list(GATE1_YEARS),
            "bidirectional_support_years": list(BIDI_YEARS),
            "window_start_year": START_YEAR,
            "window_ends": list(WINDOW_ENDS),
            "base_years": list(BASE_YEARS),
            "metrics": {
                "E1": "mean target edges per citing paper",
                "E2": "share of citing papers with >= 1 target edge",
                "E3": "mean share of DOI-resolved references pointing at the target; zero-DOI-reference papers contribute 0.0",
            },
            "directions": {"forward": "NON_EC citing papers -> EC target",
                           "reverse": "EC citing papers -> NON_EC target"},
            "gap_definition": "100 * (reverse relative change - forward relative change), percentage points",
            "weighting": "per base year: source composition weights over the support, renormalised over available strata",
            "low_conf_queue": {"predicate": f"tier='{LOWCONF_TIER}' AND confidence<{LOWCONF_THRESHOLD}",
                               "pre_registered_queue": LOWCONF_QUEUE_FILE,
                               "frozen": True},
            "seed_reused": SEED,
            "no_new_resampling": True,
        },
        "sample_sizes": {
            "in_scope_papers_by_direction_year_support": {
                f"{d}|{y}": sum(counts_full.get((d, y, s), 0) for s in support_bidi)
                for d in DIRECTIONS for y in SCOPE_YEARS},
            "per_cell_n_all_stable8_in_scope_years": {
                f"{d}|{y}|{s}": counts_full[(d, y, s)]
                for (d, y, s) in sorted(counts_full)},
        },
        "s1_gate1_replica": s1,
        "s2_low_confidence_queue": s2,
        "s3_reverse_loo": s3,
        "s4_base_period_endpoint_summary": s4,
        "s5_reference_doi_diagnostics": s5,
        "cross_check": cross,
        "limitations": [
            "All numbers are point estimates under frozen definitions; this package adds no uncertainty intervals and no coverage claims.",
            "Low-confidence exclusion (tier='llm' & confidence<0.75) is a robustness contrast, not a label correction; the queue is pre-registered and not manually reviewed here.",
            "The 'full_excluded' variant deletes edges whose target is a queue paper (and can flip a paper's E2 to 0); it does not relabel targets, so the true effect of label error could differ in either direction.",
            "Common-source leave-one-source-out reduces the same support source in both directions and renormalises each direction separately; it is a source-composition sensitivity and does not address source-selection uncertainty in general.",
            "TFS reverse pools have 9-18 papers per scope year (18 in 2019, 11 in 2021, 10 in 2024, 9 in 2025); both the full and dropped variants rest on a handful of extreme papers.",
            "Reference-DOI availability and denominator coverage are descriptive; no imputation, reweighting or scaling is performed, and no bias bound is claimed (missing DOIs are not missing at random).",
            "E1/E2 edges also require the cited side's DOI to match an in-corpus paper, so the parse-rate exposure is shared by all three estimators.",
            "2025 is right-censored; every 2025 window and endpoint number must be read next to its 2024 counterpart.",
            "The forward and reverse pools are non-paired; every gap is a descriptive between-pool comparison.",
            "Composition weights change between base years by design (that is what the base-period summary measures); weights under exclusion are recomputed from retained papers and reported alongside the frozen-weight variant.",
            "Database untouched: the two SELECTs are read-only via ecdb.raw_sql; no build/enrich/cite writes were executed.",
        ],
    }

    print("[summary] S1 paper-level consistency check:", flush=True)
    for win, row in s1["point_estimates"].items():
        print("      " + win + ": " + "; ".join(f"{m} gap={row[m]['gap_pp']}pp" for m in METRICS))
    print("[summary] S2 low-confidence queue:", flush=True)
    for d in DIRECTIONS:
        print(f"      {d}: queue n={inv[d]['total']}, per_year="
              f"{ {k: v['n'] for k, v in inv[d]['per_year'].items()} }")
    for mode in ("unit_excluded", "full_excluded"):
        blk = s2["variants"][mode]
        parts = [f"{win} " + "/".join(f"{m}={blk['point_estimates'][win][m]['gap_pp']}"
                                      for m in METRICS)
                 for win in blk["point_estimates"]]
        print(f"      {mode}: support_same={blk['support_unchanged_vs_full']}; " + "; ".join(parts))
    print(f"[summary] S3 common-source LOO (TFS dropped): min={rev_loo[tfs]['gap_min_pp']} "
          f"max={rev_loo[tfs]['gap_max_pp']} all_positive={rev_loo[tfs]['all_gaps_positive']}",
          flush=True)
    print(f"[summary] S4 matrix: {s4['summary']['n_cells']} cells, gap range "
          f"{s4['summary']['gap_min_pp']}..{s4['summary']['gap_max_pp']}pp, "
          f"all_positive={s4['summary']['all_gaps_positive']}", flush=True)
    print("[summary] S5 DOI row rate (support only): " + "; ".join(
        f"{k}={v['doi_row_rate']}" for k, v in pooled.items()), flush=True)

    if args.no_write:
        print("--no-write: JSON not written", flush=True)
    else:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        print(f"written: {os.path.relpath(OUT, ROOT)}", flush=True)
    print(f"total elapsed: {time.time()-t_start:.1f}s", flush=True)


if __name__ == "__main__":
    main()
