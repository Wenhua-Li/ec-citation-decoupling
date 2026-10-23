# The outward turn behind an apparent collapse in cross-field citations

Analysis code, frozen outputs, and derived data supporting the paper:

> Wenhua Li, Rui Wang, Tao Zhang, Xin Lu. *The outward turn behind an apparent
> collapse in cross-field citations.* (2026)

The paper asks whether an aggregate change in cross-field citation can be
compared once the observation conditions are declared — the common source
support, the paper-level estimand, the composition-weight base year and the time
endpoint — using evolutionary computation as a deep-measurement case. It
measures the citation exchange between a scientific field (evolutionary
computation) and its neighbouring literatures inside one curated bibliographic
corpus of 146,785 papers (2000–2025; 47,834 field papers), under a controlled
within-corpus design with identical collection criteria, citation windows and
indicator algorithms. Three paper-level estimands are kept separate throughout —
edge-count intensity (edges per citing paper, E1), participation share (share of
citing papers with at least one cross-domain edge, E2) and cross-domain
reference share (E3) — and are never combined into a single index.

## What changed in v3.0.0 (2026-10-23)

1. **Analysis package for the current manuscript version.** Eighteen new
   analysis scripts cover the measurement framework end to end — a specification
   ladder for source support, exact ratio-width attribution, sign-robustness
   checks, paper- and source-level resampling, leave-one-source-out audits,
   DOI-parsing exposure diagnostics and synthetic calibration — alongside the
   earlier-release scripts whose frozen outputs are still consumed by the current
   figures and registry (including the defect-injection validation behind
   Extended Data Fig. 7). The set now holds 38 analysis scripts and 47 frozen
   outputs under `research/nature/out/`.
2. **New figure set.** Six main and eight Extended Data figures, all regenerated
   from the frozen outputs by a single pipeline
   (`research/nature/figs/make_masterplan_figs.py`), replace the earlier five
   main and ten Extended Data figures. The figure-to-source map is
   `research/nature/figs/FIG_SOURCES.md`.
3. **Registries rebuilt.** The number registry (`research/nature/NUMBERS.md`),
   the quantity index (`paper/build/doc_ids.md`) and the verification tooling
   now bind each reported quantity to its generating script, frozen output and
   field path; 532 registered readings are checked by
   `research/drafts/verify_numbers.py` with zero mismatches.
4. **Wide-area OpenAlex panels extended.** The panels now include the
   20-discipline cross-science atlas (12 field interfaces), tier calibration and
   pre-screening analyses, in addition to the 13 public sources across
   economics, mathematics and psychology.
5. **Errata record updated** where it referred to files that are no longer part
   of this repository (see `ERRATA.md`); the correction itself is unchanged.

Repository contents are versioned; earlier snapshots remain available in the
commit history (the 2026-10-17 release is tag `v2.0.0`).

## Repository layout

| Path | Contents |
|---|---|
| `research/nature/*.py` | Analysis scripts — one reading family per script; most docstrings name the operational definition, input files and output path (the working language is largely Chinese, as in the original project) |
| `research/nature/out/*.json` | **Frozen analysis outputs** (47 files) — the principal frozen outputs behind the paper's readings; quantities from the wide-area panels and the archived analysis packages are bound to `research/panels/out/` and `archive/packages/*/out/` (see `paper/build/doc_ids.md`) |
| `research/nature/figs/make_masterplan_figs.py` | Figure pipeline: reads only frozen outputs, writes `figs/reconstruction/` |
| `research/nature/figs/reconstruction/*.pdf`, `*.png` | Published figures as rendered: six main and eight Extended Data figures |
| `research/nature/figs/FIG_SOURCES.md` | Figure-to-source mapping and caption obligations |
| `research/nature/figs/audit_pdf_fonts.py` | PDF text-size audit for the rendered figures (optional; needs `pypdf`) |
| `research/nature/NUMBERS.md` | Number registry: every quantitative statement, its value, producing script, output file and field path |
| `research/drafts/verify_numbers.py` | Machine cross-check of the number registry, the quantity index and the frozen outputs |
| `research/drafts/numbers_checklist.csv` | Registered-value whitelist used by the cross-check |
| `paper/build/doc_ids.md` | Quantity index: binds each quantity ID to its output file and field path |
| `research/panels/` | OpenAlex wide-area panels: raw per-source JSONL (`data/`, CC0) with per-source completion markers, collection client and source registry (`sources.json`), analysis scripts and frozen outputs (`out/`) |
| `archive/packages/*/out/*.json` | Frozen outputs of auxiliary analysis packages used by the figure pipeline and/or the number registry (read-only) |
| `ecdb/`, `eccite/`, `ecdomain/` | Corpus-construction pipeline — source code only, no data (see below) |
| `docs/` | `DATA_USAGE.md` (field dictionary, statistical caveats) and `DATA_PIPELINE.md` (data sources, cleaning rules, backup/restore) |

