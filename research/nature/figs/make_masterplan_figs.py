# -*- coding: utf-8 -*-
"""Master-plan figure set (v3 rewrite, 2026-10-18): 6 main figures + 8 Extended Data.

Reads ONLY frozen JSON outputs under research/nature/out/, research/panels/out/
and archive/packages/*/out/ (by basename). No database access, no writes outside
figs/reconstruction/. All in-figure text is English; minimum font size 7.0 pt;
PDFs are deterministic (CreationDate suppressed) so double runs are byte-identical.

2026-10-19: Nature-grade layout redesign. Data, readings, colour semantics and
file names are unchanged; only layout/typography was reworked (explicit GridSpec
margins, one-line panel headers, halo-shielded annotations, external legends).
"""
import json
import os
import traceback

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle, Patch, Circle, FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
NATURE = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(NATURE, "out")
PANELS_OUT = os.path.join(NATURE, "..", "panels", "out")
ARCH_PKGS = os.path.join(NATURE, "..", "..", "archive", "packages")
FIG_OUT = os.path.join(HERE, "reconstruction")

_search = [OUT, PANELS_OUT]
for _p in ("r3a", "r3b", "r3f", "w6_authors", "w8_funding"):
    _search.append(os.path.join(ARCH_PKGS, _p, "out"))


def load(name):
    for d in _search:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
    raise FileNotFoundError(name)


S8 = load("stable8_merged.json")
BA = load("bidirectional_asymmetry.json")
PB = load("paper_bootstrap_asymmetry.json")
SENS = load("asymmetry_sensitivity.json")
U1 = load("u1_contributions.json")
DOIB = load("doi_bracket.json")
FLD = load("flip_lambda_dual.json")  # fig2d: E3 numerator-only lambda (B version)
SYN = load("synth_width_dispersion.json")
DEC = load("decirc.json")
FM = load("fieldmap.json")
TIER = load("tier_calibration.json")
R3A = load("r3a_results.json")
DUAL = load("subfamily_dual_share.json")  # batch-2 P0-1: dual-scope debut-author shares (Fig 3a)
R3O = load("r3o_quantities.json")
AF = load("authors_flow.json")
FA = load("funding_agenda.json")
DIS = load("disruption.json")
DT = load("doctype_cd.json")
W4A = load("w4a.json")
R3B_CD = load("r3b_cd.json")
R3B_DIMS = load("r3b_dims.json")
MEM = load("memory.json")
TERMS = load("terms.json")
AUTH = load("authors.json")
CHECKS = load("checks.json")
AGE_W1 = load("age_w1.json")
AGE_W2 = load("age_w2.json")
PLAD = load("pilot_ladder.json")
PANL = load("panels_ladder.json")
U3V = load("defect_injection_validation.json")

BLUE, TEAL, ORANGE, AMBER = "#0072B2", "#009E73", "#D55E00", "#E69F00"
GREY, RED, INK = "#8C8C8C", "#B2182B", "#222222"
TIER_FILL = {"full": "#CDE9DC", "e1_tier": "#DCE1E8", "refused": "#F2F2F2"}

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 8.0,
    "axes.titlesize": 8.0, "axes.labelsize": 8.0,
    "xtick.labelsize": 7.0, "ytick.labelsize": 7.0,
    "legend.fontsize": 7.0, "axes.linewidth": 0.7,
    "axes.spines.top": False, "axes.spines.right": False,
    "hatch.linewidth": 0.5,
    "figure.dpi": 160,
})
MM = 1 / 25.4
W_DOUBLE, W_SINGLE = 183 * MM, 89 * MM
HALO = [pe.withStroke(linewidth=2.0, foreground="white")]


def save(fig, name):
    from matplotlib.text import Text
    fig.canvas.draw()
    for t in fig.findobj(Text):
        try:
            if t.get_fontsize() < 7.0:
                t.set_fontsize(7.0)
        except Exception:
            pass
    os.makedirs(FIG_OUT, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(FIG_OUT, f"{name}.{ext}"), format=ext,
                    metadata={"CreationDate": None} if ext == "pdf" else None)
    plt.close(fig)


def header(ax, tag, title, dy=0.055, dx=0.065):
    """Panel header: bold letter + one-line short title, above the axes top-left."""
    ax.text(0.0, 1.0 + dy, tag, transform=ax.transAxes, fontsize=9,
            fontweight="bold", va="bottom", ha="left")
    ax.text(dx, 1.0 + dy, title, transform=ax.transAxes, fontsize=8,
            va="bottom", ha="left")


def htext(ax, x, y, s, halo=True, **kw):
    """Annotation text with a white halo stroke so it never merges with data ink."""
    kw.setdefault("fontsize", 7.0)
    t = ax.text(x, y, s, **kw)
    if halo:
        t.set_path_effects(HALO)
    return t


def pct(x, nd=1):
    return f"{x * 100:+.{nd}f}%"


SRC7 = BA["support"]

SHORT = {
    "Applied Soft Computing": "ASC",
    "Computers and Operations Research": "C&OR",
    "Computers & Operations Research": "C&OR",
    "Engineering Applications of Artificial Intelligence": "EAAI",
    "European Journal of Operational Research": "EJOR",
    "Expert Systems with Applications": "ESWA",
    "IEEE Transactions on Fuzzy Systems": "IEEE TFS",
    "Information Sciences": "InfoSci",
}


def src_rel_change(reverse=False, src=None):
    key = "per_source_e1_reverse" if reverse else "per_source_e1"
    fld = "E1_to_non" if reverse else "E1"
    a = (S8[key][f"2021|{src}"] if reverse else S8[key][f"2021|{src}"])[fld]
    b = (S8[key][f"2024|{src}"])[fld]
    return b / a - 1 if a else float("nan")


# ----------------------------------------------------------------------------
def fig1():
    # 2026-10-20 redesign: 40/28/32 unequal top row, self-contained panel c,
    # caption-tier names in a, legend block dissolved into panels, hatched
    # censored columns in e, journal key + descriptive title in d, and an
    # approved estimand/conditions badge band on top. Data reads unchanged.
    fig = plt.figure(figsize=(W_DOUBLE, 6.6))
    outer = fig.add_gridspec(2, 1, height_ratios=[0.40, 0.60],
                             left=0.168, right=0.975, top=0.90, bottom=0.085,
                             hspace=0.22)

    # badge band: estimand definitions + four declared conditions (approved P2)
    fig.text(0.168, 0.978, "Estimands:  E1 = cross-domain edges per paper   ·   "
                           "E2 = papers with ≥1 cross-domain edge   ·   "
                           "E3 = cross-domain share of references",
             fontsize=7, va="center", ha="left", color=INK)
    pills = ("7-source common support", "declared base weights", "unpaired pools",
             "censored 2025 endpoint read with complete 2024")
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    invf = fig.transFigure.inverted()
    xcur = 0.168
    for lab in pills:
        t = fig.text(xcur, 0.945, lab, fontsize=7, va="center", ha="left",
                     color=INK, bbox=dict(boxstyle="round,pad=0.32", fc="#F4F4F4",
                                          ec="#C2C2C2", lw=0.6))
        bb = t.get_window_extent(renderer=rend)
        x0, _ = invf.transform((bb.x0, bb.y0))
        x1, _ = invf.transform((bb.x1, bb.y1))
        xcur += (x1 - x0) + 0.018

    top = outer[0].subgridspec(1, 3, width_ratios=[40, 28, 32], wspace=0.30)
    bot = outer[1].subgridspec(1, 2, width_ratios=[45, 55], wspace=0.30)

    # (a) forward E1 reading vs specification ladder
    ax = fig.add_subplot(top[0])
    s1_21, s1_24, s1_25 = (S8["s1_single_end_anchor"][y]["E1_mean_edges"]
                           for y in ("2021", "2024", "2025"))
    s2_21, s2_24, s2_25 = (S8["s2_double_end"][y]["E1_within_set_edges_per_non_paper"]
                           for y in ("2021", "2024", "2025"))
    pl_24 = S8["same_support"]["2024"]["pooled"]["rel_change"]
    pl_25 = S8["same_support"]["2025"]["pooled"]["rel_change"]
    fx_24 = S8["same_support"]["2024"]["fixed_2021_weights"]["E1"]["rel_change"]
    fx_25 = S8["same_support"]["2025"]["fixed_2021_weights"]["E1"]["rel_change"]
    rows = [
        ("anchor-restricted", s1_24 / s1_21 - 1, s1_25 / s1_21 - 1),
        ("doubly-restricted", s2_24 / s2_21 - 1, s2_25 / s2_21 - 1),
        ("common-support pooled", pl_24, pl_25),
        ("fixed baseline weights", fx_24, fx_25),
    ]
    y = np.arange(len(rows))[::-1]
    for i, (lab, v24, v25) in enumerate(rows):
        ax.barh(y[i] + 0.19, v24 * 100, height=0.34, color=ORANGE)
        ax.barh(y[i] - 0.19, v25 * 100, height=0.34, color=ORANGE, alpha=0.55,
                hatch="///", edgecolor="white", linewidth=0.4)
        htext(ax, v24 * 100 - 1.0, y[i] + 0.19, pct(v24, 1), ha="right", va="center",
              fontsize=7)
        htext(ax, v25 * 100 - 1.0, y[i] - 0.19, pct(v25, 1), ha="right", va="center",
              color="#777777", fontsize=7)
    ax.set_yticks(y); ax.set_yticklabels([r[0] for r in rows], fontsize=7)
    ax.axvline(0, color=INK, lw=1.0)
    ax.set_xlabel("Outside→EC, E1 change (%)")
    ax.set_xlim(-56, 4); ax.set_ylim(-0.75, 3.55)
    ax.set_xticks([-40, -20, 0])
    ax.text(0.01, 0.03, "solid = 2024\nhatched = 2025 (right-censored)",
            transform=ax.transAxes, fontsize=7, va="bottom", ha="left",
            color="#555555", linespacing=1.45)
    header(ax, "a", "Specification ladder, forward E1")

    # (b) base-year swing
    ax = fig.add_subplot(top[1])
    bases = ("2019", "2021", "2024")
    vals = [S8["baseline_table_forward_2124"][b]["E1"]["rel_change"] for b in bases]
    cols = [TEAL if v > 0 else ORANGE for v in vals]
    ax.bar(np.arange(3), [v * 100 for v in vals], width=0.55, color=cols)
    for i, v in enumerate(vals):
        htext(ax, i, v * 100 + (0.7 if v > 0 else -0.7), pct(v, 1), ha="center",
              va="bottom" if v > 0 else "top", fontsize=7.5)
    ax.axhline(0, color=INK, lw=1.2)
    ax.set_xticks(np.arange(3)); ax.set_xticklabels([f"{b}w" for b in bases])
    ax.set_ylabel("Forward E1 change (%)")
    ax.set_ylim(-20, 12)
    header(ax, "b", "Sign flips with base year")

    # (c) two worlds schematic: per-source lines (left) + identical aggregate (right)
    cspec = top[2].subgridspec(1, 2, width_ratios=[0.60, 0.40], wspace=0.34)
    ax1 = fig.add_subplot(cspec[0])
    ax2 = fig.add_subplot(cspec[1])
    # World A: within-source readings fall (decrease = ochre); World B: rise (teal)
    ax1.plot([0, 1], [1.42, 1.18], color=ORANGE, lw=1.4)
    ax1.plot([0, 1], [1.30, 1.02], color=ORANGE, lw=1.4, ls="--")
    ax1.plot([0, 1], [0.44, 0.70], color=TEAL, lw=1.4)
    ax1.plot([0, 1], [0.26, 0.52], color=TEAL, lw=1.4, ls="--")
    ax1.text(0.03, 1.52, "World A", fontsize=7, color=ORANGE, ha="left", va="center")
    ax1.text(0.03, 0.20, "World B", fontsize=7, color=TEAL, ha="left", va="center")
    ax1.set_xlim(-0.08, 1.12); ax1.set_ylim(0.15, 1.66)
    ax1.set_xticks([0, 1]); ax1.set_xticklabels(["t0", "t1"])
    ax1.set_yticks([])
    ax1.set_ylabel("within-source (schematic)", fontsize=7)
    # identical aggregate bars 1.20 -> 0.92 (-23.3%)
    ax2.bar([0, 1], [1.20, 0.92], width=0.52, color="#9A9A9A", edgecolor="none")
    ax2.annotate("", xy=(1.0, 0.96), xytext=(0.0, 1.24),
                 arrowprops=dict(arrowstyle="->", color=INK, lw=0.8,
                                 shrinkA=2, shrinkB=2))
    ax2.text(0.5, 1.30, "−23.3%", fontsize=7, color=INK, ha="center", va="bottom")
    ax2.text(0.5, 1.48, "identical\naggregate", fontsize=7, color="#555555",
             ha="center", va="center", linespacing=1.4)
    ax2.set_xlim(-0.55, 1.55); ax2.set_ylim(0.15, 1.66)
    ax2.set_xticks([0, 1]); ax2.set_xticklabels(["t0", "t1"])
    ax2.set_yticks([])
    ax2.set_ylabel("aggregate", fontsize=7)
    header(ax1, "c", "Two worlds, one aggregate", dx=0.10)

    # (d) reverse per-source scorecard + journal key
    dcell = bot[0].subgridspec(2, 1, height_ratios=[0.56, 0.44], hspace=0.26)
    ax = fig.add_subplot(dcell[0])
    rel = sorted((src_rel_change(True, s) * 100, s) for s in SRC7)
    y = np.arange(len(rel))
    ax.barh(y, [r[0] for r in rel], height=0.62, color=BLUE)
    for i, (v, s) in enumerate(rel):
        htext(ax, v + 1.2, i, f"+{v:.1f}%", va="center", fontsize=7)
    ax.set_yticks(y); ax.set_yticklabels([SHORT.get(r[1], r[1][:20]) for r in rel], fontsize=7)
    ax.set_xlabel("EC→outside, E1 per source (%)")
    ax.set_xlim(0, 80)
    rev_bases = [S8["baseline_table_reverse_2124"][b]["E1"]["rel_change"] * 100 for b in bases]
    htext(ax, 0.97, 0.05, f"aggregate\n{min(rev_bases):+.1f}%…{max(rev_bases):+.1f}%",
          transform=ax.transAxes, ha="right", va="bottom", color="#555555",
          linespacing=1.5, fontsize=7)
    header(ax, "d", "Reverse E1 by source")
    axk = fig.add_subplot(dcell[1]); axk.axis("off")
    axk.set_xlim(0, 1); axk.set_ylim(0, 1)
    key_lines = (
        "Journal key: ASC Applied Soft Computing",
        "InfoSci Information Sciences",
        "C&OR Computers & Operations Research",
        "ESWA Expert Systems with Applications",
        "EJOR European Journal of Operational Research",
        "IEEE TFS IEEE Transactions on Fuzzy Systems",
        "EAAI Engineering Applications of Artificial Intelligence",
    )
    for i, kl in enumerate(key_lines):
        axk.text(0.0, 0.90 - i * 0.138, kl, fontsize=7, va="top", ha="left",
                 color="#555555", clip_on=False)

    # (e) 18-cell gap heatmap; censored 2025-endpoint columns hatched
    ax = fig.add_subplot(bot[1])
    ests = ("E1", "E2", "E3"); eps = ("2024", "2025")
    grid = np.zeros((3, 6)); txt = [[""] * 6 for _ in range(3)]
    for i, e in enumerate(ests):
        for j, b in enumerate(bases):
            for k, ep in enumerate(eps):
                cell = BA["matrix"][f"{b}|2021->{ep}|{e}"]["gap_pp"]
                grid[i, j * 2 + k] = cell
                txt[i][j * 2 + k] = f"{cell:.1f}"
    im = ax.imshow(grid, cmap="BuGn", vmin=0, vmax=36, aspect="auto")
    for i in range(3):
        for j in range(6):
            dark = grid[i, j] > 24
            t = ax.text(j, i, txt[i][j], ha="center", va="center", fontsize=7,
                        color="white" if dark else INK)
            t.set_path_effects([pe.withStroke(linewidth=1.6,
                                foreground="#333333" if dark else "white")])
    for xb in (1.5, 3.5):
        ax.axvline(xb, color="white", lw=2.2)
    for j in (1, 3, 5):
        ax.add_patch(Rectangle((j - 0.5, -0.5), 1, 3, fill=False,
                               edgecolor="#909090", lw=0.8, ls=(0, (2, 2)),
                               hatch="///"))
    ax.set_xticks(range(6))
    ax.set_xticklabels(["2019w\n→2024", "2019w\n→2025", "2021w\n→2024", "2021w\n→2025",
                        "2024w\n→2024", "2024w\n→2025"], fontsize=7)
    ax.set_yticks(range(3)); ax.set_yticklabels(ests)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    header(ax, "e", "Gap (pp) across 18 specification cells")
    cb = fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.05,
                      pad=0.30, ticks=[0, 10, 20, 30])
    cb.set_label("gap (pp)  ·  hatched columns: 2025 endpoint (right-censored)",
                 fontsize=7)
    cb.ax.tick_params(labelsize=7, length=2)
    save(fig, "fig1_asymmetry_illusion")


