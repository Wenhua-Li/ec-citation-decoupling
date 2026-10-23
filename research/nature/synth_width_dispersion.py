# -*- coding: utf-8 -*-
"""Synthetic-panel test of the dispersion -> width relationship (Phase B, 2026-10-17).

Why this file exists
--------------------
The cross-corpus empirical claim so far is only directional: baseline-choice width
(|Paasche - Laspeyres|) appears larger in corpora with larger cross-source dispersion
of relative changes (EC 12.8pp / OR->ML 143.9pp / OR->evo 2.96pp / econ<->psych
32-35pp). That is a handful of points, and the width has an exact pairwise identity
(U1_formalization.md section 2) in which BOTH cross-source heterogeneity of rates
and weight migration enter multiplicatively. Before the manuscript may write even a
bounded version of "dispersion predicts width", the mapping must be calibrated on
synthetic panels where both drivers are controlled. This script does that at the
population level (aggregate quantities only; no paper-level sampling noise, which is
orthogonal to the identity).

Design (fixed BEFORE running; nothing below is tuned after the fact)
--------------------------------------------------------------------
Strata grid (all combinations):
  * S (number of sources)          : {2, 3, 5, 7, 10}
  * tau (weight-migration level)   : {0.05, 0.2, 0.5}
  * mu_r (mean relative change)    : {0.0, 0.15}
  * sigma_r (dispersion of r_s)    : {0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0}
Replicates per stratum: 4,000. Total panels: 840,000.

Per panel:
  * a_s ~ LogNormal(0, 1)              (baseline source means, heterogeneous levels)
  * u = w(X) ~ Dirichlet(1)            (baseline weights)
  * v = w(Y) ∝ u_s * exp(tau * g_s), g_s iid N(0,1)   (end weights)
  * r_s ~ N(mu_r, sigma_r^2), truncated at r_s >= -0.95; b_s = a_s * (1 + r_s)

Quantities (frozen definitions, U1_formalization.md section 10):
  * L = sum(u*b)/sum(u*a) - 1  (Laspeyres),  P = sum(v*b)/sum(v*a) - 1  (Paasche)
  * width = |P - L|
  * dispersion = sample standard deviation of r_s (all a_s > 0 here, so no
    zero-start exclusion is triggered)
  * migration = 0.5 * sum|v_s - u_s|   (total-variation distance of the weights)

Pre-declared checks
-------------------
  1. Exactness: the signed width equals the pairwise identity of U1 section 2 up to
     float tolerance (max abs error reported; must be < 1e-10).
  2. Limit: at sigma_r = 0.05 and tau = 0.05 the median width must be near zero
     (< 1pp); identical relative changes imply zero width.
  3. Calibration: global and per-(S, tau) Spearman(width, dispersion); decile
     calibration curve of width given dispersion (q10/q50/q90).
  4. Decomposition: R^2 of width ~ dispersion vs width ~ migration vs
     width ~ dispersion + migration vs width ~ dispersion + migration + S
     (linear OLS on the pooled sample; log-log variant as robustness).
  5. Sign diagnostics: P(sign(L) != sign(P) | mixed signs of r_s) vs the same
     probability under consistent signs -- the synthetic counterpart of the
     sign-consistency criterion (proposition 2).

Read-only: no database access, no writes outside research/nature/out/.
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(HERE, "out", "synth_width_dispersion.json")

SEED = 20261017
REPS = 4000
S_GRID = (2, 3, 5, 7, 10)
TAU_GRID = (0.05, 0.2, 0.5)
MU_GRID = (0.0, 0.15)
SIGMA_GRID = (0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0)


def simulate_panel_batch(rng, n, S, tau, mu_r, sigma_r):
    """Draw n panels; return arrays of width, dispersion, migration, sign-mismatch."""
    a = rng.lognormal(0.0, 1.0, size=(n, S))
    u = rng.dirichlet(np.ones(S), size=n)
    g = rng.normal(0.0, 1.0, size=(n, S))
    v = u * np.exp(tau * g)
    v = v / v.sum(axis=1, keepdims=True)
    r = np.maximum(rng.normal(mu_r, sigma_r, size=(n, S)), -0.95)
    b = a * (1.0 + r)

    B0 = (u * a).sum(axis=1)
    L = (u * b).sum(axis=1) / B0 - 1.0
    P = (v * b).sum(axis=1) / (v * a).sum(axis=1) - 1.0
    width = np.abs(P - L)

    # pairwise identity (U1 section 2), vectorized over pairs
    num = np.zeros(n)
    for i in range(S):
        for j in range(i + 1, S):
            num += (v[:, i] * u[:, j] - u[:, i] * v[:, j]) * (b[:, i] * a[:, j] - a[:, i] * b[:, j])
    identity = num / ((v * a).sum(axis=1) * B0)
    identity_err = np.max(np.abs((P - L) - identity))

    dispersion = r.std(axis=1, ddof=1)
    migration = 0.5 * np.abs(v - u).sum(axis=1)
    sign_mismatch = (np.sign(L) != np.sign(P)).astype(float)
    mixed_signs = ((r > 0).any(axis=1) & (r < 0).any(axis=1)).astype(float)
    return width, dispersion, migration, sign_mismatch, mixed_signs, float(identity_err)


def spearman(x, y):
    xr = np.argsort(np.argsort(x))
    yr = np.argsort(np.argsort(y))
    xr = xr - xr.mean()
    yr = yr - yr.mean()
    denom = np.sqrt((xr**2).sum() * (yr**2).sum())
    return float((xr * yr).sum() / denom) if denom else None


def r2(x_cols, y):
    X = np.column_stack([np.ones(len(y))] + x_cols)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    ss_res = float((resid**2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return 1.0 - ss_res / ss_tot if ss_tot else None


def main():
    rng = np.random.default_rng(SEED)
    strata = {}
    max_identity_err = 0.0
    all_w, all_d, all_m, all_sign, all_mixed, all_S = [], [], [], [], [], []
    for S in S_GRID:
        for tau in TAU_GRID:
            for mu in MU_GRID:
                for sigma in SIGMA_GRID:
                    w, d, m, sm, mx, err = simulate_panel_batch(rng, REPS, S, tau, mu, sigma)
                    max_identity_err = max(max_identity_err, err)
                    key = f"S{S}|tau{tau}|mu{mu}|sigma{sigma}"
                    strata[key] = {
                        "spearman_width_dispersion": spearman(d, w),
                        "median_width_pp": float(np.median(w) * 100),
                        "median_dispersion": float(np.median(d)),
                    }
                    all_w.append(w)
                    all_d.append(d)
                    all_m.append(m)
                    all_sign.append(sm)
                    all_mixed.append(mx)
                    all_S.append(np.full(len(w), S, dtype=float))

    W = np.concatenate(all_w)
    D = np.concatenate(all_d)
    M = np.concatenate(all_m)
    SIGN = np.concatenate(all_sign)
    MIXED = np.concatenate(all_mixed)
    SARR = np.concatenate(all_S)

    # decile calibration of width given dispersion
    qs = np.quantile(D, np.linspace(0, 1, 11))
    calib = []
    for k in range(10):
        lo, hi = qs[k], qs[k + 1]
        mask = (D >= lo) & (D <= hi) if k == 9 else (D >= lo) & (D < hi)
        if mask.sum() == 0:
            continue
        calib.append({
            "decile": k + 1,
            "dispersion_range": [float(lo), float(hi)],
            "width_pp_q10": float(np.quantile(W[mask], 0.10) * 100),
            "width_pp_q50": float(np.quantile(W[mask], 0.50) * 100),
            "width_pp_q90": float(np.quantile(W[mask], 0.90) * 100),
        })

    # R^2 decomposition (pooled)
    r2_d = r2([D], W)
    r2_m = r2([M], W)
    r2_dm = r2([D, M], W)
    r2_dms = r2([D, M, SARR], W)
    # log-log robustness (strictly positive values only)
    pos = (W > 1e-12) & (D > 1e-12) & (M > 1e-12)
    r2_log_dm = r2([np.log(D[pos]), np.log(M[pos])], np.log(W[pos]))

    # sign diagnostics
    def mismatch_share(mask):
        return float(SIGN[mask].mean()) if mask.sum() else None

    sign_diag = {
        "p_sign_mismatch_given_mixed": mismatch_share(MIXED == 1),
        "p_sign_mismatch_given_consistent": mismatch_share(MIXED == 0),
        "share_mixed": float(MIXED.mean()),
    }

    # per-tau and per-S global Spearman (dispersion -> width); rebuild masks cleanly
    masks_tau = {tau: [] for tau in TAU_GRID}
    masks_S = {S: [] for S in S_GRID}
    pos0 = 0
    for S in S_GRID:
        for tau in TAU_GRID:
            for mu in MU_GRID:
                for sigma in SIGMA_GRID:
                    masks_tau[tau].append(np.arange(pos0, pos0 + REPS))
                    masks_S[S].append(np.arange(pos0, pos0 + REPS))
                    pos0 += REPS
    per_tau = {}
    for tau in TAU_GRID:
        ii = np.concatenate(masks_tau[tau])
        per_tau[str(tau)] = spearman(D[ii], W[ii])
    per_S = {}
    for S in S_GRID:
        ii = np.concatenate(masks_S[S])
        per_S[str(S)] = spearman(D[ii], W[ii])

    low_stratum = strata["S5|tau0.05|mu0.0|sigma0.05"]

    result = {
        "task": "synthetic calibration of dispersion -> baseline-choice width (Phase B)",
        "seed": SEED,
        "reps_per_stratum": REPS,
        "n_panels": int(len(W)),
        "grids": {"S": list(S_GRID), "tau": list(TAU_GRID), "mu_r": list(MU_GRID), "sigma_r": list(SIGMA_GRID)},
        "definitions": {
            "width": "|Paasche - Laspeyres| on the aggregate ratio (U1 section 10)",
            "dispersion": "sample sd of per-source relative changes r_s",
            "migration": "0.5 * sum|w_s(Y) - w_s(X)| (total variation)",
        },
        "checks": {
            "pairwise_identity_max_abs_error": max_identity_err,
            "low_dispersion_low_migration_stratum": low_stratum,
        },
        "global": {
            "spearman_width_dispersion": spearman(D, W),
            "spearman_width_migration": spearman(M, W),
            "r2_width_on_dispersion": r2_d,
            "r2_width_on_migration": r2_m,
            "r2_width_on_dispersion_migration": r2_dm,
            "r2_width_on_dispersion_migration_S": r2_dms,
            "r2_loglog_width_on_dispersion_migration": r2_log_dm,
        },
        "spearman_width_dispersion_by_tau": per_tau,
        "spearman_width_dispersion_by_S": per_S,
        "decile_calibration": calib,
        "sign_diagnostics": sign_diag,
        "width_pp_quantiles_pooled": {
            "q10": float(np.quantile(W, 0.10) * 100),
            "q50": float(np.quantile(W, 0.50) * 100),
            "q90": float(np.quantile(W, 0.90) * 100),
        },
        "notes": [
            "Population-level panels: no paper-level sampling noise; the mapping tested here is between aggregate quantities.",
            "Dispersion alone cannot pin down width: migration enters the pairwise identity multiplicatively; R^2 values quantify the gap.",
            "Zero-start sources (a_s = 0) are not generated here; the frozen rule excludes them from dispersion and reports them separately.",
        ],
    }

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    print(json.dumps({
        "identity_max_err": result["checks"]["pairwise_identity_max_abs_error"],
        "global_spearman_width_dispersion": round(result["global"]["spearman_width_dispersion"], 4),
        "global_spearman_width_migration": round(result["global"]["spearman_width_migration"], 4),
        "r2_d": round(r2_d, 4), "r2_m": round(r2_m, 4), "r2_dm": round(r2_dm, 4), "r2_dms": round(r2_dms, 4),
        "sign_mismatch_mixed": round(sign_diag["p_sign_mismatch_given_mixed"], 4),
        "sign_mismatch_consistent": round(sign_diag["p_sign_mismatch_given_consistent"], 4),
        "low_stratum_median_width_pp": round(low_stratum["median_width_pp"], 4),
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