Some comments and registry entries reference internal or archived working files
that are not part of this repository; they are retained as provenance and are
not needed to run the released pipeline.

## Two reproduction layers

**Layer 1 — outputs to figures (no database required).**

```bash
python research/nature/figs/make_masterplan_figs.py     # rebuilds all 14 figures from the frozen outputs
python research/drafts/verify_numbers.py                # registry / quantity-index / output consistency
python research/nature/figs/audit_pdf_fonts.py          # optional: PDF text-size audit
```

Requirements: Python 3.10+, `numpy`, `matplotlib` (figures only); `pypdf` for
the optional font audit. The figure pipeline reads only JSON files and never
touches a database. `verify_numbers.py` cross-checks registered values against
the number registry and the quantity index; because the manuscript and
Supplementary Information sources are not part of this repository, the
manuscript-text pass of that script has nothing to scan here and is skipped.

**Layer 2 — rebuilding the corpus and re-running the analyses.**

The raw bibliographic records are **not** redistributed here (source licence
terms). Rebuilding the main corpus requires the licensed bibliographic export
plus the public citation APIs (Crossref / Semantic Scholar / OpenCitations); the
extraction, cleaning, DOI matching and domain-labelling steps are implemented in
`ecdb/`, `eccite/` and `ecdomain/`, and documented in `docs/DATA_PIPELINE.md`,
so that a holder of the same licensed export can rebuild the corpus. The
OpenAlex wide-area panels are CC0 and can be re-collected with the code in
`research/panels/`. Once the database is rebuilt, each analysis script in
`research/nature/` runs standalone and writes its output under
`research/nature/out/`.

## Data availability

The bibliographic corpus was assembled from a licensed bibliographic export
together with public citation APIs, as described in the paper's Methods and
Supplementary Methods; the source list, cleaning rules and backup procedure are
documented in `docs/DATA_PIPELINE.md`. The raw bibliographic records are not
redistributed here (source licence terms). The derived data supporting the
findings — frozen analysis outputs, registry tables and panel records — are in
this repository. Only aggregate statistics are released; author name-level
trajectories are computed for analysis but not published. The manuscript and
Supplementary Information text are not part of this repository. The
bibliographic corpus is available subject to the original source licences.

## Licence

- **Code** (all `*.py` files under `ecdb/`, `eccite/`, `ecdomain/`, `research/`
  and `paper/`): MIT — see `LICENSE`.
- **Derived data, registries and documentation** (`research/nature/out/`,
  `research/nature/NUMBERS.md`, `research/nature/figs/FIG_SOURCES.md`,
  `research/nature/figs/reconstruction/`, `research/drafts/numbers_checklist.csv`,
  `paper/build/doc_ids.md`, `research/panels/out/`, `research/panels/sources.json`,
  `archive/packages/*/out/`, `docs/`): CC BY 4.0 — see `LICENSE-DATA.md`.
- **OpenAlex panel raw records** (`research/panels/data/`): distributed under
  OpenAlex's CC0 terms; the collection code remains MIT and the derived outputs
  (`research/panels/out/`) remain CC BY 4.0.

## Citation

See `CITATION.cff`. Please cite the associated paper and the repository version
or commit you used.

## Contact

Corresponding author: Rui Wang (ruiwangnudt@gmail.com).