# ----------------------------------------------------------------------------
def fig2():
    # 2026-10-20 redesign: b redrawn as the 21-term pairwise lower-triangle
    # width matrix (EJOR row/column framed, exact-width sum annotated); the
    # per-source dw*dm bars are demoted to an in-figure note inside a;
    # c becomes a named 7-source x 3-estimand LOO heatmap; d gains the three
    # registered lambda points. Estimand colour coding moved to grey scale.
    fig = plt.figure(figsize=(W_DOUBLE, 5.4))
    gs = fig.add_gridspec(2, 2, left=0.105, right=0.975, top=0.885, bottom=0.135,
                          hspace=0.62, wspace=0.36)

    # (a) dw-dm risk map (+ demoted interaction summary as in-figure note)
    ax = fig.add_subplot(gs[0, 0])
    offsets = {
        "Information Sciences": ((-7, 3), "right"),
        "European Journal of Operational Research": ((0, 9), "center"),
        "Applied Soft Computing": ((-7, -5), "right"),
        "Computers and Operations Research": ((7, 4), "left"),
        "IEEE Transactions on Fuzzy Systems": ((6, 9), "left"),
        "Expert Systems with Applications": ((7, -2), "left"),
        "Engineering Applications of Artificial Intelligence": ((7, -3), "left"),
    }
    for r in U1["horizontal_interaction"]:
        s, dw, dm = r["source"], r["delta_weight"], r["delta_level"]
        hot = s in ("Engineering Applications of Artificial Intelligence",
                    "European Journal of Operational Research")
        ax.scatter(dw, dm, s=90 if hot else 46, color=ORANGE if hot else GREY,
                   zorder=3 if hot else 2, edgecolor=INK, linewidth=0.5)
        off, ha = offsets.get(s, ((5, 4), "left"))
        ax.annotate(SHORT.get(s, s[:8]), (dw, dm), textcoords="offset points",
                    xytext=off, fontsize=7, ha=ha, va="center",
                    color=INK if hot else "#555555",
                    path_effects=HALO)
    ax.axhline(0, color="#AAAAAA", lw=0.7); ax.axvline(0, color="#AAAAAA", lw=0.7)
    ax.set_xlabel("Weight change Δw (share, 2021→2024)")
    ax.set_ylabel("Rate change Δm (edges/paper)")
    ax.set_xlim(-0.175, 0.205); ax.set_ylim(-0.43, 0.78)
    ax.set_xticks([-0.15, -0.10, -0.05, 0.05, 0.10, 0.15, 0.20])
    irows = sorted(U1["horizontal_interaction"], key=lambda r: r["interaction"])
    inter_sum = sum(r["interaction"] for r in irows) * 100
    htext(ax, 0.02, 0.035, f"Σ Δw×Δm = {inter_sum:.2f} pp\n"
          f"EAAI + EJOR = 95.5% of net interaction",
          transform=ax.transAxes, ha="left", va="bottom", fontsize=7,
          color="#555555", linespacing=1.5)
    header(ax, "a", "Weight change vs rate change by source")

    # (b) 21-term pairwise exact-width matrix (lower triangle)
    ax = fig.add_subplot(gs[0, 1])
    order = list(SRC7)
    n = len(order)
    pair_val = {}
    for t in U1["pairwise_terms"]:
        (s1, s2), v = t["sources"], t["width_contribution"] * 100
        pair_val[frozenset((s1, s2))] = v
    mat = np.full((n, n), np.nan)
    for i in range(n):
        for j in range(n):
            if i > j:
                mat[i, j] = pair_val[frozenset((order[i], order[j]))]
    mmasked = np.ma.masked_invalid(mat)
    cmap = LinearSegmentedColormap.from_list("ochre_teal", [ORANGE, "#FFFFFF", TEAL])
    norm = TwoSlopeNorm(vmin=-3.5, vcenter=0, vmax=0.5)
    ax.set_facecolor("white")
    im = ax.imshow(mmasked, cmap=cmap, norm=norm, aspect="auto")
    for i in range(n):
        for j in range(n):
            if i > j:
                v = mat[i, j]
                dark = abs(v) > 2.2
                t = ax.text(j, i, f"{v:+.2f}", ha="center", va="center",
                            fontsize=7,
                            color="white" if dark else INK)
                t.set_path_effects([pe.withStroke(linewidth=1.6,
                                    foreground="#333333" if dark else "white")])
    ej = order.index("European Journal of Operational Research")
    ax.add_patch(Rectangle((-0.5, ej - 0.5), ej + 1.0, 1.0, fill=False,
                           edgecolor=INK, lw=2.0, zorder=5))
    ax.add_patch(Rectangle((ej - 0.5, ej - 0.5), 1.0, n - ej + 0.0, fill=False,
                           edgecolor=INK, lw=2.0, zorder=5))
    # 2026-10-21 visual fix: the in-matrix Σ note overlaid bottom-row cells;
    # demoted to a one-line footnote below the rotated tick labels (no cell
    # contact), same registered value 12.777 pp.
    ax.text(1.0, -0.30, "Σ = 12.777 pp (exact width)",
            transform=ax.transAxes, ha="right", va="top", fontsize=7,
            color="#555555", clip_on=False)
    ax.set_xticks(range(n)); ax.set_yticks(range(n))
    ax.set_xticklabels([SHORT.get(s, s[:8]) for s in order], fontsize=7,
                       rotation=38, ha="right")
    ax.set_yticklabels([SHORT.get(s, s[:8]) for s in order], fontsize=7)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    header(ax, "b", "Pairwise width contributions, 21 source pairs (pp)")
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.05, ticks=[-3, -2, -1, 0])
    cb.set_label("width contribution (pp)", fontsize=7)
    cb.ax.tick_params(labelsize=7, length=2)

    # (c) leave-one-source-out: named 7 sources x 3 estimands heatmap
    ax = fig.add_subplot(gs[1, 0])
    ests = ("E1", "E2", "E3")
    grid = np.array([[BA["loo"][f"{s}|2021|2021->2024|{e}"]["gap_pp"]
                      for e in ests] for s in order])
    im = ax.imshow(grid, cmap="BuGn", vmin=0, vmax=36, aspect="auto")
    for i in range(n):
        for j, e in enumerate(ests):
            dark = grid[i, j] > 24
            t = ax.text(j, i, f"{grid[i, j]:.1f}", ha="center", va="center",
                        fontsize=7,
                        color="white" if dark else INK)
            t.set_path_effects([pe.withStroke(linewidth=1.6,
                                foreground="#333333" if dark else "white")])
    ax.set_xticks(range(3)); ax.set_xticklabels(ests, fontsize=7)
    ax.set_yticks(range(n))
    ax.set_yticklabels([SHORT.get(s, s[:8]) for s in order], fontsize=7)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.text(0.0, -0.26, "leave-one-source-out gap, 2021→2024, base-2021 weights",
            transform=ax.transAxes, fontsize=7, va="top", ha="left",
            color="#555555", clip_on=False)
    ax.text(0.0, -0.40, "smallest gap across all 18 cells: 2.49 pp",
            transform=ax.transAxes, fontsize=7, va="top", ha="left",
            color="#555555", clip_on=False)
    header(ax, "c", "Leave-one-source-out gap (pp) by source")

    # (d) lambda flip frontier + three registered lambda points + observed point
    ax = fig.add_subplot(gs[1, 1])
    tp24 = DOIB["tipping_point"]["2021->2024"]
    fr = [p["lambda_forward"] for p in tp24["frontier"]]
    rr = [p["lambda_reverse_breakeven"] for p in tp24["frontier"]]
    ax.plot(fr, rr, color=INK, lw=1.6)
    ax.fill_between(fr, rr, 0.6, color="#EFEFEF", alpha=0.9)
    ax.plot([0, 0.45], [0, 0.45], color="#AAAAAA", lw=0.8, ls=":")
    lam = {"E1": tp24["diagonal_flip_lambda_e1"],
           "E3": tp24["diagonal_flip_lambda"],
           "E3, numerator-only":
               FLD["windows"]["2021->2024"]["lambda_star_e3_versionB_numerator_only"]}
    mk = {"E1": ("o", INK), "E3": ("s", "#555555"),
          "E3, numerator-only": ("^", "#999999")}
    lab_xy = {"E1": (0.265, 0.135), "E3": (0.305, 0.315),
              "E3, numerator-only": (0.105, 0.055)}
    for name, lv in lam.items():
        m, c = mk[name]
        ax.plot(lv, lv, m, color=c, ms=5.5, mec=INK, mew=0.5, zorder=4)
        lab = (f"{name}: λ = {lv:.3f}" if name != "E3, numerator-only"
               # registered display value 0.041 (NUMBERS:430); raw 0.040487
               else "E3, numerator-only:\nλ = 0.041")
        ax.annotate(lab, (lv, lv), xytext=lab_xy[name],
                    fontsize=7, color=INK, va="center", linespacing=1.4,
                    arrowprops=dict(arrowstyle="-", color="#777777", lw=0.6,
                                    shrinkA=0, shrinkB=2),
                    path_effects=HALO)
    ax.plot(0.02, 0.08, "D", color="white", ms=5.5, mec=INK, mew=0.9, zorder=4)
    ax.annotate("observed parsed target\nshares ≈0.02 / 0.08", (0.02, 0.08),
                xytext=(0.055, 0.175), fontsize=7, color=INK, va="center",
                arrowprops=dict(arrowstyle="-", color="#777777", lw=0.6,
                                shrinkA=0, shrinkB=2),
                path_effects=HALO)
    ax.annotate("flip frontier", (0.10, rr[2]), xytext=(0.175, 0.44),
                fontsize=7, color=INK, va="center",
                arrowprops=dict(arrowstyle="-", color="#777777", lw=0.6,
                                shrinkA=0, shrinkB=2),
                path_effects=HALO)
    ax.text(0.02, 0.97, "exposure bracket, not a correction",
            transform=ax.transAxes, fontsize=7, ha="left", va="top",
            color="#555555")
    ax.set_xlabel("λ forward (target share among unparsed rows)")
    ax.set_ylabel("λ reverse needed to erase gap")
    ax.set_xlim(-0.01, 0.45); ax.set_ylim(0, 0.6)
    header(ax, "d", "Counterfactual exposure frontier, 2021→2024")
    save(fig, "fig2_decomposition_engine")


