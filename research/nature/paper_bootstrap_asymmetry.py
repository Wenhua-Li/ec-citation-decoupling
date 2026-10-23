# -*- coding: utf-8 -*-
"""Paper-level stratified resampling of the bidirectional gap (2026-10-15).

Read-only downstream analysis.  Exactly two SELECTs touch the database:

  1) one meta SELECT (papers JOIN paper_domain): accession_no / pub_year /
     source / label / tier / confidence per paper;
  2) one conditional aggregation over paper_refs_out (LEFT JOIN papers ON
     doi, LEFT JOIN paper_domain): per citing paper, edges into EC, edges into
     NON_EC, and the DOI-reference denominator COUNT(DISTINCT cited_doi).

``paper_cit_edges`` is NOT used (DOCS/DATA_USAGE.md note 10); the E3 denominator
is the distinct-DOI reference count, matching stable8_merged.py.

Scope: canonical merged names (CANON) restricted to the frozen STABLE8 set,
years 2021 / 2024 / 2025, labels EC (reverse pool: EC -> NON_EC) and NON_EC
(forward pool: NON_EC -> EC).  Support = sources with a non-empty paper pool in
ALL of 2021/2024/2025 in BOTH directions (empirically the registered 7-source
common support; Computers and Industrial Engineering drops out, its collection
ends 2021).

Paper-level resampling design:
  * resampling unit = CITING PAPER (its edge counts and DOI-reference
    denominator move together); edges are never treated as independent samples;
  * strata = direction x year x source; within each stratum papers are drawn
    with replacement, stratum size held fixed;
  * fixed 2021 composition weights (per direction, over the support), so the
    comparison holds source mix constant at the 2021 mix;
  * forward and reverse paper pools are resampled INDEPENDENTLY (non-paired):
    separate seeded RNG streams, no paper or stratum is matched across
    directions;
  * gap window = 2021 -> Y for Y in {2024, 2025}; metrics E1 (mean target
    edges per paper), E2 (share of papers with >= 1 target edge), E3 (mean
    share of DOI-resolved references pointing at the target; papers with zero
    DOI references contribute 0.0 and stay in the E1/E2/E3 denominators,
    matching stable8_merged.py);
  * fixed seed, REPS = 4000 (>= the registered minimum of 2000).

The emitted q025/q50/q975 are percentile intervals of the paper-resampling
distribution only.  They are NOT an automatic 95% confidence interval and
carry no frequentist coverage guarantee; source-selection, labeling and
reference-parsing uncertainty are outside the resampling model.

Output: research/nature/out/paper_bootstrap_asymmetry.json (new file; frozen
outputs stable8_merged.json / bidirectional_asymmetry.json are read-only
cross-check inputs and are never written).

Usage:
  python research/nature/paper_bootstrap_asymmetry.py                 # full run
  python research/nature/paper_bootstrap_asymmetry.py --probe         # 100 reps, no write
"""
import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ecdb
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "paper_bootstrap_asymmetry.json")
FROZEN_STABLE8 = os.path.join(HERE, "out", "stable8_merged.json")
FROZEN_GAP = os.path.join(HERE, "out", "bidirectional_asymmetry.json")

# --- frozen definitions (copied verbatim from stable8_merged.py) --------------
CANON = {
    "Applied Soft Computing Journal": "Applied Soft Computing",  # same journal, EI title variant
    "Information sciences": "Information Sciences",              # case variant, 99 papers, year 2000 only
    "Computers & Operations Research": "Computers and Operations Research",  # ampersand variant, 1 paper, 2000
}
STABLE8 = {
    "Applied Soft Computing",
    "Computers and Industrial Engineering",
    "Computers and Operations Research",
    "Engineering Applications of Artificial Intelligence",
    "European Journal of Operational Research",
    "Expert Systems with Applications",
    "IEEE Transactions on Fuzzy Systems",
    "Information Sciences",
}

SEED = 20261015
SEED_FORWARD = [SEED, 1]
SEED_REVERSE = [SEED, 2]
REPS = 4000          # >= registered minimum of 2000
CHUNK = 1000         # replicate chunk size for vectorised resampling
START_YEAR = 2021
WINDOW_ENDS = (2024, 2025)
SCOPE_YEARS = (START_YEAR, 2024, 2025)
METRICS = ("E1", "E2", "E3")
M_IDX = {m: i for i, m in enumerate(METRICS)}
CENSORED_YEARS = (2025,)
DIRECTIONS = ("forward", "reverse")
TARGET_LABEL = {"forward": "EC", "reverse": "NON_EC"}

