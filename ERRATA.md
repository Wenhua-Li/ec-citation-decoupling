# Errata

## 2026-10-17 — Supplementary Table 6 ("C2 composition sensitivity"): estimand labelling corrected

**What was wrong.** In the version of Supplementary Table 6 (S06) submitted with
the NHB version of this work, the row "C2 composition sensitivity" reported the
pair **0.291 → 0.232 (−20.2%)** (source-standardized) and **0.291 → 0.203
(−30.3%)** (topic-standardized) under a per-paper-rate ("edges per paper")
reading. These two values are in fact the **participation share** (the share of
citing papers with at least one target-domain edge, estimand E2), not the
per-paper edge count (estimand E1). The cause was a counting-unit defect in the
original script (a single DISTINCT clause collapsing the unit of analysis),
found during internal review on 2026-10-14 and recomputed the same day.

**Correct values** (composition weights fixed at 2021; window 2021→2025; source
= `research/nature/c2_composition_sensitivity.py` →
`research/nature/out/c2_composition_sensitivity.json`):

| Estimand | Source-standardized | Topic-standardized |
|---|---|---|
| **E1** — target-domain citation edges per citing paper | 0.830 → 0.642 (**−22.7%**) | 0.830 → 0.520 (**−37.4%**) |
| **E2** — share of citing papers with ≥1 target-domain edge | 0.291 → 0.232 (**−20.2%**) | 0.291 → 0.203 (**−30.3%**) |

Scope notes: the 2025 layer lacks Computers & Industrial Engineering (2021
weight 0.129); this is handled by explicit coverage-share reweighting (0.871),
not silently. This analysis is a sensitivity check and does not replace the
registered main specification.

**Status of the public record.** Repository v1.0.0 (2026-10-06) did not include
the C2 composition-sensitivity row anywhere (the mislabelled row exists only in
the NHB-submitted SI package). v2.0.0 adds the row to
`paper/si/tables/s06_robustness.csv|.tex` and the registry index
`s13_registry_index.csv|.tex` in corrected form, so the public tables now match
the corrected analysis. No value previously published in this repository was
altered; this erratum documents the correction affecting the submitted SI.