# ----------------------------------------------------------------------------
def fig3():
    # 2026-10-20 redesign: a split into dumbbell zone + independent relative-
    # change text column, small-sample families grouped under a grey
    # "descriptive" band; b y-axis raised to 0-17.5 and LLM line neutralised;
    # c grey-scale lines + matched/standardised gap note; d adds the I1/I6
    # youth-bias secondary curve (0.472->1.607) and a pre-2004 "not
    # computable" band. Data reads unchanged.
    fig = plt.figure(figsize=(W_DOUBLE, 6.2))
    gs = fig.add_gridspec(2, 2, height_ratios=[0.57, 0.43],
                          left=0.185, right=0.935, top=0.93, bottom=0.10,
                          hspace=0.30, wspace=0.38)

    # (a) subfamily turnover dumbbells + independent relative-change column
    acell = gs[0, 0].subgridspec(1, 2, width_ratios=[0.64, 0.36], wspace=0.04)
    axd = fig.add_subplot(acell[0])
    axt = fig.add_subplot(acell[1])
    fams = [f for f in DUAL["subfamilies"]]
    elig = sorted((f for f in fams if f["eligible"]),
                  key=lambda f: -f["rel_change_ec_debut"])
    desc = sorted((f for f in fams if not f["eligible"]),
                  key=lambda f: -f["rel_change_ec_debut"])
    show = elig + desc                      # 9 adjudicated + 9 descriptive rows
    yrows = list(range(len(show) - 1, -1, -1))   # top-to-bottom
    labels = {"ga": "genetic algorithms", "general_ec": "general EC",
              "emo": "multi-objective (EMO)", "particle_swarm": "particle swarm",
              "other_swarm_bio": "other swarm/bio",
              "other_metaheuristic": "other metaheuristic",
              "OTHER": "other/unclassified",
              "genetic_programming": "genetic programming",
              "differential_evolution": "differential evolution",
              "generic_heuristic": "generic heuristic",
              "memetic_hybrid": "memetic/hybrid", "ant_colony": "ant colony",
              "evolution_strategies": "evolution strategies",
              "neuroevolution": "neuroevolution",
              "eda": "estimation-of-distribution",
              "lcs": "learning classifier systems",
              "hyper_heuristic": "hyper-heuristic",
              "genetic_fuzzy": "genetic fuzzy"}
    n_desc = len(desc)
    axd.add_patch(Rectangle((0, -0.6), 30, n_desc + 0.1, fc="#EFEFEF", ec="none",
                            zorder=0))
    axd.text(29.4, 7.5, "descriptive (n<200)", fontsize=7,
             color="#666666", ha="right", va="center", zorder=1)
    axd.scatter([13.0], [5.7], s=22, color="#BBBBBB", zorder=5)
    axd.text(14.2, 5.7, "= 2003–07", fontsize=7, color="#555555", va="center",
             zorder=5)
    axd.scatter([13.0], [4.5], s=34, color="#666666", zorder=5)
    axd.text(14.2, 4.5, "= 2019–22", fontsize=7, color="#555555", va="center",
             zorder=5)
    for f, yy in zip(show, yrows):
        g1, g2 = f["share_ec_debut_G1"] * 100, f["share_ec_debut_G2"] * 100
        rel = f["rel_change_ec_debut"] * 100
        if f["eligible"]:
            up = g2 > g1
            c_line = TEAL if up else ORANGE
            c_new = TEAL if up else ORANGE
            c_txt = TEAL if up else "#B25000"
        else:
            c_line, c_new, c_txt = "#B0B0B0", "#8A8A8A", "#777777"
        axd.plot([g1, g2], [yy, yy], color=c_line, lw=1.8, alpha=0.8, zorder=2)
        axd.scatter([g1], [yy], s=22, color="#BBBBBB", zorder=3)
        axd.scatter([g2], [yy], s=34, color=c_new, zorder=4)
        axt.text(0.04, yy, f"{rel:+.1f}%", fontsize=7, va="center", ha="left",
                 color=c_txt)
    axd.set_yticks(yrows)
    axd.set_yticklabels([labels.get(f["family"], f["family"].replace("_", " "))
                         for f in show], fontsize=7)
    axd.set_xlabel("Share of EC-debut authors (%)")
    axd.set_xlim(0, 30); axd.set_ylim(-0.6, len(show) + 1.7)
    axd.set_xticks([0, 10, 20, 30])
    axt.set_xlim(0, 1); axt.set_ylim(-0.6, len(show) + 1.7)
    axt.axis("off")
    axt.text(0.04, len(show) + 0.95, "relative change", fontsize=7, color=INK,
             va="center", ha="left")
    axt.text(0.04, len(show) + 0.22, "2003–07 → 2019–22", fontsize=7,
             color="#555555", va="center", ha="left")
    header(axd, "a", "Subfamily shares of EC-debut authors")

    # (b) incoming agendas
    ax = fig.add_subplot(gs[0, 1])
    yrs = sorted(int(y) for y in TERMS["share"]["LLM/GPT"])
    llm = [TERMS["share"]["LLM/GPT"][str(y)]["a"] * 100 for y in yrs]
    ag = R3B_DIMS["agenda_external_sum"]["EC_any"]
    agy = sorted(int(y) for y in ag)
    agv = [ag[str(y)]["external_sum"] * 100 for y in agy]
    ax.plot(agy, agv, color=INK, lw=1.8, label="external topics, EC papers")
    ax.plot(yrs, llm, color="#4D4D4D", lw=1.6, ls="--", marker="o", ms=2.4,
            label="LLM/GPT terms (A-tier)")
    ax.axhline(0, color="#AAAAAA", lw=0.6)
    ax.set_xlabel("Year"); ax.set_ylabel("Share of papers (%)")
    ax.set_ylim(0, 17.5); ax.set_yticks([0, 5, 10, 15])
    ax.legend(frameon=True, framealpha=1.0, edgecolor="#DDDDDD", loc="upper left",
              fontsize=7)
    header(ax, "b", "External topics and LLM/GPT term shares")

    # (c) CD5 divergence
    ax = fig.add_subplot(gs[1, 0])
    yrs = [r["year"] for r in DIS if "EC" in r and "NON_EC" in r]
    ec = [r["EC"]["mean"] for r in DIS if "EC" in r and "NON_EC" in r]
    non = [r["NON_EC"]["mean"] for r in DIS if "EC" in r and "NON_EC" in r]
    ax.plot(yrs, ec, color=INK, lw=1.8, label="EC")
    ax.plot(yrs, non, color="#777777", lw=1.8, ls="--", label="non-EC")
    ax.axhline(0, color="#AAAAAA", lw=0.6)
    ax.annotate("2018–20 gap raw −0.443\n→ journal-only −0.368\n"
                "2005–07 raw −0.035 → +0.059\n"
                "gap is matched/standardized,\nnot the difference of means",
                (2002.0, -0.44), fontsize=7, color=INK, va="bottom", ha="left",
                bbox=dict(fc="white", ec="#CCCCCC", lw=0.5, pad=2.5),
                linespacing=1.45)
    ax.set_xlabel("Cohort year"); ax.set_ylabel("CD5 disruption index")
    ax.set_ylim(-0.45, 0.58)
    ax.set_xticks([2005, 2010, 2015, 2020])
    ax.legend(frameon=True, framealpha=1.0, edgecolor="#DDDDDD", loc="upper right",
              fontsize=7)
    header(ax, "c", "CD5 disruption index, EC vs non-EC cohorts")

    # (d) citation ageing + I1/I6 youth-bias secondary curve
    ax = fig.add_subplot(gs[1, 1])
    by = MEM["by_citing_year_oc"]
    yy = [r["year"] for r in by]; ge5 = [r["share_age_ge_5"] * 100 for r in by]
    ax.axvspan(2001.5, 2004, color="#EAEAEA", zorder=0)
    ax.text(2002.75, 32, "not computable", fontsize=7, color="#666666",
            ha="center", va="center", rotation=90, zorder=1)
    ax.plot(yy, ge5, color=INK, lw=1.8, zorder=3)
    ax.fill_between(yy, ge5, 0, color="#BBBBBB", alpha=0.25, zorder=1)
    peak = max(by, key=lambda r: r["share_age_ge_5"])
    ax.annotate(f"peak {peak['share_age_ge_5']*100:.1f}% ({peak['year']})",
                (peak["year"], peak["share_age_ge_5"] * 100),
                xytext=(max(yy) + 0.3, peak["share_age_ge_5"] * 100 + 5.5),
                fontsize=7, va="bottom", ha="right",
                arrowprops=dict(arrowstyle="-", color="#777777", lw=0.6,
                                shrinkA=0, shrinkB=2),
                path_effects=HALO)
    ax.set_xlabel("Citing year"); ax.set_ylabel("Citations to work ≥5 years old (%)")
    ax.set_xlim(2001.5, 2025.5); ax.set_ylim(0, 64)
    ax2 = ax.twinx()
    ax2.spines["right"].set_visible(True)
    yb = MEM["youth_bias_oc"]
    yx = [r["year"] for r in yb]; yv = [r["I1_over_I6"] for r in yb]
    ax2.plot(yx, yv, color="#4D4D4D", lw=1.4, ls="--", marker="o", ms=2.6,
             zorder=4)
    ax2.set_ylim(0, 1.9)
    ax2.set_ylabel("youth-bias ratio I1/I6", fontsize=8, color="#4D4D4D")
    ax2.tick_params(axis="y", labelsize=7, colors="#4D4D4D")
    ax2.annotate(f"{yv[0]:.3f}", (yx[0], yv[0]), textcoords="offset points",
                 xytext=(2, -11), fontsize=7, color="#4D4D4D", ha="left",
                 path_effects=HALO, zorder=5)
    ax2.annotate(f"{yv[-1]:.3f}", (yx[-1], yv[-1]), textcoords="offset points",
                 xytext=(-12, -12), fontsize=7, color="#4D4D4D", ha="right",
                 va="top", path_effects=HALO, zorder=5)
    header(ax, "d", "The citation base ages")
    save(fig, "fig3_internal_ecology")