META_SQL = (
    "SELECT p.accession_no AS acc, p.pub_year AS y, p.source AS src, "
    "d.label AS lab, d.tier AS tier, d.confidence AS conf "
    "FROM papers p JOIN paper_domain d ON d.accession_no = p.accession_no"
)
REFS_SQL = (
    "SELECT r.accession_no AS acc, "
    "COUNT(DISTINCT CASE WHEN d.label='EC' THEN pc.accession_no END) AS n_ec, "
    "COUNT(DISTINCT CASE WHEN d.label='NON_EC' THEN pc.accession_no END) AS n_non, "
    "COUNT(DISTINCT r.cited_doi) AS n_refs_doi "
    "FROM paper_refs_out r "
    "LEFT JOIN papers pc ON pc.doi = r.cited_doi "
    "LEFT JOIN paper_domain d ON d.accession_no = pc.accession_no "
    "WHERE r.cited_doi IS NOT NULL "
    "GROUP BY r.accession_no"
)


def r6(x):
    return None if x is None else round(float(x), 6)


def r4(x):
    return None if x is None else round(float(x), 4)


def quantiles(values):
    if values.size == 0:
        return {"q025": None, "q50": None, "q975": None}
    qs = np.quantile(values, [0.025, 0.5, 0.975])  # linear interpolation, as in bidirectional_asymmetry.py
    return {"q025": r6(qs[0]), "q50": r6(qs[1]), "q975": r6(qs[2])}


