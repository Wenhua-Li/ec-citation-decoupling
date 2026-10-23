# Changelog

All notable changes to the contents of this repository. Earlier snapshots
remain available in the commit history; the 2026-10-17 release is tag `v2.0.0`.

## 3.0.0 — 2026-10-23

Contents updated to the analysis package for the current manuscript version.

- **Analysis scripts**: eighteen new scripts cover the measurement framework end
  to end — specification ladders for source support, exact ratio-width
  attribution, sign-robustness checks, paper- and source-level resampling,
  leave-one-source-out audits, DOI-parsing exposure diagnostics and synthetic
  calibration. The earlier-release scripts whose frozen outputs remain in use
  are retained, including the defect-injection validation behind Extended Data
  Fig. 7 (38 scripts in total).
- **Frozen outputs**: 47 JSON files under `research/nature/out/`; every reported
  number is bound to a frozen JSON in the repository — the principal outputs sit
  here, while panel- and package-derived quantities are bound to
  `research/panels/out/` and `archive/packages/*/out/`.
- **Figures**: a new set of six main and eight Extended Data figures, generated
  from the frozen outputs by a single pipeline
  (`research/nature/figs/make_masterplan_figs.py`). The earlier five main and
  ten Extended Data figures and their pipeline were removed.
- **Registries**: the number registry (`research/nature/NUMBERS.md`) and the
  quantity index (`paper/build/doc_ids.md`) were rebuilt (532 registered
  readings, zero mismatches in the verification script), and the verification
  tooling was updated.
- **Wide-area panels**: the OpenAlex panels now include the 20-discipline
  cross-science atlas (12 field interfaces), tier calibration and pre-screening
  analyses, in addition to the 13 public sources across economics, mathematics
  and psychology.
- **Removed**: the earlier figure set and its pipeline, the per-table CSV/LaTeX
  exports (`paper/si/tables/`), the old table-generation scripts and other
  superseded build and provenance files. The corrected S06 values documented in
  the erratum remain in the number registry (see `ERRATA.md`).
- **Security**: the OpenAlex collection client no longer carries default API
  keys; keys are supplied through the `ECOA_API_KEYS` environment variable.

## 2.0.0 — 2026-10-17

- Erratum for Supplementary Table 6 ("C2 composition sensitivity"): estimand
  labelling corrected — see `ERRATA.md`.
- Newly collected OpenAlex wide-area panels: 13 sources across economics,
  mathematics and psychology (~27.4k works), with raw per-source records,
  collection code and frozen outputs.
- Registry and quantity-index rows for the corrected C2 analysis.

## 1.0.0 — 2026-10-06

- Initial release: analysis code, frozen outputs and derived data.