# ----------------------------------------------------------------------------
def fig4():
    # 2026-10-20 redesign (spec 08 §2 Fig4): a dual-axis + parity line; b rebuilt
    # as two shared-x rows (top: EC vs non-EC retention with the TRUE non-EC
    # retention from flow_robust NON-origin rows — P0 data fix, N15; bottom:
    # EC→non-EC migration + net outflow ratio); c gains a first-difference
    # lead-lag inset (lag -3..+3, lag 0 highlighted, registered r = +0.926);
    # d gains a third strip (newcomer co-authorship). Titles made descriptive.
    fig = plt.figure(figsize=(W_DOUBLE, 5.2))
    gs = fig.add_gridspec(2, 2, left=0.085, right=0.925, top=0.895, bottom=0.115,
                          hspace=0.68, wspace=0.48)

    # (a) first-choice share: left raw share, right corrected ratio + parity
    ax = fig.add_subplot(gs[0, 0])
    fc = R3O["first_choice_share"]; yrs = sorted(int(y) for y in fc)
    cr = R3O["corrected_first_choice_ratio_paper_weight"]
    l1, = ax.plot(yrs, [fc[str(y)] * 100 for y in yrs], color=ORANGE, lw=1.8,
                  label="raw first-paper EC share (left)")
    ax.set_ylim(0, 50)
    ax.set_ylabel("Raw first-paper EC share (%)", color=ORANGE)
    ax.tick_params(axis="y", labelcolor=ORANGE)
    ax.set_xlabel("Year")
    axr = ax.twinx()
    l2, = axr.plot(yrs, [cr[str(y)] for y in yrs], color=BLUE, lw=1.8,
                   label="composition-corrected ratio (right)")
    axr.axhline(1.0, color="#555555", lw=1.0, ls="--", zorder=1)
    axr.text(2004.0, 0.978, "parity = 1.0", fontsize=7, color="#555555")
    axr.set_ylim(0.5, 1.0)
    axr.set_ylabel("Composition-corrected ratio", color=BLUE)
    axr.tick_params(axis="y", labelcolor=BLUE)
    axr.spines["right"].set_visible(True)
    ax.legend(handles=[l1, l2], frameon=True, framealpha=1.0, edgecolor="#DDDDDD",
              loc="lower left", fontsize=7)
    header(ax, "a", "First-paper entry into EC: raw vs corrected")

    # (b) author flow: two rows sharing the period axis
    per = AF["ec_attrition_series_robust"]
    short = {"2003-2006 -> 2007-2010": "03–06→07–10", "2007-2010 -> 2011-2014": "07–10→11–14",
             "2011-2014 -> 2015-2018": "11–14→15–18", "2015-2018 -> 2019-2022": "15–18→19–22",
             "2019-2022 -> 2023-2025": "19–22→23–25"}
    labels = [short.get(p["period"], p["period"]) for p in per]
    x = np.arange(len(per))
    ec_ret = [p["EC"] * 100 for p in per]            # EC retention (robust): 63.35 -> 41.56
    frob = AF["flow_robust"]                          # same five transitions, NON-origin rows
    non_ret = [r["NON->NON"] / (r["NON->EC"] + r["NON->NON"] + r["NON->mixed"] + r["NON->absent"]) * 100
               for r in frob]                         # true non-EC retention: 57.3 -> 65.8
    gb = gs[0, 1].subgridspec(2, 1, height_ratios=[1.3, 1.0], hspace=0.10)
    axb1 = fig.add_subplot(gb[0])
    axb1.bar(x - 0.19, ec_ret, width=0.36, color=BLUE, label="EC retention")
    axb1.bar(x + 0.19, non_ret, width=0.36, color=GREY, label="non-EC retention")
    axb1.set_ylim(0, 100)
    axb1.set_ylabel("Retention (%)")
    axb1.set_xticks(x)
    axb1.tick_params(axis="x", labelbottom=False, length=0)
    axb1.legend(frameon=True, framealpha=1.0, edgecolor="#DDDDDD", loc="upper right",
                fontsize=7, ncol=2)
    header(axb1, "b", "Author retention and EC→non-EC migration", dy=0.09)
    axb2 = fig.add_subplot(gb[1], sharex=axb1)
    mig = [p["NON"] * 100 for p in per]              # EC authors' share in non-EC: 9.36 -> 18.29
    axb2.plot(x, mig, color=ORANGE, lw=1.8, marker="o", ms=3)
    ff = AF["flow_full"]
    net0 = ff[0]["EC->NON"] / ff[0]["NON->EC"]       # 0.95
    net1 = ff[-1]["EC->NON"] / ff[-1]["NON->EC"]     # 1.62
    axb2.text(0.02, 0.94, f"net outflow ratio (EC→non-EC ÷ non-EC→EC): {net0:.2f} → {net1:.2f}",
              transform=axb2.transAxes, fontsize=7, va="top", ha="left", color=INK,
              path_effects=HALO)
    axb2.set_ylim(0, 24)
    axb2.set_ylabel("EC→non-EC\nmigration (%)", fontsize=7)
    axb2.set_xticks(x)
    axb2.set_xticklabels(labels, fontsize=7, rotation=30, ha="right")

    # (c) funding agenda + first-difference lead-lag inset (side inset column,
    # same construction as the registered diagnostic in funding_permutation.py:
    # funded subset external_sum vs the five external frontier term shares
    # summed from terms.json, 2016-2025 -> 9 first-difference pairs;
    # lag 0 r = +0.9258, registered +0.926 (NUMBERS:165/432), shown as +0.93)
    gc2 = gs[1, 0].subgridspec(1, 2, width_ratios=[0.60, 0.40], wspace=0.42)
    ax = fig.add_subplot(gc2[0])
    fs = FA["funded_subset_share"]; fy = sorted(int(y) for y in fs)
    ax.plot(fy, [fs[str(y)]["external_sum"] * 100 for y in fy], color=TEAL, lw=1.8, marker="o", ms=3,
            label="funded subset")
    ag = R3B_DIMS["agenda_external_sum"]["EC_any"]
    ax.plot(fy, [ag[str(y)]["external_sum"] * 100 for y in fy], color=BLUE, lw=1.8, label="all EC papers")
    ax.set_xlabel("Year"); ax.set_ylabel("External-topic share (%)")
    ax.set_xticks([2016, 2019, 2022, 2025])
    ax.legend(frameon=True, framealpha=1.0, edgecolor="#DDDDDD", loc="upper left",
              fontsize=7)
    # 2026-10-21 visual fix (round 2): this axes is the narrow 60% sub-column
    # (~31 mm), so the default axes-fraction dx=0.065 put the title start at
    # ~2.0 mm and fused it with the bold "c" glyph (~1.8 mm wide). dx=0.132
    # restores the ~4.0 mm absolute letter->title offset used by a/b/d.
    header(ax, "c", "Funded vs all-EC external share", dy=0.115, dx=0.132)
    EXT5 = ["deep learning", "reinforcement learning", "LLM/GPT", "transformer", "explainable AI"]
    funded = np.array([fs[str(y)]["external_sum"] for y in fy], dtype=float)
    full = np.zeros(len(fy))
    for name in EXT5:
        for i, y in enumerate(fy):
            v = TERMS["share"][name].get(str(y), {}).get("ec")
            if v is not None:
                full[i] += v
    df_, dg_ = np.diff(funded), np.diff(full)

    def _pear(x_, y_):
        xc, yc = x_ - x_.mean(), y_ - y_.mean()
        den = float(np.sqrt((xc ** 2).sum() * (yc ** 2).sum()))
        return float((xc * yc).sum() / den) if den else float("nan")

    lags = list(range(-3, 4))
    rr = []
    for lag in lags:
        if lag < 0:
            x_, y_ = df_[-lag:], dg_[:len(dg_) + lag]
        elif lag > 0:
            x_, y_ = df_[:-lag], dg_[lag:]
        else:
            x_, y_ = df_, dg_
        rr.append(_pear(x_, y_))
    axi = fig.add_subplot(gc2[1])
    axi.bar(lags, rr, width=0.62,
            color=[BLUE if lag == 0 else "#BBBBBB" for lag in lags])
    axi.set_xticks(lags)
    axi.set_xticklabels([f"{l:+d}" for l in lags], fontsize=7)
    axi.set_yticks([0, 0.5, 1.0])
    axi.tick_params(labelsize=7)
    axi.set_ylim(0, 1.05)
    axi.set_xlabel(f"lag (yr)\nfirst-difference, lag 0: r = {rr[3]:+.2f}",
                   fontsize=7, labelpad=1)
    axi.set_ylabel("r", fontsize=7, labelpad=1)
    # 2026-10-21 visual fix: the two-line inset title fused with the panel-c
    # header band (letter + one-line title span the 60/40 split); the r note
    # now sits on its own line below the inset x-label, clear of both.

    # (d) counter-evidence bundle: three stacked strips sharing the year axis
    # (series labels sit inside each strip — ylabels would collide at this height)
    gd = gs[1, 1].subgridspec(3, 1, hspace=0.42)
    axt = fig.add_subplot(gd[0])
    sc = AUTH["self_citation"]; sy = [r["year"] for r in sc]; sv = [r["rate"] * 100 for r in sc]
    axt.plot(sy, sv, color="#5A5A5A", lw=1.6)
    axt.text(0.02, 0.06, "self-citation (%)", transform=axt.transAxes, fontsize=7,
             va="bottom", ha="left", color="#5A5A5A")
    axt.tick_params(axis="y", labelcolor="#5A5A5A", labelsize=7)
    axt.tick_params(axis="x", labelbottom=False, length=0)
    axt.set_xlim(min(sy) - 0.5, max(sy) + 0.5)
    header(axt, "d", "Self-citation, classic citations, newcomer co-authorship", dy=0.14)
    axm = fig.add_subplot(gd[1], sharex=axt)
    ns = CHECKS["c3_nsga2_series"]["oc"]; ny = sorted(int(y) for y in ns)
    axm.plot(ny, [ns[str(y)] for y in ny], color=AMBER, lw=1.6)
    axm.text(0.02, 0.86, "NSGA-II citations", transform=axm.transAxes, fontsize=7,
             va="top", ha="left", color="#B07A00")
    axm.tick_params(axis="y", labelcolor="#B07A00", labelsize=7)
    axm.tick_params(axis="x", labelbottom=False, length=0)
    axn = fig.add_subplot(gd[2], sharex=axt)
    ent = AUTH["entrants"]
    ey = [r["year"] for r in ent]; ev = [r["share_papers_with_newcomer"] * 100 for r in ent]
    axn.plot(ey, ev, color=TEAL, lw=1.6)
    axn.text(0.02, 0.14, "papers with a newcomer (%)", transform=axn.transAxes,
             fontsize=7, va="bottom", ha="left", color="#0B6E4F")
    axn.tick_params(axis="y", labelcolor="#0B6E4F", labelsize=7)
    axn.set_ylim(60, 90)
    axn.set_yticks([60, 75, 90])
    axn.set_xlabel("Year")
    save(fig, "fig4_people_money")


# ----------------------------------------------------------------------------
PAIRS = [
    ("physics", "materials"), ("chemistry", "chemical_engineering"),
    ("biology", "medicine"), ("computer_science", "electrical_engineering"),
    ("neuroscience", "psychology"), ("economics", "business"),
    ("sociology", "political_science"), ("statistics", "computer_science"),
    ("ecology", "earth_science"), ("biomedical_engineering", "medicine"),
    ("mathematics", "physics"), ("mechanical_engineering", "materials"),
]
PNAME = {
    "physics": "physics", "materials": "materials", "chemistry": "chemistry",
    "chemical_engineering": "chem. eng.", "biology": "biology", "medicine": "medicine",
    "computer_science": "comp. sci.", "electrical_engineering": "elec. eng.",
    "neuroscience": "neurosci.", "psychology": "psychology", "economics": "economics",
    "business": "business", "sociology": "sociology", "political_science": "poli. sci.",
    "statistics": "statistics", "ecology": "ecology", "earth_science": "earth sci.",
    "biomedical_engineering": "biomed. eng.", "mathematics": "mathematics",
    "mechanical_engineering": "mech. eng.",
}