def main():
    ap = argparse.ArgumentParser(description="Paper-level stratified resampling")
    ap.add_argument("--reps", type=int, default=REPS, help=f"replicates (default {REPS})")
    ap.add_argument("--probe", action="store_true", help="100 reps, print summary, write nothing")
    ap.add_argument("--no-write", action="store_true", help="run at full reps but do not write the JSON")
    args = ap.parse_args()
    reps = 100 if args.probe else args.reps
    t_start = time.time()

    # ---- query 1: meta (single SELECT) --------------------------------------
    t0 = time.time()
    meta = {}
    for r in ecdb.raw_sql(META_SQL, max_rows=200000)["rows"]:
        meta[r["acc"]] = {
            "y": r["y"],
            "src": CANON.get(r["src"], r["src"]),
            "lab": r["lab"],
            "tier": r["tier"],
            "conf": r["conf"],
        }
    print(f"[1/5] meta rows: {len(meta)}  ({time.time()-t0:.1f}s)", flush=True)

    # ---- query 2: conditional aggregation (single SELECT) --------------------
    t0 = time.time()
    agg = {}
    for r in ecdb.raw_sql(REFS_SQL, max_rows=300000)["rows"]:
        agg[r["acc"]] = (int(r["n_ec"]), int(r["n_non"]), int(r["n_refs_doi"]))
    print(f"[2/5] refs aggregate rows: {len(agg)}  ({time.time()-t0:.1f}s)", flush=True)

    # ---- per-paper records ---------------------------------------------------
    records = defaultdict(list)          # (direction, year, source) -> [(acc, e1, e2, e3)]
    tier_counts = defaultdict(Counter)   # stratum -> Counter(tier)
    conf_min = {}                        # stratum -> min confidence (None excluded)
    refs_sum = defaultdict(int)          # stratum -> sum of DOI-reference denominators
    n_zero_refs = 0
    for acc, m in meta.items():
        y, src, lab = m["y"], m["src"], m["lab"]
        if y not in SCOPE_YEARS or src not in STABLE8:
            continue
        d = "forward" if lab == "NON_EC" else "reverse"
        n_ec, n_non, n_refs = agg.get(acc, (0, 0, 0))
        edges = n_ec if d == "forward" else n_non
        if n_refs == 0:
            n_zero_refs += 1
        key = (d, y, src)
        records[key].append((acc, float(edges), 1.0 if edges else 0.0,
                             (edges / n_refs) if n_refs else 0.0))
        tier_counts[key][m["tier"]] += 1
        refs_sum[key] += n_refs
        if m["conf"] is not None:
            conf_min[key] = min(conf_min.get(key, 1.0), float(m["conf"]))
    print(f"[3/5] in-scope papers: {sum(len(v) for v in records.values())}; "
          f"papers with zero DOI refs (kept, contribute 0): {n_zero_refs}", flush=True)

    # ---- support: non-empty in all scope years, both directions --------------
    counts = Counter({k: len(v) for k, v in records.items()})
    support = sorted({s for (d, y, s) in records
                      if all(counts[(dd, yy, s)] > 0 for dd in DIRECTIONS for yy in SCOPE_YEARS)})
    excluded = {}
    for (d, y, s), recs in sorted(records.items()):
        if s not in support:
            excluded.setdefault(s, {}).setdefault(str(y), {})[d] = len(recs)
    print(f"      support ({len(support)} sources): {support}", flush=True)
    print(f"      excluded stable8 strata: {excluded}", flush=True)

    # ---- stratum arrays (sorted by accession -> independent of SQL row order) -
    strata = {}
    for d in DIRECTIONS:
        for y in SCOPE_YEARS:
            for s in support:
                recs = sorted(records[(d, y, s)])          # accession order
                strata[(d, y, s)] = np.array([[r[1], r[2], r[3]] for r in recs], dtype=np.float64)

    # ---- fixed 2021 composition weights (per direction) ----------------------
    weights = {}
    for d in DIRECTIONS:
        n21 = [counts[(d, START_YEAR, s)] for s in support]
        tot = sum(n21)
        weights[d] = {s: n / tot for s, n in zip(support, n21)}

    # ---- observed point estimates -------------------------------------------
    obs_A = {}
    for d in DIRECTIONS:
        for y in SCOPE_YEARS:
            v = np.zeros(3)
            for s in support:
                v += weights[d][s] * strata[(d, y, s)].mean(axis=0)
            obs_A[(d, y)] = v
    obs_rel = {d: {Y: obs_A[(d, Y)] / obs_A[(d, START_YEAR)] - 1.0 for Y in WINDOW_ENDS}
               for d in DIRECTIONS}

    # ---- bootstrap: independent, non-paired resampling per direction ---------
    t0 = time.time()

    def resample_means(rng, arr):
        n = arr.shape[0]
        out = np.empty((reps, arr.shape[1]), dtype=np.float64)
        for lo in range(0, reps, CHUNK):
            hi = min(lo + CHUNK, reps)
            idx = rng.integers(0, n, size=(hi - lo, n), dtype=np.int64)
            for m in range(arr.shape[1]):
                out[lo:hi, m] = arr[idx, m].mean(axis=1)
        return out

    res = {}
    for d in DIRECTIONS:
        rng = np.random.default_rng(np.random.SeedSequence(SEED_FORWARD if d == "forward" else SEED_REVERSE))
        for y in SCOPE_YEARS:
            for s in support:
                res[(d, y, s)] = resample_means(rng, strata[(d, y, s)])

    boot_A = {}
    for d in DIRECTIONS:
        for y in SCOPE_YEARS:
            acc = np.zeros((reps, 3), dtype=np.float64)
            for s in support:
                acc += weights[d][s] * res[(d, y, s)]
            boot_A[(d, y)] = acc

    boot_rel = {}
    for d in DIRECTIONS:
        base = boot_A[(d, START_YEAR)]
        for Y in WINDOW_ENDS:
            with np.errstate(divide="ignore", invalid="ignore"):
                boot_rel[(d, Y)] = np.where(base > 0, boot_A[(d, Y)] / np.where(base > 0, base, 1.0) - 1.0,
                                            np.nan)
    print(f"[4/5] bootstrap: {reps} replicates x {len(DIRECTIONS)} directions x "
          f"{len(SCOPE_YEARS)*len(support)} strata  ({time.time()-t0:.1f}s)", flush=True)

    bootstrap = {}
    for Y in WINDOW_ENDS:
        window = f"{START_YEAR}->{Y}"
        for m in METRICS:
            i = M_IDX[m]
            f = boot_rel[("forward", Y)][:, i]
            rv = boot_rel[("reverse", Y)][:, i]
            valid = np.isfinite(f) & np.isfinite(rv)
            gap = 100.0 * (rv[valid] - f[valid])
            bootstrap[f"{window}|{m}"] = {
                "window": window,
                "metric": m,
                "right_censored": Y in CENSORED_YEARS,
                "n_reps": reps,
                "n_valid": int(valid.sum()),
                "gap_pp": quantiles(gap),
                "positive_share": r6(float((gap > 0).mean())) if gap.size else None,
                "forward_rel_change": quantiles(f[valid]),
                "reverse_rel_change": quantiles(rv[valid]),
            }

    point_estimates = {}
    for Y in WINDOW_ENDS:
        point_estimates[f"{START_YEAR}->{Y}"] = {
            m: {
                "forward_rel_change": r4(obs_rel["forward"][Y][i]),
                "reverse_rel_change": r4(obs_rel["reverse"][Y][i]),
                "gap_pp": r4(100.0 * (obs_rel["reverse"][Y][i] - obs_rel["forward"][Y][i])),
            }
            for m, i in M_IDX.items()
        }

    # ---- support coverage ----------------------------------------------------
    coverage = {}
    for d in DIRECTIONS:
        cov = {}
        for y in SCOPE_YEARS:
            n_sup = sum(counts[(d, y, s)] for s in support)
            n_all = sum(v for (dd, yy, _s), v in counts.items() if dd == d and yy == y)
            w_sum = sum(weights[d][s] for s in support if counts[(d, y, s)] > 0)
            cov[str(y)] = {
                "n_papers_in_support": n_sup,
                "n_papers_stable8_pool": n_all,
                "share_of_stable8_pool": r6(n_sup / n_all) if n_all else None,
                "weight_sum_2021_weights": r6(w_sum),
            }
        coverage[d] = cov

    strata_out = {}
    for key in sorted(strata):
        d, y, s = key
        arr = strata[key]
        n = arr.shape[0]
        strata_out[f"{d}|{y}|{s}"] = {
            "n": n,
            "tier_counts": dict(sorted(tier_counts[key].items())),
            "min_confidence": r4(conf_min.get(key)),
            "n_edges": int(arr[:, 0].sum()),
            "n_participating": int(arr[:, 1].sum()),
            "n_refs_doi": int(refs_sum[key]),
            "sum_share_of_refs": float(arr[:, 2].sum()),
            "E1": r6(arr[:, 0].mean()),
            "E2": r6(arr[:, 1].mean()),
            "E3": r6(arr[:, 2].mean()),
        }

    # ---- read-only cross-checks against the frozen outputs -------------------
    cross = {
        "point_estimate_check": {"checked": 0, "mismatch": []},
        "per_source_cell_check": {"checked": 0, "mismatch": []},
        "gap_matrix_check": {"checked": 0, "mismatch": []},
    }
    if os.path.exists(FROZEN_STABLE8):
        with open(FROZEN_STABLE8, encoding="utf-8") as fh:
            frozen = json.load(fh)
        for Y in WINDOW_ENDS:
            for d, field in (("forward", "same_support"), ("reverse", "same_support_reverse")):
                fw = frozen[field][str(Y)]["fixed_2021_weights"]
                for m, i in M_IDX.items():
                    cross["point_estimate_check"]["checked"] += 1
                    mine_rel = float(obs_rel[d][Y][i])
                    theirs_rel = fw[m]["rel_change"]
                    mine_b = float(obs_A[(d, START_YEAR)][i])
                    mine_e = float(obs_A[(d, Y)][i])
                    if (theirs_rel is None or abs(mine_rel - theirs_rel) > 5e-5
                            or abs(mine_b - fw[m]["2021"]) > 2e-6
                            or abs(mine_e - fw[m][str(Y)]) > 2e-6):
                        cross["point_estimate_check"]["mismatch"].append(
                            [f"{d}|{START_YEAR}->{Y}|{m}", [mine_b, mine_e, mine_rel],
                             [fw[m]["2021"], fw[m][str(Y)], theirs_rel]])
        fwd_cells = frozen["per_source_e1"]
        rev_cells = frozen["per_source_e1_reverse"]
        for (d, y, s) in sorted(strata):
            cross["per_source_cell_check"]["checked"] += 1
            n = counts[(d, y, s)]
            mean = strata[(d, y, s)].mean(axis=0)
            if d == "forward":
                ref = fwd_cells[f"{y}|{s}"]
                ok = (ref["n_non"] == n
                      and abs(ref["E1"] - mean[0]) <= 1e-6
                      and abs(ref["E2"] - mean[1]) <= 1e-6
                      and abs(ref["E3"] - mean[2]) <= 1e-6)
                if not ok:
                    cross["per_source_cell_check"]["mismatch"].append(
                        [f"{d}|{y}|{s}", [n, *[r6(v) for v in mean]], ref])
            else:
                ref = rev_cells[f"{y}|{s}"]
                arr = strata[(d, y, s)]
                ok = (ref["n_ec"] == n
                      and ref["n_edges_to_non"] == int(arr[:, 0].sum())
                      and ref["n_participating"] == int(arr[:, 1].sum())
                      and ref["n_refs"] == refs_sum[(d, y, s)]
                      and abs(ref["sum_share_of_refs"] - float(arr[:, 2].sum())) <= 1e-9
                      and abs(ref["E1_to_non"] - mean[0]) <= 1e-6
                      and abs(ref["E2_to_non"] - mean[1]) <= 1e-6
                      and abs(ref["E3_to_non"] - mean[2]) <= 1e-6)
                if not ok:
                    cross["per_source_cell_check"]["mismatch"].append([f"{d}|{y}|{s}", ref])
    if os.path.exists(FROZEN_GAP):
        with open(FROZEN_GAP, encoding="utf-8") as fh:
            frozen_gap = json.load(fh)
        for Y in WINDOW_ENDS:
            for m, i in M_IDX.items():
                key = f"{START_YEAR}|{START_YEAR}->{Y}|{m}"
                if key not in frozen_gap.get("matrix", {}):
                    continue
                cross["gap_matrix_check"]["checked"] += 1
                mine = 100.0 * float(obs_rel["reverse"][Y][i] - obs_rel["forward"][Y][i])
                theirs = frozen_gap["matrix"][key]["gap_pp"]
                if abs(mine - theirs) > 1e-3:
                    cross["gap_matrix_check"]["mismatch"].append([key, mine, theirs])
    for name, block in cross.items():
        print(f"      cross-check {name}: checked={block['checked']} "
              f"mismatches={len(block['mismatch'])}", flush=True)

    # ---- output --------------------------------------------------------------
    result = {
        "task": "Paper-level stratified resampling of the reverse-forward asymmetry gap",
        "script": "research/nature/paper_bootstrap_asymmetry.py",
        "input": {
            "database": os.path.relpath(ecdb.db_path(), ROOT).replace(os.sep, "/"),
            "access": "SQLite read-only URI (ecdb.raw_sql default); no writes",
            "meta_sql": " ".join(META_SQL.split()),
            "refs_sql": " ".join(REFS_SQL.split()),
            "paper_cit_edges_used": False,
            "cross_check_inputs": [
                "research/nature/out/stable8_merged.json (read-only)",
                "research/nature/out/bidirectional_asymmetry.json (read-only)",
            ],
        },
        "disclaimer": {
            "zh": ("本输出是论文级分层 bootstrap：在 方向×年份×刊源 分层内对引用论文有放回重抽，每篇论文"
                   "的到EC/到NON边数与 DOI 参考文献分母一起被重抽，边不作为独立样本；正向（NON_EC 引用论文池）"
                   "与反向（EC 引用论文池）相互独立、非配对。q025/q50/q975 只是该重抽分布的分位区间，不是自动 "
                   "95% 置信区间，也不承诺频率派覆盖；刊源选择、领域标注与参考文献解析的不确定性不在重抽模型内。"
                   "2025 端点为右删失年份，其窗口结果须与 2024 端点并读。"),
            "en": ("Paper-level stratified bootstrap: citing papers are resampled with replacement within "
                   "direction x year x source strata, each paper carrying its own edge counts and DOI-reference "
                   "denominator together (edges are never independent samples); forward (NON_EC citing) and "
                   "reverse (EC citing) pools are resampled independently and are not paired. q025/q50/q975 are "
                   "percentile intervals of this resampling distribution only - NOT an automatic 95% confidence "
                   "interval, with no frequentist coverage guarantee. Source selection, domain labeling and "
                   "reference-parsing uncertainty lie outside the resampling model. 2025 is right-censored; read "
                   "it next to the 2024 endpoint."),
        },
        "spec": {
            "start_year": START_YEAR,
            "windows": [f"{START_YEAR}->{Y}" for Y in WINDOW_ENDS],
            "metrics": {
                "E1": "mean target edges per citing paper",
                "E2": "share of citing papers with >= 1 target edge",
                "E3": "mean share of DOI-resolved references pointing at the target; papers with zero DOI refs contribute 0.0 and stay in the denominators",
            },
            "strata": "direction x year x canonical source",
            "resampling_unit": "citing paper (edges and DOI-reference denominator resampled together)",
            "weighting": "fixed 2021 composition weights per direction over the support, renormalised over available strata",
            "pairing": "forward and reverse pools are non-paired; independent seeded RNG streams",
            "reps": reps,
            "seed": SEED,
            "seed_forward": SEED_FORWARD,
            "seed_reverse": SEED_REVERSE,
            "quantile_method": "linear interpolation",
            "e3_denominator": "COUNT(DISTINCT cited_doi) per citing paper",
        },
        "support": {
            "rule": "canonical source with non-empty paper pool in 2021, 2024 and 2025 in BOTH directions",
            "sources": support,
            "n_sources": len(support),
            "excluded_stable8_strata_counts": excluded,
            "weights_2021": {d: {s: r6(w) for s, w in weights[d].items()} for d in DIRECTIONS},
            "coverage": coverage,
        },
        "strata": strata_out,
        "point_estimates": point_estimates,
        "bootstrap": bootstrap,
        "endpoint_censoring": {
            "censored_endpoint_years": list(CENSORED_YEARS),
            "note": ("2025 is the final collection year (right censoring). Every 2021->2025 number mixes trend "
                     "with truncation and must be read next to its 2021->2024 counterpart (registered full-run "
                     "sensitivity ~13 pp of extra decline on 2021->2025 vs 2021->2024, same sign in both "
                     "directions)."),
        },
        "cross_check": cross,
        "limitations": [
            "Composition is frozen at the 2021 mix (fixed 2021 weights); source-mix shifts in 2024/2025 are intentionally not re-sampled.",
            "Papers from sources outside the support (notably Computers and Industrial Engineering, collection ends 2021) are excluded; coverage share is reported per direction and year.",
            "Resampling models within-stratum variability of the citing-paper pool only; labeling (LLM-tier), source-selection and reference-parsing uncertainty are outside the model.",
            "Percentile intervals only; no bias correction (no BCa, no studentisation) and no coverage claim.",
            "Forward and reverse pools differ in size and coverage; they are treated as independent (non-paired) in every replicate.",
            "E3 uses DOI-resolved references only; papers with zero DOI references contribute 0.0 and remain in all E1/E2/E3 denominators (matches stable8_merged.py).",
            "Edge counts are distinct cited in-corpus papers per citing paper (COUNT(DISTINCT pc.accession_no)); edges within one paper move together under resampling.",
        ],
    }

    print("[5/5] summary:", flush=True)
    for key, blk in bootstrap.items():
        print(f"      {key}: gap_pp q025/q50/q975 = {blk['gap_pp']['q025']}/{blk['gap_pp']['q50']}/"
              f"{blk['gap_pp']['q975']}, positive_share={blk['positive_share']}, "
              f"n_valid={blk['n_valid']}/{blk['n_reps']}", flush=True)
    for win, row in point_estimates.items():
        print(f"      point {win}: " + "; ".join(
            f"{m} fwd={row[m]['forward_rel_change']} rev={row[m]['reverse_rel_change']} gap={row[m]['gap_pp']}pp"
            for m in METRICS), flush=True)

    if args.probe or args.no_write:
        print("probe/no-write mode: JSON not written", flush=True)
    else:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        print(f"written: {os.path.relpath(OUT, ROOT)}", flush=True)
    print(f"total elapsed: {time.time()-t_start:.1f}s (reps={reps})", flush=True)


if __name__ == "__main__":
    main()
