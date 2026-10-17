# One-way decoupling of a field's citation exchange at its output peak

Analysis code, frozen outputs, and derived data for the paper:

> Wenhua Li, Rui Wang, Tao Zhang, Xin Lu. *One-way decoupling of a field's citation exchange at its output peak.* (2026)

The paper measures how the citation exchange between a scientific field
(evolutionary computation) and its neighbouring literatures changes while the
field is at its output peak, under a controlled within-corpus design: one
curated bibliographic corpus of 146,785 papers (2000–2025) in which the field
(47,834 papers) and comparison literatures are observed under identical
collection criteria, citation windows, and indicator algorithms.

## What's new in v2.0.0 (2026-10-17)

1. **Erratum — Supplementary Table 6, "C2 composition sensitivity"**: the
   −20.2% / −30.3% pair was labelled as the per-paper rate (E1) in the
   NHB-submitted SI; it is the participation share (E2). Corrected values for
   both estimands are now registered and tabulated (E1: −22.7% / −37.4%). Full
   record: [`ERRATA.md`](ERRATA.md). Repository v1.0.0 did not contain the
   mislabelled row; nothing previously published here was altered.
2. **Newly collected OpenAlex panels** (`research/panels/`): a second,
   wide-area corpus harvested from OpenAlex (CC0) — 13 sources across
   economics, mathematics and psychology (~27.4k works, raw per-source JSONL in
   `data/`, collection client `oa_client.py` + `panel_download.py`, source
   registry `sources.json`), together with the analysis scripts
   (`panels_ladder.py`, `control_boundary_v2.py`,
   `defect_injection_validation.py`) and frozen outputs (`out/`). These panels
   support the cross-corpus portability analyses of the revised manuscript in
   preparation.
3. Registry and doc-index rows for the corrected C2 analysis (Q57/Q58) added
   to `research/nature/NUMBERS.md`, `paper/build/doc_ids.md` and
   `paper/si/tables/s13_registry_index.*`.

## Repository layout

| Path | Contents |
|---|---|
| `research/nature/*.py` | Analysis scripts (one reading family per script; Chinese docstrings state the exact operational definition, input fields, and output paths) |
| `research/nature/out/*.json` | **Frozen analysis outputs** — every number in the paper is produced by these files |
| `research/nature/figs/make_figs.py` | Figure-generation pipeline for the 5 main figures and 10 Extended Data figures (reads only frozen outputs) |
| `research/nature/figs/*.png|*.pdf` | Published figures as rendered |
| `research/nature/NUMBERS.md` | The number registry: every quantitative statement in the paper, its value, producing script, output file, and field path |
| `research/drafts/verify_numbers.py` | Machine cross-check of the manuscript against the registry |
| `paper/build/make_tables.py` | Generates the 13 supplementary tables (CSV + LaTeX) from the frozen outputs — no hand-entered numbers |
| `paper/si/tables/*.csv` | Per-table source data (Supplementary Tables 1–13) |
| `archive/packages/*/out/*.json` | Frozen outputs of auxiliary analysis packages consumed by the figure pipeline (read-only) |
| `research/panels/` | **(v2.0.0)** OpenAlex wide-area panels: raw per-source JSONL (`data/`), collection client and source registry, analysis scripts, frozen outputs (`out/`) |
| `ecdb/`, `eccite/`, `ecdomain/` | Corpus-construction pipeline (see below) — source code only, no data |
| `docs/` | `DATA_USAGE.md` (field dictionary, 12 statistical caveats), `DATA_PIPELINE.md` (data sources, cleaning rules, backup/restore) |

Some comments reference internal working documents that are not part of this
repository; they document provenance decisions only.

## Two reproduction layers

**Layer 1 — outputs to tables and figures (no database required).**

```bash
python paper/build/make_tables.py            # rebuilds all 13 supplementary tables from out/*.json
python research/nature/figs/make_figs.py     # rebuilds all figures from frozen outputs
python research/drafts/verify_numbers.py     # cross-checks the manuscript against the registry
```

Requirements: Python 3.10+, `numpy`, `matplotlib` (figures only). Table
generation uses the standard library only.

**Layer 2 — rebuilding the corpus and rerunning the analyses.**

The raw bibliographic records are **not** redistributed here (source licence
terms); the corpus is rebuilt from public bibliographic sources using the
pipeline in `ecdb/`, `eccite/`, and `ecdomain/`, following
`docs/DATA_PIPELINE.md`. The pipeline joins records by DOI, de-duplicates
across Crossref / Semantic Scholar / OpenCitations, assigns domain labels by a
two-stage venue + content pass (97% agreement on a 200-paper hand-checked gold
standard), and yields the in-corpus citation-edge table. Once the database is
rebuilt, each analysis script in `research/nature/` runs standalone and writes
its own `out/*.json`.

## Data availability statement (as in the manuscript)

The bibliographic corpus was assembled from public bibliographic records, as
described in the Methods and Supplementary Methods. The derived data supporting
the findings (frozen analysis outputs and per-table source data) are in this
repository.

## Licence

- **Code** (everything under `ecdb/`, `eccite/`, `ecdomain/`, `research/`,
  `paper/build/`): MIT — see `LICENSE`.
- **Derived data** (`research/nature/out/`, `paper/si/tables/`,
  `archive/packages/*/out/`, figures): CC BY 4.0 — see `LICENSE-DATA.md`.
- **OpenAlex panel raw records** (`research/panels/data/`): redistributed
  under OpenAlex's CC0 terms; collection code remains MIT and derived outputs
  (`research/panels/out/`) remain CC BY 4.0.

## Citation

See `CITATION.cff`. Please cite the paper when it is published; cite this
repository version for reproducibility.

## Contact

Corresponding author: Rui Wang (ruiwangnudt@gmail.com).