def fig5():
    # 2026-10-20 redesign (spec 08 §2 Fig5): a restyled (tier = fill strength:
    # full = solid deep teal, E1 tier = medium grey, refused = white + neutral
    # grey hatch; in-cell E1 number + three-state sign marker; shared-field mark
    # stays on the row-label side; "not collected" -> light grey dash; mandated
    # bottom footnote); c (Poisson calibration) demoted to an inset column at
    # a's lower right; d (support change) compressed to a narrow strip at a's
    # right (~18%): the two PRB rows merged into one split-record row
    # (0 = hollow bar, 14,894 = solid bar), C&IE departure note, symlog axis
    # labelled; b gains the grey separator band above statistics<->CS and the
    # caption-verbatim count title; refused cells carry a "pooled only" note.
    fig = plt.figure(figsize=(W_DOUBLE, 6.9))
    gs = fig.add_gridspec(2, 3, height_ratios=[1.8, 1.0],
                          width_ratios=[0.56, 0.26, 0.18],
                          left=0.178, right=0.985, top=0.930, bottom=0.080,
                          hspace=0.55, wspace=0.32)

    # (a) 12-pair matrix: rows = pairs, columns = the two directions
    ax = fig.add_subplot(gs[0, 0])
    shared = {"physics", "computer_science", "medicine", "materials"}
    TIER_FC = {"full": TEAL, "e1_tier": "#8C8C8C", "refused": "white"}
    ax.set_xlim(0, 2); ax.set_ylim(-0.15, 12.9)
    for i, (a_, b_) in enumerate(PAIRS):
        y = len(PAIRS) - 1 - i
        for j in range(2):
            s_, t_ = (a_, b_) if j == 0 else (b_, a_)
            dk = f"{s_}->{t_}"
            if dk not in FM["directions"]:
                ax.text(j + 0.5, y + 0.5, "—", ha="center", va="center",
                        fontsize=8, color="#B8B8B8")
                continue
            d = FM["directions"][dk]
            e1 = d["aggregates"]["E1"]["pooled_rel"] * 100
            tier = d["tier"]
            ax.add_patch(Rectangle((j + 0.03, y + 0.08), 0.94, 0.84,
                                   facecolor=TIER_FC[tier],
                                   edgecolor="#6E6E6E" if tier == "refused" else "none",
                                   lw=0.9, hatch="///" if tier == "refused" else None))
            txtcol = INK if tier == "refused" else "white"
            # three-state sign marker: filled = all sources positive,
            # open = all sources negative, half-filled = mixed signs
            sc = d["scorecard"]["E1"]
            if tier != "refused":
                if sc["consistent"] and sc["direction"] == "up":
                    fs_ = "full"
                elif sc["consistent"] and sc["direction"] == "down":
                    fs_ = "none"
                else:
                    fs_ = "left"
                ax.plot([j + 0.16], [y + 0.5], marker="o", ms=3.6, lw=0.9,
                        markerfacecolor=txtcol if fs_ != "none" else "none",
                        markeredgecolor=txtcol, fillstyle=fs_,
                        markeredgewidth=0.9, zorder=5)
                ax.text(j + 0.56, y + 0.5, f"{e1:+.0f}%", ha="center", va="center",
                        fontsize=7, color=txtcol)
            else:
                ax.text(j + 0.5, y + 0.60, f"{e1:+.0f}%", ha="center", va="center",
                        fontsize=7, color=txtcol, path_effects=HALO)
                ax.text(j + 0.5, y + 0.31, "pooled only", ha="center", va="center",
                        fontsize=7, color="#6E6E6E", path_effects=HALO)
    ax.set_yticks([k + 0.5 for k in range(len(PAIRS))])
    ax.set_yticklabels([("◦ " if {a_, b_} & shared else "") + f"{PNAME[a_]} ↔ {PNAME[b_]}"
                        for a_, b_ in PAIRS][::-1], fontsize=7)
    ax.set_xticks([])
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.text(0.5, 12.55, "A → B", ha="center", va="center", fontsize=7.5)
    ax.text(1.5, 12.55, "B → A", ha="center", va="center", fontsize=7.5)
    ax.text(-0.03, 12.55, "field pair", ha="right", va="center", fontsize=7, color="#555555")
    ax.text(0.5, -0.120, "100 edges/window gate; 9.2% per-source sign error",
            transform=ax.transAxes, fontsize=7, ha="center", va="top", color="#444444")
    ax.text(0.5, -0.205, "cell value = E1 pooled rel. change, 2011–13 → 2021–23",
            transform=ax.transAxes, fontsize=7, ha="center", va="top", color="#555555")
    header(ax, "a", "Twelve field pairs: tiers, E1 signs and sign-consistency", dy=0.045)

    # key + (c) Poisson calibration inset column at a's right / lower right
    gc = gs[0, 1].subgridspec(2, 1, height_ratios=[1.0, 1.05], hspace=0.40)
    axk = fig.add_subplot(gc[0]); axk.axis("off")
    mk = dict(marker="o", lw=0, ms=5, markeredgecolor=INK, markeredgewidth=0.9)
    axk.legend(handles=[
        Patch(fc=TEAL, ec="none", label="full protocol"),
        Patch(fc="#8C8C8C", ec="none", label="E1 tier"),
        Patch(fc="white", ec="#6E6E6E", hatch="///", label="refused (pooled only)"),
        Line2D([0], [0], markerfacecolor=INK, label="all sources positive", **mk),
        Line2D([0], [0], markerfacecolor="none", label="all sources negative", **mk),
        Line2D([0], [0], markerfacecolor=INK, fillstyle="left", label="mixed signs", **mk),
        Line2D([0], [0], marker="_", ms=9, lw=0, markeredgecolor="#B8B8B8",
               label="not collected"),
        Line2D([0], [0], marker="o", ms=3, lw=0, markerfacecolor="none",
               markeredgecolor="#555555", markeredgewidth=0.9,
               label="field shared by ≥2 pairs"),
    ], loc="upper left", bbox_to_anchor=(0.0, 1.04), fontsize=7, frameon=False,
        handlelength=1.5, labelspacing=0.38, borderaxespad=0.0, handletextpad=0.7)
    axc = fig.add_subplot(gc[1])
    tab = TIER["per_source_table"]
    lam = [r["lam0"] for r in tab]; e20 = [r["err_d20"] * 100 for r in tab]
    axc.plot(lam, e20, color=BLUE, lw=1.6, marker="o", ms=2.6)
    thr = TIER["readings"]["per_source_edges_for_10pct_sign_error_at_20pct_change"]
    axc.axhline(10, color=RED, lw=0.9, ls="--")
    axc.axvline(thr, color="#999999", lw=0.9, ls=":")
    axc.annotate(f"{thr} edges/window\n→ 9.2% sign error\n(at 20% true change)",
                 (thr, 10), fontsize=7, xytext=(0.97, 0.30), textcoords="axes fraction",
                 ha="right", va="bottom",
                 arrowprops=dict(arrowstyle="-", color="#999999", lw=0.7),
                 path_effects=HALO)
    axc.set_xscale("log")
    axc.set_xticks([10, 100]); axc.set_xticklabels(["10", "100"])
    axc.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    axc.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    axc.set_xlabel("expected edges / source / window", fontsize=7)
    axc.set_ylabel("sign error (%)", fontsize=7)
    axc.tick_params(labelsize=7)
    header(axc, "c", "Poisson gate calibration", dy=0.10, dx=0.115)

    # (d) support-change narrow strip: merged PRB split record
    # (all annotation texts are axes-fraction anchored — symlog data coords
    # would push 7pt strings past the strip's right edge)
    axd = fig.add_subplot(gs[0, 2])
    d = FM["directions"]["physics->materials"]
    n_early = d["per_source"]["S4210237713"]["early"]["n_articles"]    # 0
    n_modern = d["per_source"]["S4210237713"]["modern"]["n_articles"]  # 14,894
    axd.set_xscale("symlog")
    axd.set_xlim(-0.9, 60000)
    axd.set_ylim(0, 1)
    # one merged row: hollow bar for the 0-article early window, solid for modern
    axd.text(0.02, 0.94, "PRB (split record)", transform=axd.transAxes, fontsize=7,
             va="top", ha="left", color=INK, fontweight="bold")
    axd.barh(0.68, 2.2, left=-0.45, height=0.13, facecolor="none",
             edgecolor="#8C8C8C", lw=0.9)
    axd.text(0.30, 0.68, f"{n_early} early", transform=axd.transAxes, fontsize=7,
             va="center", ha="left", color="#555555")
    axd.barh(0.50, n_modern, left=-0.45, height=0.13, color=TEAL)
    axd.text(0.84, 0.50, f"{n_modern:,}", transform=axd.transAxes, fontsize=7,
             va="center", ha="right", color="white", fontweight="bold")
    axd.text(0.30, 0.36, "modern", transform=axd.transAxes, fontsize=7,
             va="center", ha="left", color="#555555")
    axd.set_yticks([])
    axd.set_xticks([0, 100, 10000])
    axd.set_xticklabels(["0", "100", "10000"])
    axd.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    axd.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    axd.tick_params(axis="x", labelsize=7)
    axd.set_xlabel("articles per window\n(symlog scale)", fontsize=7)
    axd.text(0.02, 0.21,
             "split record →\nexcluded from\ncommon support;\nsame class as\nEC's departed C&IE",
             transform=axd.transAxes, fontsize=7, va="top", ha="left",
             color="#555555", linespacing=1.25)
    header(axd, "d", "Support change", dy=0.06, dx=0.115)

    # (b) pair-gap forest
    ax = fig.add_subplot(gs[1, :])
    gp_keys = [f"{a_}<->{b_}" for a_, b_ in PAIRS[:8]]
    # sign classes anchored to the registered caption grouping (submission Fig. 5
    # caption + Results: 2 positive / 3 negative / 2 sign-unstable /
    # statistics<->CS reported separately); neurosci.<->psychology is classed
    # negative there although its q025–q975 interval crosses zero.
    GAP_CLASS = {
        "chemistry<->chemical_engineering": "pos",
        "computer_science<->electrical_engineering": "pos",
        "physics<->materials": "neg",
        "biology<->medicine": "neg",
        "neuroscience<->psychology": "neg",
        "economics<->business": "unstable",
        "sociology<->political_science": "unstable",
        "statistics<->computer_science": "separate",
    }
    CLS_COL = {"pos": TEAL, "neg": ORANGE, "unstable": GREY, "separate": ORANGE}
    ypos = []
    for i, pk in enumerate(gp_keys):
        bt = FM["pair_gap_bootstrap_e1"][pk]
        col = CLS_COL[GAP_CLASS[pk]]
        y = len(gp_keys) - 1 - i
        # 2026-10-21 visual fix: extra 0.75-row gap above the statistics<->CS
        # row so the separator band + its note clear every CI line/endpoint
        if y >= 1:
            y += 0.75
        ypos.append(y)
        ax.plot([bt["q025"], bt["q975"]], [y, y], color=col, lw=2.2, alpha=0.85,
                solid_capstyle="round")
        ax.plot([bt["q50"]], [y], "o", color=col, ms=5)
        htext(ax, 185, y, f"{bt['pos_share']*100:.0f}%", va="center", fontsize=7, color=col)
    # grey separator band above the statistics<->CS row (bottom row, y = 0);
    # band 0.48-1.24 and the centred note stay clear of row 0's marker
    # (top ~0.18) and row 1's CI line (bottom ~1.67 at y = 1.75)
    ax.add_patch(Rectangle((-275, 0.48), 525, 0.76, facecolor="#EDEDED",
                           edgecolor="none", zorder=0))
    ax.text(-270, 0.86, "statistics↔comp. sci.: forward direction refused; reported separately",
            fontsize=7, va="center", ha="left", color="#555555", zorder=1)
    ax.axvline(0, color=INK, lw=1.0)
    ax.set_yticks(ypos)
    ax.set_yticklabels([f"{PNAME[a_]}↔{PNAME[b_]}" for a_, b_ in PAIRS[:8]], fontsize=7)
    ax.set_xlabel("Paired gap (pp), bootstrap q025–q975; right label = positive share")
    ax.set_xlim(-275, 250); ax.set_ylim(-0.65, 8.40)
    header(ax, "b", "Paired gaps: 2 positive, 3 negative, 2 sign-unstable, 1 reported separately")
    save(fig, "fig5_cross_science_atlas")


# ----------------------------------------------------------------------------
# 2026-10-20: row colour is now derived from the data (teal = rising share,
# ochre = falling; G3 increase/decrease semantics) and the "bull control"
# internal key is replaced by the source's display name (Machine Learning,
# S62148650; w1_panels.json / NUMBERS:146).
W1_SERIES = [
    ("operations_research__S103321696", "OR (EJOR)"),
    ("control_theory__S51360982", "control (Automatica)"),
    ("evolutionary_biology__S109682412", "evo. biology (JTB)"),
    ("machine_learning_bull__S62148650", "ML (Machine Learning)"),
    ("computer_vision__S25538012", "computer vision (IJCV)"),
    ("nlp__S155526855", "NLP (Comput. Ling.)"),
]


# --- hand-drawn vector glyphs (no external artwork) -------------------------
def _glyph_ax(ax):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")
    return ax


def icon_check(ax, color):
    _glyph_ax(ax)
    ax.plot([0.15, 0.40, 0.85], [0.52, 0.22, 0.78], color=color, lw=1.8,
            solid_capstyle="round", solid_joinstyle="round")


def icon_cross(ax, color):
    _glyph_ax(ax)
    ax.plot([0.25, 0.75], [0.25, 0.75], color=color, lw=1.8, solid_capstyle="round")
    ax.plot([0.25, 0.75], [0.75, 0.25], color=color, lw=1.8, solid_capstyle="round")


def icon_target(ax, color=TEAL):
    _glyph_ax(ax)
    for r in (0.42, 0.28, 0.14):
        ax.add_patch(Circle((0.5, 0.5), r, fill=False, ec=color, lw=1.1))
    ax.add_patch(Circle((0.5, 0.5), 0.05, fc=color, ec="none"))


def icon_layers(ax, color=BLUE):
    _glyph_ax(ax)
    for i in range(3):
        ax.add_patch(Rectangle((0.12 + 0.11 * i, 0.12 + 0.11 * i), 0.5, 0.5,
                               fill=False, ec=color, lw=1.1))


def icon_balance(ax, color=INK):
    _glyph_ax(ax)
    ax.plot([0.5, 0.5], [0.18, 0.84], color=color, lw=1.2)
    ax.plot([0.18, 0.82], [0.68, 0.68], color=color, lw=1.2)
    ax.plot([0.36, 0.64], [0.18, 0.18], color=color, lw=1.2)
    for x in (0.18, 0.82):
        ax.plot([x, x], [0.68, 0.50], color=color, lw=0.9)
        ax.add_patch(Circle((x, 0.42), 0.075, fill=False, ec=color, lw=0.9))


def icon_timeline(ax, color=ORANGE):
    _glyph_ax(ax)
    ax.annotate("", xy=(0.88, 0.5), xytext=(0.12, 0.5),
                arrowprops=dict(arrowstyle="<->", color=color, lw=1.3))
    for x in (0.12, 0.88):
        ax.plot([x, x], [0.36, 0.64], color=color, lw=1.1)
        ax.add_patch(Circle((x, 0.5), 0.055, fc=color, ec="none"))


def icon_dispersion(ax, color=AMBER):
    _glyph_ax(ax)
    for x, y in ((0.20, 0.30), (0.35, 0.62), (0.50, 0.42), (0.62, 0.72),
                 (0.75, 0.35), (0.86, 0.55), (0.45, 0.82)):
        ax.add_patch(Circle((x, y), 0.05, fc=color, ec="none"))


def icon_traffic(ax):
    _glyph_ax(ax)
    ax.add_patch(FancyBboxPatch((0.30, 0.08), 0.40, 0.84, boxstyle="round,pad=0.02",
                                fc="#F0F0F0", ec=INK, lw=0.8,
                                mutation_aspect=1.0))
    for y, c in ((0.74, TEAL), (0.50, AMBER), (0.26, RED)):
        ax.add_patch(Circle((0.5, y), 0.11, fc=c, ec="none"))


def fig6():
    # 2026-10-20 redesign (spec 08 §2 Fig6): bottom declaration-card band
    # deleted (the full card lives in ED8); freed height (~20%) goes to c as
    # co-hero; a colours follow increase/decrease semantics (teal = rising,
    # ochre = falling) and the ML row shows the real source name; b title made
    # descriptive; c carries the three R² calibres in-figure; d keeps the
    # four-quadrant screen with an embedded six-field mini reporting card.
    fig = plt.figure(figsize=(W_DOUBLE, 5.5))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.32],
                          left=0.16, right=0.965, top=0.925, bottom=0.080,
                          hspace=0.55, wspace=0.32)

    # (a) W1 memory split
    ax = fig.add_subplot(gs[0, 0])
    for i, (k, lab) in enumerate(W1_SERIES):
        s = AGE_W1[k]
        yrs = sorted(int(y) for y in s if s[y].get("n_papers"))
        v0, v1 = s[str(yrs[0])]["share_ge5"], s[str(yrs[-1])]["share_ge5"]
        c = TEAL if v1 >= v0 else ORANGE
        yy = len(W1_SERIES) - 1 - i
        ax.plot([v0, v1], [yy, yy], color=c, lw=2.0, alpha=0.8)
        ax.scatter([v0], [yy], s=24, color="#BBBBBB", zorder=3)
        ax.scatter([v1], [yy], s=38, color=c, zorder=4)
        htext(ax, max(v0, v1) + 0.015, yy, f"{v0:.2f}→{v1:.2f}", va="center",
              fontsize=7, color=c)
    ax.set_yticks(range(len(W1_SERIES)))
    ax.set_yticklabels([x[1] for x in W1_SERIES][::-1], fontsize=7)
    ax.set_xlim(0.3, 1.04)
    ax.set_xlabel("Share of citations ≥5 years old (first→last panel year)")
    ax.legend(handles=[Line2D([0], [0], color=TEAL, lw=2.0, label="rising"),
                       Line2D([0], [0], color=ORANGE, lw=2.0, label="falling")],
              loc="lower right", fontsize=7, frameon=True, framealpha=1.0,
              edgecolor="#DDDDDD")
    header(ax, "a", "Memory splits: DL-adjacent young, methodological old")

    # (b) cross-corpus widths
    ax = fig.add_subplot(gs[0, 1])
    items = [
        ("EC (7 sources)", abs(U1["aggregates"]["exact_width_percentage_points"])),
        ("econ→psych", PANL["directions"]["economics->psychology"]["width_pp"]),
        ("psych→econ", PANL["directions"]["psychology->economics"]["width_pp"]),
        ("OR→ML", PLAD["pairs"]["OR<->ML"]["OR->ML"]["fixed_composition"]["E1_width_pp"]),
        ("OR→evo", PLAD["pairs"]["OR<->evo"]["OR->evo"]["fixed_composition"]["E1_width_pp"]),
    ]
    y = np.arange(len(items))[::-1]
    ax.barh(y, [v for _, v in items], height=0.58, color=[BLUE, GREY, GREY, ORANGE, GREY])
    for yy_, (lab, v) in zip(y, items):
        htext(ax, v + 2.5, yy_, f"{v:.1f} pp", va="center", fontsize=7)
    ax.set_yticks(y); ax.set_yticklabels([k for k, _ in items], fontsize=7)
    ax.set_xlabel("Laspeyres–Paasche width (pp)")
    ax.set_xlim(0, 162)
    header(ax, "b", "L–P widths across corpora")

    # (c) synthetic calibration (co-hero)
    ax = fig.add_subplot(gs[1, 0])
    dc = SYN["decile_calibration"]
    x = [r["decile"] for r in dc]
    med = [r["width_pp_q50"] for r in dc]
    lo = [r["width_pp_q10"] for r in dc]; hi = [r["width_pp_q90"] for r in dc]
    ax.fill_between(x, lo, hi, color=BLUE, alpha=0.18, label="q10–q90")
    ax.plot(x, med, color=BLUE, lw=1.8, label="median width")
    ax.set_yscale("log")
    ax.set_yticks([0.01, 0.1, 1, 10])
    ax.set_yticklabels(["0.01", "0.1", "1", "10"])
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xlabel("Cross-source dispersion decile (840,000 synthetic panels)")
    ax.set_ylabel("L–P width (pp)")
    g = SYN["global"]
    ax.text(0.97, 0.05,
            f"R²: dispersion-only {g['r2_width_on_dispersion']:.2f} · "
            f"joint {g['r2_width_on_dispersion_migration']:.2f} · "
            f"log–log {g['r2_loglog_width_on_dispersion_migration']:.2f}",
            transform=ax.transAxes, fontsize=7, ha="right", va="bottom",
            color=INK, path_effects=HALO)
    ax.legend(frameon=True, framealpha=1.0, edgecolor="#DDDDDD", loc="upper left",
              fontsize=7)
    header(ax, "c", "Synthetic panels: width vs cross-source dispersion")

    # (d) U3 screen: four-quadrant card + embedded six-field mini card
    ax = fig.add_subplot(gs[1, 1])
    ax.axis("off")
    X0, X1, Y0, Y1 = -0.30, 2.12, -1.72, 2.62
    ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1)
    cf = U3V["scoring"]["confusion_all"]
    quads = [
        # (x, y, count, role, face, edge, glyph)
        (0.03, 1.28, cf["TP"], "TP · true positive", "#EAF2EC", TEAL, icon_check),
        (1.08, 1.28, cf["FP"], "FP · false positive", "#FDF1E3", ORANGE, icon_cross),
        (0.03, 0.18, cf["FN"], "FN · false negative", "#FBEDEB", RED, icon_cross),
        (1.08, 0.18, cf["TN"], "TN · true negative", "#F2F2F2", GREY, icon_check),
    ]
    for x0, y0, n, role, fc_, ec_, glyph in quads:
        ax.add_patch(FancyBboxPatch((x0, y0), 0.99, 1.02,
                                    boxstyle="round,pad=0.02,rounding_size=0.06",
                                    fc=fc_, ec=ec_, lw=1.0))
        cx = (x0 + 0.495 - X0) / (X1 - X0)
        cy = (y0 + 0.72 - Y0) / (Y1 - Y0)
        glyph(ax.inset_axes([cx - 0.034, cy - 0.038, 0.068, 0.076]), ec_)
        ax.text(x0 + 0.495, y0 + 0.40, f"{n:,}", ha="center", va="center",
                fontsize=10, fontweight="bold", color=INK)
        ax.text(x0 + 0.495, y0 + 0.13, role, ha="center", va="center",
                fontsize=7, color="#555555")
    ax.text(0.525, 2.46, "defect present", ha="center", va="center", fontsize=7,
            color="#555555")
    ax.text(1.575, 2.46, "defect absent", ha="center", va="center", fontsize=7,
            color="#555555")
    for yv, s in ((1.79, "flagged"), (0.69, "passed")):
        ax.text(-0.13, yv, s, ha="center", va="center", fontsize=7, rotation=90,
                color="#555555")
    ax.text(0.525, -0.14,
            f"detection {cf['TP']/(cf['TP']+cf['FN'])*100:.1f}% · "
            f"miss {cf['FN']/(cf['TP']+cf['FN'])*100:.1f}%",
            ha="center", va="center", fontsize=7, color=INK)
    # embedded six-field mini reporting card (2 x 3 grid; full card lives in ED8)
    ax.text(-0.28, -0.40, "reporting card (6 fields):", fontsize=7, va="center",
            ha="left", fontweight="bold", color=INK)
    fields = [
        ("estimand", "E1 · E2 · E3"),
        ("support set", "7 merged sources"),
        ("base year", "2021 · L–P"),
        ("endpoints", "2021→2024/25"),
        ("dispersion", "signs + width"),
        ("screen", "3-state gate"),
    ]
    fw, fh, fgap = 0.76, 0.52, 0.05
    for i, (name, gloss) in enumerate(fields):
        fx = -0.28 + (i % 3) * (fw + fgap)
        fy0 = -0.58 - (i // 3) * (fh + 0.08)
        ax.add_patch(FancyBboxPatch((fx, fy0 - fh), fw, fh,
                                    boxstyle="round,pad=0.012,rounding_size=0.03",
                                    fc="#EAF2EC", ec=TEAL, lw=0.7))
        ax.text(fx + fw / 2, fy0 - 0.075, name, fontsize=7, ha="center", va="top",
                color=INK, fontweight="bold")
        ax.text(fx + fw / 2, fy0 - 0.255, gloss, fontsize=7, ha="center", va="top",
                color="#555555")
    header(ax, "d", "Coverage–power screen", dy=0.03)
    save(fig, "fig6_portability_calibration")


# ----------------------------------------------------------------------------
def ed1():
    fig = plt.figure(figsize=(W_DOUBLE, 3.3))
    gs = fig.add_gridspec(1, 2, left=0.065, right=0.985, top=0.845, bottom=0.20,
                          wspace=0.30)
    layers_f = [
        ("anchor-\nrestricted", lambda ep: S8["s1_single_end_anchor"][ep]["E1_mean_edges"] /
         S8["s1_single_end_anchor"]["2021"]["E1_mean_edges"] - 1),
        ("common support\npooled", lambda ep: S8["same_support"][ep]["pooled"]["rel_change"]),
        ("fixed 2021\ncomposition", lambda ep: S8["same_support"][ep]["fixed_2021_weights"]["E1"]["rel_change"]),
    ]
    layers_r = [
        ("full\nsupport", lambda ep: S8["s1_reverse_full"][ep]["E1_mean_edges_to_non"] /
         S8["s1_reverse_full"]["2021"]["E1_mean_edges_to_non"] - 1),
        ("common support\npooled", lambda ep: S8["same_support_reverse"][ep]["pooled"]["E1"]["rel_change"]),
        ("fixed 2021\ncomposition", lambda ep: S8["same_support_reverse"][ep]["fixed_2021_weights"]["E1"]["rel_change"]),
    ]
    enc = [Patch(fc=ORANGE, ec="none", label="2024"),
           Patch(fc=ORANGE, alpha=0.55, hatch="///", ec="white", lw=0.4,
                 label="2025 (right-censored)")]
    for k, (ax, layers, ttl, base, light) in enumerate(
            ((fig.add_subplot(gs[0]), layers_f, "Forward (outside→EC), E1", ORANGE, True),
             (fig.add_subplot(gs[1]), layers_r, "Reverse (EC→outside), E1", BLUE, False))):
        x = np.arange(len(layers))
        for i, (lab, fn) in enumerate(layers):
            for ep, dx in (("2024", 0.17), ("2025", -0.17)):
                v = fn(ep) * 100
                ax.bar(i + dx, v, width=0.32,
                       color=base if ep == "2024" else base,
                       alpha=1.0 if ep == "2024" else 0.55,
                       hatch="" if ep == "2024" else "///",
                       edgecolor="white", lw=0.4)
                htext(ax, i + dx, v + (0.9 if v > 0 else -0.9), pct(v / 100, 1),
                      ha="center", va="bottom" if v > 0 else "top", fontsize=7.0,
                      color=INK if ep == "2024" else "#777777")
        ax.set_xticks(x); ax.set_xticklabels([l[0] for l in layers], fontsize=6.8)
        ax.axhline(0, color=INK, lw=0.9)
        ax.set_ylabel("Relative change (%)")
        ax.set_ylim(-44, 4) if k == 0 else ax.set_ylim(0, 17.5)
        header(ax, "a" if k == 0 else "b", ttl, dy=0.16 if k == 0 else 0.055)
    fig.axes[0].legend(handles=enc, frameon=False, loc="lower left",
                       bbox_to_anchor=(0.0, 1.01, 1.0, 0.13), ncol=2, fontsize=7.0)
    save(fig, "ed1_spec_ladders")


def ed2():
    # 2026-10-21 redesign (spec 08 section ED2): a = full 18-cell bootstrap
    # forest (3 estimands x 3 base years x 2 endpoints; q025/q50/q975 all
    # frozen in BA["bootstrap"]); b = 7-source x 6-column sign scorecard
    # (forward/reverse x E1/E2/E3, relative change 2021->2024, teal=rise /
    # orange=fall) replacing the anonymous LOO scatter (the named LOO heatmap
    # now lives in Fig2c). Endpoint is a category dimension: neutral ink/grey
    # + linestyle/marker, 2025 flagged right-censored (G3).
    fig = plt.figure(figsize=(W_DOUBLE, 4.6))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.05, 1], left=0.105, right=0.975,
                          top=0.855, bottom=0.10, wspace=0.26)

    # (a) 18-cell forest, blocked by estimand
    ax = fig.add_subplot(gs[0])
    order = []
    for est in ("E1", "E2", "E3"):
        grp = [(k.split("|")[0], k.split("->")[1].split("|")[0], k)
               for k in BA["bootstrap"] if k.endswith("|" + est)]
        grp.sort(key=lambda t: (t[0], t[1]))
        order.append((est, grp))
    slots, ticklab, ticky = [], [], []
    y = 0.0
    for est, grp in order:                     # E1 block low, E3 block high
        for base, ep, k in grp:
            slots.append((y, est, base, ep, k))
            ticklab.append(f"{base}w\u2192{ep[2:]}")
            ticky.append(y)
            y += 1.0
        y += 1.2                               # gap between estimand blocks
    for yy, est, base, ep, k in slots:
        b = BA["bootstrap"][k]
        cens = ep == "2025"
        col, ls, mfc = (GREY, (0, (3, 2)), "white") if cens else (INK, "-", INK)
        ax.plot([b["q025"], b["q975"]], [yy, yy], lw=2.0, color=col, ls=ls,
                alpha=0.9, solid_capstyle="round")
        ax.plot([b["q50"]], [yy], "o", ms=4, color=col, mfc=mfc, mec=col)
        ax.text(93, yy, "excludes 0" if b["q025"] > 0 else "crosses 0",
                fontsize=7, color="#555555", ha="right", va="center")
    for est, grp in order:                     # bold block tags above blocks
        top_y = max(s[0] for s in slots if s[1] == est)
        ax.text(-19, top_y + 0.75, est, fontsize=8, fontweight="bold",
                color=INK, ha="left", va="center")
    ax.axvline(0, color=INK, lw=1.0)
    ax.set_yticks(ticky); ax.set_yticklabels(ticklab, fontsize=7)
    ax.set_xlim(-20, 95); ax.set_ylim(-0.7, 22.3)
    ax.set_xticks([0, 20, 40, 60])
    ax.set_xlabel("Gap (pp), source-level cluster resampling")
    ax.text(0.015, 0.985, "3 base years \u00d7 2 endpoints \u00d7 3 estimands",
            transform=ax.transAxes, fontsize=7, color="#555555", va="top")
    ax.text(0.985, 0.985, "CI vs 0", transform=ax.transAxes, fontsize=7,
            color="#555555", va="top", ha="right")
    ax.legend(handles=[Line2D([0], [0], color=INK, lw=2.0, marker="o", ms=4,
                              label="\u21922024"),
                       Line2D([0], [0], color=GREY, lw=2.0, ls=(0, (3, 2)),
                              marker="o", ms=4, mfc="white",
                              label="\u21922025 (right-censored)")],
              loc="lower left", bbox_to_anchor=(0.0, 1.005, 1.0, 0.08),
              mode="expand", ncol=2, frameon=False, fontsize=7)
    header(ax, "a", "Bootstrap gap distributions", dy=0.125)

    # (b) 7-source x 6-column sign scorecard, 2021->2024
    axb = fig.add_subplot(gs[1])
    axb.axis("off")
    axb.set_xlim(0, 11.6); axb.set_ylim(-1.9, 8.8)
    colx = [3.55, 4.90, 6.25, 8.05, 9.40, 10.75]
    pairs = [("E1", "E1_to_non"), ("E2", "E2_to_non"), ("E3", "E3_to_non")]
    axb.text(4.90, 8.30, "forward", ha="center", va="center", fontsize=8,
             fontweight="bold")
    axb.text(9.40, 8.30, "reverse", ha="center", va="center", fontsize=8,
             fontweight="bold")
    for cx, lab in zip(colx, ("E1", "E2", "E3", "E1", "E2", "E3")):
        axb.text(cx, 7.65, lab, ha="center", va="center", fontsize=7,
                 color="#555555")
    axb.plot([7.15, 7.15], [-0.45, 8.0], color="#CCCCCC", lw=0.7)
    for i, s in enumerate(SRC7):
        yy = 6.6 - i * 1.0
        if i % 2 == 0:
            axb.add_patch(Rectangle((0.0, yy - 0.46), 11.6, 0.94,
                                    fc="#F5F5F5", ec="none", zorder=0))
        axb.text(0.05, yy, SHORT[s], ha="left", va="center", fontsize=7)
        f21, f24 = (S8["per_source_e1"][f"2021|{s}"],
                    S8["per_source_e1"][f"2024|{s}"])
        r21, r24 = (S8["per_source_e1_reverse"][f"2021|{s}"],
                    S8["per_source_e1_reverse"][f"2024|{s}"])
        for j, (ff, fr) in enumerate(pairs):
            vf = (f24[ff] / f21[ff] - 1) * 100
            vr = (r24[fr] / r21[fr] - 1) * 100
            for kk, v in ((0, vf), (1, vr)):
                axb.text(colx[j + 3 * kk], yy, f"{v:+.1f}", ha="center",
                         va="center", fontsize=7,
                         color=TEAL if v >= 0 else ORANGE)
    axb.text(0.05, -0.75, "Relative change 2021\u21922024 (%); teal = rise, "
                          "orange = fall.\nforward = outside\u2192EC, "
                          "reverse = EC\u2192outside.\nSign structure only, "
                          "not a propensity claim.",
             fontsize=7, color="#444444", va="top", linespacing=1.5)
    header(axb, "b", "Per-source sign scorecard", dy=0.055)
    save(fig, "ed2_uncertainty_loo")


def ed3():
    # 2026-10-21 redesign (spec 08 section ED3): a adds the frozen 5-6-author
    # bucket (W4A team_size carries 1-2/3-4/5-6/7+ for 2018-20); b moves
    # CD5/CD3/CD2 to a greyscale three-tier category code (ink/grey/light grey
    # + distinct linestyles and markers, G3); c gains its y-axis label and the
    # "(36-51%)" title fragment moves in-axes as an explained note.
    fig = plt.figure(figsize=(W_DOUBLE, 2.9))
    gs = fig.add_gridspec(1, 3, left=0.06, right=0.985, top=0.825, bottom=0.20,
                          wspace=0.42)
    ax = fig.add_subplot(gs[0])
    tb = W4A["team_size"]["buckets"]
    x = np.arange(4)
    for i, grp in enumerate(("EC", "NON_EC")):
        vals = [tb[f"2018-20|{grp}|{b}"]["mean"] for b in ("1-2", "3-4", "5-6", "7+")]
        ax.bar(x + (i - 0.5) * 0.36, vals, width=0.34, color=ORANGE if grp == "EC" else GREY,
               label="EC" if grp == "EC" else "non-EC")
    ax.set_xticks(x); ax.set_xticklabels(("1–2 authors", "3–4", "5–6", "7+"), fontsize=7)
    ax.axhline(0, color=INK, lw=0.8)
    ax.legend(frameon=True, framealpha=1.0, edgecolor="#DDDDDD", fontsize=7,
              loc="upper left")
    ax.set_ylabel("CD5 (2018–20)")
    header(ax, "a", "Team-size strata")
    ax = fig.add_subplot(gs[1])
    for nm, key, c, ls, mk in (("CD5", "cd5", INK, "-", "o"),
                               ("CD3", "cd3", "#666666", (0, (4, 2)), "s"),
                               ("CD2", "cd2", "#ABABAB", (0, (1.5, 1.5, 4, 1.5)), "^")):
        ser = R3B_CD[key]
        yy = sorted(int(y) for y in ser)
        ax.plot(yy, [ser[str(y)]["gap"] for y in yy], lw=1.6, color=c, ls=ls,
                marker=mk, ms=3.0, label=nm)
    ax.axhline(0, color=INK, lw=0.8)
    ax.legend(frameon=True, framealpha=1.0, edgecolor="#DDDDDD", fontsize=7, ncol=3,
              loc="lower left", columnspacing=1.0, handlelength=1.6)
    ax.set_xlabel("Cohort year"); ax.set_ylabel("EC − non-EC gap")
    header(ax, "b", "Window bridge: no rebound through 2023")
    ax = fig.add_subplot(gs[2])
    nc = R3B_CD["cd5_NONciter"]
    yy = sorted(int(y) for y in nc)
    ax.plot(yy, [nc[str(y)]["gap"] for y in yy], lw=1.5, color=TEAL)
    ax.axhline(0, color=INK, lw=0.8)
    ax.set_xlabel("Cohort year"); ax.set_ylabel("EC − non-EC gap")
    ax.text(0.97, 0.96, "36–51% of the unadjusted gap", transform=ax.transAxes,
            fontsize=7, color="#555555", va="top", ha="right")
    header(ax, "c", "Non-EC-citer yardstick")
    save(fig, "ed3_cd5_robustness")


def ed4():
    fig = plt.figure(figsize=(W_DOUBLE, 2.9))
    gs = fig.add_gridspec(1, 2, left=0.075, right=0.985, top=0.825, bottom=0.20,
                          wspace=0.32)
    ax = fig.add_subplot(gs[0])
    cw = MEM["cohort_windows"]
    # C10 truncation: a cohort is computable only if its 0–3 y citation window is
    # fully observable, i.e. cohort year + 3 <= last citing year in the frozen data
    # (MEM["cy_max"]); the cutoff is derived, not hardcoded.
    last_ok = max(r["year"] for r in cw if r["year"] + 3 <= MEM["cy_max"])
    cw = [r for r in cw if r["year"] <= last_ok]
    yy = [r["year"] for r in cw]; v = [r["early_share_01_of_0_3"] for r in cw]
    ax.plot(yy, v, color=TEAL, lw=1.8)
    ax.set_xlabel("Cohort year")
    ax.set_ylabel("share of cohort citations to recent work")
    ax.set_ylim(0.20, 0.45)
    ax.text(0.97, 0.05, "right-censored cohorts excluded", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=7, color="#555555")
    header(ax, "a", "Cohort front-loading 26.1%→37.0%")
    ax = fig.add_subplot(gs[1])
    for k, lab, c in (("expert_systems__search", "expert systems", BLUE),
                      ("symbolic_ai__search", "symbolic AI", TEAL),
                      ("fuzzy_logic__search", "fuzzy logic", AMBER)):
        s = AGE_W2[k]
        yy = sorted(int(y) for y in s)
        ax.plot(yy, [s[str(y)]["share_ge5"] for y in yy], lw=1.5, color=c, label=lab)
    ax.legend(frameon=True, framealpha=1.0, edgecolor="#DDDDDD", fontsize=7.0,
              loc="lower right")
    ax.set_xlabel("Citing year"); ax.set_ylabel("Share ≥5y")
    header(ax, "b", "Historical decline cases: memory rebounds")
    save(fig, "ed4_memory_detail")


def ed5():
    # 2026-10-21 redesign (spec 08 section ED5): a plots the SIGNED relative
    # change (-rel_decline; contraction negative, expansion positive -- the
    # same sign convention as Fig3a) with +/-25% adjudication lines and
    # teal=rise / orange=fall (G3 second semantic pair); b becomes a
    # full-width audit table over ALL 18 frozen subfamily rows (spec and
    # NUMBERS:221 say "17 families", but the frozen r3a_results.json carries
    # 18 rows: 9 eligible + 9 not eligible -- deviation logged as BLOCKED-17).
    # The "Measurement honesty notes" prose is removed from the canvas
    # (caption/SI takeover per C3; logged in exec_log_D).
    labels = {"ga": "genetic algorithms", "general_ec": "general EC",
              "emo": "multi-objective (EMO)", "particle_swarm": "particle swarm",
              "other_swarm_bio": "other swarm/bio",
              "other_metaheuristic": "other metaheuristic",
              "OTHER": "other/unclassified",
              "genetic_programming": "genetic programming",
              "differential_evolution": "differential evolution",
              "generic_heuristic": "generic heuristic",
              "memetic_hybrid": "memetic/hybrid", "ant_colony": "ant colony",
              "evolution_strategies": "evolution strategies",
              "neuroevolution": "neuroevolution",
              "eda": "estimation-of-distribution",
              "lcs": "learning classifier systems",
              "hyper_heuristic": "hyper-heuristic",
              "genetic_fuzzy": "genetic fuzzy"}
    fig = plt.figure(figsize=(W_DOUBLE, 6.8))
    gs = fig.add_gridspec(2, 1, height_ratios=[0.40, 0.60], left=0.175,
                          right=0.975, top=0.935, bottom=0.035, hspace=0.34)

    # (a) signed relative change, eligible subfamilies
    ax = fig.add_subplot(gs[0])
    elig = sorted((f for f in R3A["subfamilies"] if f["eligible"]),
                  key=lambda f: f["rel_decline"])   # = signed change, desc
    y = np.arange(len(elig))[::-1]
    vals = [-f["rel_decline"] * 100 for f in elig]
    ax.barh(y, vals, height=0.62,
            color=[TEAL if v >= 0 else ORANGE for v in vals], alpha=0.9)
    ax.set_yticks(y)
    ax.set_yticklabels([labels[f["family"]] for f in elig], fontsize=7)
    ax.axvline(0, color=INK, lw=0.9)
    for xx in (-25, 25):
        ax.axvline(xx, color=RED, lw=0.8, ls="--")
    ax.text(0.985, 1.03, "dashed lines: \u00b125% adjudication",
            transform=ax.transAxes, fontsize=7, color=RED,
            ha="right", va="bottom")
    ax.set_xlabel("Relative change, all-field debut pool (%)")
    ax.set_xlim(-88, 48)
    header(ax, "a", "Eligible subfamilies (n\u2265200 both periods)", dy=0.10)

    # (b) full-width audit table, all 18 frozen subfamily rows
    axt = fig.add_subplot(gs[1])
    axt.axis("off")
    inel = sorted((f for f in R3A["subfamilies"] if not f["eligible"]),
                  key=lambda f: f["share_G1"] / f["share_G2"])  # change desc
    rows = elig + inel
    X = {"fam": 0.5, "ne": 40.0, "nm": 50.5, "rc": 64.0, "bp": 78.0, "el": 90.0}
    axt.set_xlim(0, 100); axt.set_ylim(-0.2, 20.9)
    axt.plot([0, 100], [19.35, 19.35], color=INK, lw=0.8)
    for key, txt, ha in (("fam", "subfamily", "left"),
                         ("ne", "n early", "right"), ("nm", "n modern", "right"),
                         ("rc", "relative change", "center"),
                         ("bp", "BH p", "center"), ("el", "eligible", "center")):
        axt.text(X[key], 19.85, txt, fontsize=7, fontweight="bold",
                 ha=ha, va="center")
    for i, f in enumerate(rows):
        yy = 18.55 - i * 0.98
        if i % 2:
            axt.add_patch(Rectangle((0, yy - 0.47), 100, 0.96, fc="#F5F5F5",
                                    ec="none", zorder=0))
        e = f["eligible"]
        # eligible rows carry the frozen rel_decline (signed flip, matches
        # panel a and NUMBERS exactly); ineligible rows fall back to the
        # share ratio from the same frozen record (descriptive).
        s = (-f["rel_decline"] * 100) if e else \
            (f["share_G2"] / f["share_G1"] - 1) * 100
        col = (TEAL if s >= 0 else ORANGE) if e else "#777777"
        axt.text(X["fam"], yy, labels[f["family"]], fontsize=7, ha="left",
                 va="center", color=INK if e else "#555555")
        axt.text(X["ne"], yy, f"{f['n_G1']:,}", fontsize=7, ha="right",
                 va="center")
        axt.text(X["nm"], yy, f"{f['n_G2']:,}", fontsize=7, ha="right",
                 va="center")
        axt.text(X["rc"], yy, f"{s:+.1f}%", fontsize=7, ha="center",
                 va="center", color=col)
        axt.text(X["bp"], yy,
                 (("<1e-6" if f["p_BH"] == 0.0 else f"{f['p_BH']:.2f}")
                  if e else "\u2014(n<200)"),
                 fontsize=7, ha="center", va="center")
        axt.text(X["el"], yy, "yes" if e else "no", fontsize=7, ha="center",
                 va="center")
        if i == len(elig) - 1:
            axt.plot([0, 100], [yy - 0.49, yy - 0.49], color="#BBBBBB", lw=0.6)
    axt.text(0.5, 0.45, "Pool: all-field first-paper authors, 2003\u201307 vs "
                        "2019\u201322; eligible = n\u2265200 in both periods. "
                        "'no' rows are descriptive (no test).",
             fontsize=7, color="#555555", va="center")
    header(axt, "b", "Subfamily audit table, all-field debut pool", dy=0.045)
    save(fig, "ed5_subfamily_terms_audit")


def ed6():
    # 轴标用锚刊名（来自冻结配置），原始 OpenAlex 记录号不进论文图；
    # 长刊名用标准缩写（ISO 4 风格），超宽两行换行
    sc = load("source_candidates.json")
    sid2name = {}
    for journals in sc.values():
        for jname, cands in journals.items():
            for c in cands:
                sid2name.setdefault(c["sid"], jname)
    with open(os.path.join(NATURE, "..", "panels", "sources.json"), encoding="utf-8") as f:
        for row in json.load(f)["sources"]:
            sid2name[row["sid"]] = row["journal"]

    ABBR = {
        "Journal of the American Chemical Society": "J. Am. Chem. Soc.",
        "Angewandte Chemie International Edition": "Angew. Chem. Int. Ed.",
        "IEEE Transactions on Information Theory": "IEEE Trans. Inf. Theory",
        "IEEE Transactions on Signal Processing": "IEEE Trans. Signal Process.",
        "IEEE Transactions on Biomedical Engineering": "IEEE Trans. Biomed. Eng.",
        "Industrial & Engineering Chemistry Research": "Ind. Eng. Chem. Res.",
        "Journal of Experimental Psychology: General": "J. Exp. Psychol. General",
        "Physical Review Letters": "Phys. Rev. Lett.",
        "Physical Review B": "Phys. Rev. B",
        "Physical Review A": "Phys. Rev. A",
        "Applied Physics Letters": "Appl. Phys. Lett.",
        "Proceedings of the IEEE": "Proc. IEEE",
        "Journal of Neuroscience": "J. Neuroscience",
        "Nucleic Acids Research": "Nucleic Acids Res.",
        "The EMBO Journal": "EMBO J.",
    }

    def jname(sid):
        return ABBR.get(sid2name.get(sid, ""), sid2name.get(sid, sid))

    def jwrap(nm):
        if len(nm) <= 22:
            return nm
        cut = nm.rfind(" ", 0, len(nm) // 2 + 6)
        return nm if cut <= 0 else nm[:cut] + "\n" + nm[cut + 1:]

    # window row per panel, derived from the frozen fieldmap design (not hardcoded)
    _w = FM["design"]["windows"]
    wrow = (f"{_w['early'][0][:4]}–{_w['early'][1][2:4]} → "
            f"{_w['modern'][0][:4]}–{_w['modern'][1][2:4]}")

    full_dirs = [d for d, v in FM["directions"].items() if v["tier"] == "full"][:9]
    fig = plt.figure(figsize=(W_DOUBLE, 5.3))
    gs = fig.add_gridspec(3, 3, left=0.15, right=0.99, top=0.93, bottom=0.115,
                          hspace=0.62, wspace=0.50)
    ax0 = None
    for idx, dk in enumerate(full_dirs):
        ax = fig.add_subplot(gs[idx], sharex=ax0)
        ax0 = ax0 or ax
        d = FM["directions"][dk]
        per = d["per_source"]
        y = np.arange(len(per))[::-1]
        seen = set()
        rowlab = []
        for sid in per:
            base = jname(sid)
            nm = base + " (duplicate record)" if base in seen else base
            seen.add(base)
            rowlab.append(jwrap(nm))
        for yy_, (sid, v) in zip(y, per.items()):
            e, m = v["early"]["E1"], v["modern"]["E1"]
            ax.plot([e, m], [yy_, yy_], lw=1.6, color=TEAL if m > e else GREY)
            ax.scatter([e], [yy_], s=14, color="#BBBBBB", zorder=3)
            ax.scatter([m], [yy_], s=24, color=TEAL if m > e else "#777777", zorder=4)
            if abs(m - e) < 0.01:  # visually one dot: label it so it is not read as missing
                htext(ax, max(e, m) + 0.12, yy_, "early = modern", fontsize=7.0,
                      color="#555555", va="center")
        ax.set_yticks(y); ax.set_yticklabels(rowlab, fontsize=7.0)
        # two-line panel head: letter + direction title above, window years below-right;
        # direction titles reuse Fig. 5's short field names so they never leave the canvas
        _a, _b = dk.split("->")
        dtitle = f"{PNAME.get(_a, _a)}→{PNAME.get(_b, _b)}"
        ax.text(0.0, 1.0 + 0.16, "abcdefghi"[idx], transform=ax.transAxes, fontsize=9,
                fontweight="bold", va="bottom", ha="left")
        ax.text(0.065, 1.0 + 0.16, dtitle,
                transform=ax.transAxes, fontsize=7.5, va="bottom", ha="left")
        ax.text(1.0, 1.0 + 0.05, wrow, transform=ax.transAxes, fontsize=7.0,
                va="bottom", ha="right", color="#555555")
        if idx >= 6:
            ax.set_xlabel("E1 per paper (early → modern)", fontsize=7.0)
    fig.legend(handles=[
        Line2D([0], [0], color=TEAL, lw=1.6, marker="o", ms=4, label="rising source"),
        Line2D([0], [0], color="#777777", lw=1.6, marker="o", ms=4, label="falling source"),
        Line2D([0], [0], color="none", marker="o", ms=4, mfc="#BBBBBB", mec="#BBBBBB",
               label="light dot = early window"),
        Line2D([0], [0], color="none", marker="o", ms=4, mfc="#555555", mec="#555555",
               label="solid dot = modern window")],
        loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=4, frameon=False,
        fontsize=7.0, handletextpad=0.6, columnspacing=1.2)
    save(fig, "ed6_fieldmap_sources")


def ed7():
    fig = plt.figure(figsize=(W_DOUBLE, 4.3))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.35], left=0.075, right=0.985,
                          top=0.885, bottom=0.315, wspace=0.42)
    ax = fig.add_subplot(gs[0])
    cf = U3V["scoring"]["confusion_all"]
    # N1 fix: FP=68 sits at flagged×absent, FN=4,203 at passed×present.
    # Semantic fills (G3): detected = warm teal, missed = warm ochre,
    # correct rejection = grey; false refusal = pale amber (milder error).
    cells = [  # (row, col, key, face, edge)
        (0, 0, "TP", "#CDE9DC", TEAL),
        (0, 1, "FP", "#F9EEDC", AMBER),
        (1, 0, "FN", "#F5DBC8", ORANGE),
        (1, 1, "TN", "#EFEFEF", GREY),
    ]
    for r, c, tag, fc_, ec_ in cells:
        ax.add_patch(Rectangle((c, 1 - r), 1, 1, facecolor=fc_, edgecolor=ec_, lw=1.2))
        ax.text(c + 0.5, 1 - r + 0.56, f"{cf[tag]:,}", ha="center", va="center",
                fontsize=11, fontweight="bold", color=INK)
        ax.text(c + 0.5, 1 - r + 0.28, tag, ha="center", va="center",
                fontsize=7.5, fontweight="bold", color=ec_)
    ax.set_xlim(-0.05, 2.05); ax.set_ylim(-0.05, 2.05)
    ax.set_xticks([0.5, 1.5]); ax.set_xticklabels(["defect\npresent", "defect\nabsent"],
                                                  fontsize=7)
    ax.set_yticks([1.5, 0.5]); ax.set_yticklabels(["flagged", "passed"], fontsize=7)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    det = cf["TP"] / (cf["TP"] + cf["FN"]); fpr = cf["FP"] / (cf["FP"] + cf["TN"])
    fn_ = cf["FN"] / (cf["TP"] + cf["FN"])
    ax.text(0.5, -0.12, f"detection {det*100:.1f}% · miss {fn_*100:.1f}% · "
                        f"false-rejection {fpr*100:.1f}%",
            transform=ax.transAxes, fontsize=7, ha="center", va="top", color="#555555")
    # colour key (each chip mirrors its cell's fill/edge)
    key = [("TP · detected", "#CDE9DC", TEAL), ("FP · false refusal", "#F9EEDC", AMBER),
           ("FN · missed", "#F5DBC8", ORANGE), ("TN · correct rejection", "#EFEFEF", GREY)]
    for r, pair in enumerate((key[:2], key[2:])):
        for c, (lab, fc_, ec_) in enumerate(pair):
            x0 = 0.06 + c * 0.50
            yy = -0.255 - r * 0.105
            ax.add_patch(Rectangle((x0, yy - 0.028), 0.055, 0.062,
                                   transform=ax.transAxes, facecolor=fc_,
                                   edgecolor=ec_, lw=1.0, clip_on=False))
            ax.text(x0 + 0.075, yy, lab, transform=ax.transAxes, fontsize=7,
                    va="center", ha="left", color="#333333")
    ax.text(0.5, -0.475, f"{cf['UNKNOWN_truth_void']} void adjudications not shown",
            transform=ax.transAxes, fontsize=7, ha="center", va="top", color="#555555")
    header(ax, "a", "Confusion summary (10,800 adjudications)")

    ax = fig.add_subplot(gs[1])
    dr = U3V["dose_response"]
    scenarios = [
        ("healthy/ref_loss/refs_missing_field", "refs missing (end window)"),
        ("healthy/ref_loss/refs_missing_field_both_windows", "refs missing (both windows)"),
        ("healthy/source_loss/source_partial_big", "big source partial loss"),
        ("healthy/source_loss/source_partial_small", "small source partial loss"),
        ("healthy/edge_loss/edge_thinning", "edge thinning"),
        ("healthy/edge_loss/edge_thinning_end_only", "edge thinning (end window)"),
    ]
    # G3: scenarios are a categorical dimension — neutral greyscale, with the
    # channel carried by linestyle + marker (colour-blind safe), not hue.
    styles = [("-", "o", "#111111"), ("--", "s", "#3A3A3A"), ("-.", "^", "#636363"),
              (":", "D", "#8C8C8C"), ((0, (3, 1, 1, 1)), "v", "#ABABAB"),
              ((0, (5, 1)), "P", "#C8C8C8")]
    for (key, lab), (ls, mk, col) in zip(scenarios, styles):
        v = dr[key]
        ax.plot(v["dose"], v["flag_rate"], lw=1.4, ls=ls, marker=mk, ms=3.8,
                color=col, label=lab)
    ax.set_xscale("log")
    ax.set_xticks([5, 10, 20, 50, 100])
    ax.set_xticklabels(["5", "10", "20", "50", "100"])
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xlabel("Defect dose (% of end-window citing papers)")
    ax.set_ylabel("Flag rate")
    ax.set_ylim(-0.04, 1.06)
    ax.legend(frameon=False, fontsize=7.0, ncol=2, loc="upper left",
              bbox_to_anchor=(-0.06, -0.17), columnspacing=1.1, handlelength=2.6)
    header(ax, "b", "Dose–response across defect scenarios")
    save(fig, "ed7_u3_validation")


def ed8():
    import textwrap
    # C8: designed at the 131 mm print width so type is not down-scaled;
    # six field cards on a 2 x 3 grid. Readings are unchanged.
    Wmm, Hmm = 131.0, 92.0
    fig = plt.figure(figsize=(Wmm * MM, Hmm * MM))
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.set_xlim(0, Wmm); ax.set_ylim(0, Hmm)

    def glyph_at(x, y, s):  # mm box -> axes-fraction inset
        return ax.inset_axes([x / Wmm, y / Hmm, s / Wmm, s / Hmm])

    ax.text(4, Hmm - 5.5, "Reporting card for cross-field citation change (6 mandatory fields)",
            fontsize=9, fontweight="bold", va="center")
    cards = [
        ("estimand", "E1 edges/paper · E2 participation · E3 share (never combined)", icon_target),
        ("support set", "7 merged sources common to both directions (2019/21/24/25)", icon_layers),
        ("composition base year", "declare one; report [Laspeyres … Paasche] when per-source signs mix", icon_balance),
        ("endpoints", "2021→2024 (complete) · 2021→2025 (right-censored, always co-read)", icon_timeline),
        ("dispersion", "per-source sign table + exact pairwise width", icon_dispersion),
        ("three-state screen", "comparable / partial / refused — with its measured miss rate", icon_traffic),
    ]
    cw, ch, gx, gy, x0 = 38.0, 30.0, 4.5, 4.5, 4.0
    ytop = Hmm - 11.5
    for i, (name, gloss, glyph) in enumerate(cards):
        r, c = divmod(i, 3)
        x = x0 + c * (cw + gx)
        y = ytop - (r + 1) * ch - r * gy
        ax.add_patch(FancyBboxPatch((x, y), cw, ch,
                                    boxstyle="round,pad=0.6,rounding_size=1.4",
                                    fc="#EAF2EC", ec=TEAL, lw=0.8))
        glyph(glyph_at(x + 2.8, y + ch - 10.8, 8.0))
        ax.text(x + 12.4, y + ch - 6.8, textwrap.fill(name, 17), fontsize=7,
                fontweight="bold", va="center", linespacing=1.25)
        ax.text(x + 2.8, y + ch - 13.6, textwrap.fill(gloss, 26), fontsize=7,
                va="top", color="#333333", linespacing=1.35)
    ax.text(4, 12.4,
            textwrap.fill(
                "Declared readings shipped with this paper: EC forward E1 [−14.6%, +7.1%] "
                "across base years; EC reverse E1 +1.6%…+66.0% (all 7 sources); "
                "gap +5.16…+33.97 pp (18 cells); 12-pair atlas tiers 8 full / 10 E1 / 2 refused.",
                88),
            fontsize=7, va="top", linespacing=1.55)
    save(fig, "ed8_reporting_card")


def main():
    os.makedirs(FIG_OUT, exist_ok=True)
    for fn in (fig1, fig2, fig3, fig4, fig5, fig6,
               ed1, ed2, ed3, ed4, ed5, ed6, ed7, ed8):
        try:
            fn()
            print("OK", fn.__name__)
        except Exception:
            print("FAIL", fn.__name__)
            traceback.print_exc()


if __name__ == "__main__":
    main()
