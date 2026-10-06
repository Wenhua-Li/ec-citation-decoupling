# -*- coding: utf-8 -*-
"""出图脚本 v2（2026-10-03 结构级重构）：主图 5 张 + Extended Data 10 张。

图群架构（paper/plan/05_figure_refactor_v2.md）：
  fig1 同框悖论门面（规模窄条 ×2 + 双端交换主格 + 入口 teaser + 同格森林）
  fig2 腿 3：CD5 分化与四类对照
  fig3 腿 2：入口重组（家族级 + 首选/校正 + 迁移/参与率）
  fig4 边界与机制排除（引用年龄 + 议程两侧 + LLM 渗透 + 资金零结果）
  fig5 校准与交付（泳道 + 提前量点带 + 协议横条；旧 fig5/fig6 合并）
  ed1 设计总览 / ed2 语料份额 / ed3 窗口变体+同格热图 / ed4 团队规模 /
  ed5 腿 1 口径稳健性 / ed6 相关矩阵 / ed7 自引互引 / ed8 议程热图 /
  ed9 解析率 / ed10 颠覆附加稳健性

用法：python make_figs.py fig1 | all
输出：本目录 <name>.png + .pdf + <name>.alignment.json（多面板对齐门留档）。
数据只读自冻结件（../../nature/out、../../r3b/out、../../r3a/out、
../../../archive/packages/w6|w8*/out）；图内文字数字仅限 NUMBERS.md 登记值。
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.gridspec as gridspec  # noqa: E402
from matplotlib.colors import TwoSlopeNorm  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = HERE
DATA = os.path.join(HERE, "..", "out")
R3B = os.path.join(HERE, "..", "..", "..", "archive", "packages", "r3b", "out")
R3A = os.path.join(HERE, "..", "..", "..", "archive", "packages", "r3a", "out")
W6 = os.path.join(HERE, "..", "..", "..", "archive", "packages", "w6_authors", "out")
W8 = os.path.join(HERE, "..", "..", "..", "archive", "packages", "w8_funding", "out")

# nature-figure 技能的对齐门（位置随用户环境，按 home 相对解析，不写绝对路径）
_SKILL_SCRIPTS = os.path.join(os.path.expanduser("~"), ".zcode", "skills",
                              "nature-figure", "scripts")
if os.path.isdir(_SKILL_SCRIPTS) and _SKILL_SCRIPTS not in sys.path:
    sys.path.insert(0, _SKILL_SCRIPTS)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 7,
    "axes.linewidth": 0.8,
    "figure.dpi": 300,
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
    "axes.unicode_minus": False,
    "legend.frameon": False,
    "axes.labelsize": 7,
    "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5,
    "xtick.major.width": 0.7,
    "ytick.major.width": 0.7,
    "xtick.major.size": 2.4,
    "ytick.major.size": 2.4,
    "axes.spines.top": False,
})
# Okabe-Ito 色盲友好调色板（语义映射：EC=蓝 / 非 EC=橙 / 恶化=红橙 / 良好=绿 / 未命中=灰）
C = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73",
     "red": "#D55E00", "purple": "#CC79A7", "sky": "#56B4E9", "yellow": "#F0E442",
     "black": "#000000", "grey": "#7F7F7F"}
BOXFC = "#F4F4F4"
W183 = 183 / 25.4  # 双栏最终印出宽度（英寸）

MIN_N = 30  # CD5 年度均值入图的最小样本量


def load(name, root=None):
    with open(os.path.join(root or DATA, name), encoding="utf-8") as f:
        return json.load(f)


def savefig(fig, name, panel_ids=None, exclude=(), exemptions=(),
            row_groups=None, col_groups=None):
    """导出 PNG+PDF；多面板图先过渲染时对齐门（1.5 pt），留档 alignment json。"""
    fig.canvas.draw()
    live = [ax for ax in fig.axes
            if ax.get_visible() and not str(ax.get_label()).startswith("<colorbar")]
    if len(live) >= 2:
        from audit_panel_alignment import require_matplotlib_panel_alignment
        require_matplotlib_panel_alignment(
            fig, json_out=os.path.join(OUT, name + ".alignment.json"),
            panel_ids=panel_ids, exclude_axes=list(exclude),
            exemptions=exemptions, row_groups=row_groups, column_groups=col_groups,
            tolerance_pt=1.5, gutter_tolerance_pt=1.5, strict=True)
    else:
        print("alignment gate: NOT APPLICABLE (single panel)", name)
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=300)
    fig.savefig(os.path.join(OUT, name + ".pdf"))
    fig.savefig(os.path.join(OUT, name + ".svg"))  # 矢量 QA 件（预检要求）
    plt.close(fig)
    print("saved", name)


def ptitle(ax, letter, text):
    """面板字母 8 pt 粗体独立 + 标题 7 pt 粗体（Nature 主刊规格）。"""
    ax.text(0.0, 1.06, letter, transform=ax.transAxes, fontsize=8,
            fontweight="bold", va="bottom", ha="left")
    ax.text(0.038, 1.06, text, transform=ax.transAxes, fontsize=7,
            fontweight="bold", va="bottom", ha="left")


def note(ax, x, y, s, color=None, fs=6.5, ha="left", va="center", box=True):
    kw = dict(fontsize=fs, color=color or C["grey"], ha=ha, va=va)
    if box:
        kw["bbox"] = dict(facecolor="white", edgecolor="none", alpha=0.88, pad=1.2)
    return ax.text(x, y, s, **kw)


def years_ax(ax, lo=2000, hi=2025, step=5):
    ax.set_xlim(lo, hi)
    ax.set_xticks(list(range(lo, hi + 1, step)))


# ============================ 主图 ============================

def fig1():
    """Fig 1 同框悖论门面：规模窄条 ×2 + 双端交换主格（含分子/分母带）+ 入口 + 同格。"""
    trade = load("trade.json")
    q = load("r3o_quantities.json")
    checks = load("checks.json")
    st = load("stability.json")
    bal = load("r3b_dims.json", R3B)["balance_stable"]
    fl = [r for r in trade["flow"] if not r.get("a_tier_only")]

    fig = plt.figure(figsize=(W183, 5.55))
    gs = gridspec.GridSpec(3, 2, figure=fig, height_ratios=[0.74, 1.5, 1.02],
                           hspace=0.62, wspace=0.24,
                           left=0.075, right=0.938, top=0.955, bottom=0.105)
    gsc = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=gs[1, :],
                                           height_ratios=[2.6, 1.0], hspace=0.12)
    axa = fig.add_subplot(gs[0, 0])
    axb = fig.add_subplot(gs[0, 1])
    axc = fig.add_subplot(gsc[0])
    axband = fig.add_subplot(gsc[1], sharex=axc)
    axd = fig.add_subplot(gs[2, 0])
    axe = fig.add_subplot(gs[2, 1])

    # a: EC 年发文量（柱）
    axa.bar([r["year"] for r in fl], [r["pool_EC"] for r in fl],
            color=C["blue"], alpha=0.82, width=0.82)
    axa.annotate("record high\n2024: 2,995", xy=(2024, 2995), xytext=(2008.5, 2450),
                 fontsize=6.5, color=C["grey"],
                 arrowprops=dict(arrowstyle="-", color=C["grey"], lw=0.6))
    axa.set_ylabel("EC papers per year")
    years_ax(axa)
    axa.set_xlim(1999.4, 2025.6)  # 首尾柱完整落框（视觉验收修正）
    axa.set_xlabel("Year")
    ptitle(axa, "a", "Output at record high")

    # b: NSGA-II 年被引（单源 OC）
    oc = checks["c3_nsga2_series"]["oc"]
    ys = sorted(int(y) for y in oc)
    axb.plot(ys, [oc[str(y)] for y in ys], color=C["green"], lw=1.3)
    axb.set_ylim(0, 5000)
    axb.annotate("2,636 (2020)", xy=(2020, 2636), xytext=(2007.5, 3350),
                 fontsize=6.5, color=C["grey"],
                 arrowprops=dict(arrowstyle="-", color=C["grey"], lw=0.6))
    axb.annotate("4,518 record high", xy=(2024.6, 4518), xytext=(2023.6, 4300),
                 fontsize=6.5, color=C["green"], ha="right",
                 arrowprops=dict(arrowstyle="-", color=C["green"], lw=0.6))
    axb.set_ylabel("citations per year")
    years_ax(axb)
    axb.set_xlabel("Year")
    ptitle(axb, "b", "Canon citations at record high")

    # c: 主格——双端篇均引用交换 + 底部分子/分母带
    axr = axc.twinx()
    axr.spines["right"].set_visible(True)
    ysb = sorted(int(y) for y in bal)
    inn = [bal[str(y)]["rate_NON_papers_cite_EC"] for y in ysb]
    out = [bal[str(y)]["rate_EC_papers_cite_NON"] for y in ysb]
    axc.plot(ysb, inn, color=C["red"], lw=1.7, zorder=3)
    axr.plot(ysb, out, color=C["sky"], lw=1.7, zorder=3)
    axc.set_ylim(0, 0.78)
    axr.set_ylim(0, 3.9)
    axc.set_ylabel("outside \u2192 EC,\nper non-EC paper", color=C["red"], fontsize=7)
    axr.set_ylabel("EC \u2192 outside,\nper EC paper", color=C["sky"], fontsize=7)
    axc.tick_params(axis="y", labelcolor=C["red"])
    axr.tick_params(axis="y", labelcolor=C["sky"])
    axc.axvline(2022, color=C["grey"], lw=0.7, ls="--", zorder=2)
    axc.text(2021.7, 0.755, "ChatGPT", fontsize=6, color=C["grey"], ha="right",
             va="top")
    note(axc, 2001.0, 0.66, "EC \u2192 outside stays at 2.8\u20133.2", color=C["sky"], fs=7)
    note(axc, 2021.5, 0.30, "\u221248% from 2021 peak\n0.686 \u2192 0.358", color=C["red"],
         fs=7, ha="right", va="top")
    plt.setp(axc.get_xticklabels(), visible=False)
    ptitle(axc, "c", "Citation exchange turns one-way")

    # 分子/分母带（防御②图面落地）：稳定集内非 EC 池规模 与 集内 NON→EC 边数
    # （2026-10-05 H0 修复：旧版误用全库池 pool_NON 作分母、并把 EC→NON 序列
    #   当 NON→EC 标注；现改用双端口径自身的分量——N_NON 与其×左轴率的导出边数，
    #   端点值均为 NUMBERS.md:263/265 登记值）
    pool = np.array([bal[str(y)]["N_NON"] for y in ysb])
    edges = np.array([bal[str(y)]["N_NON"] * bal[str(y)]["rate_NON_papers_cite_EC"]
                      for y in ysb])
    fy = ysb
    # 上下文带：两条细线各占上/下半区（仅示形状，量值见标签与图注）；
    # 标签置于右半区两线之间的空带
    axband.plot(fy, 0.5 + 0.5 * pool / pool.max(), lw=1.0, color="#9A9A9A")
    axband.plot(fy, 0.06 + 0.4 * edges / edges.max(), lw=1.0, color="#4D4D4D",
                ls="--")
    axband.set_ylim(0, 1.15)
    axband.set_yticks([])
    axband.set_xlabel("Year")
    years_ax(axband)

    # d: 入口 teaser（新人首选单线）
    fs_ = q["first_choice_share"]
    ysd = sorted(int(y) for y in fs_)
    axd.plot(ysd, [fs_[str(y)] * 100 for y in ysd], color=C["red"], lw=1.4)
    axd.set_ylim(0, 56)
    axd.annotate("44.8% (2005)", xy=(2005.2, 44.8), xytext=(2007.5, 48.5),
                 fontsize=6.5, color=C["grey"],
                 arrowprops=dict(arrowstyle="-", color=C["grey"], lw=0.6))
    axd.annotate("13.5%", xy=(2025, 13.5), xytext=(2020.5, 6.5),
                 fontsize=6.5, color=C["grey"], ha="right",
                 arrowprops=dict(arrowstyle="-", color=C["grey"], lw=0.6))
    axd.set_ylabel("newcomers' first choice (%)")
    years_ax(axd)
    axd.set_xlabel("Year")
    ptitle(axd, "d", "Entry shifts outward")

    # e: 二维同格 8/8 森林图
    cells = {}
    for k, v in st["c_cd5_2d_strata"].items():
        win, grp, rp, rq = k.split("|")
        if win == "2018-20":
            cells.setdefault((rp, rq), {})[grp] = v
    rows = []
    for (rp, rq), g in cells.items():
        if "EC" in g and "NON_EC" in g:
            rows.append((rp.replace("Rp", "").replace("-", "\u2013"),
                         rq.replace("Rq", "").replace("-", "\u2013"),
                         g["EC"]["mean"] - g["NON_EC"]["mean"], g["EC"]["n"]))
    rows.sort(key=lambda r: r[2], reverse=True)
    nmax = max(r[3] for r in rows)
    for i, (rp, rq, gap, n) in enumerate(rows):
        w = 0.05 * (n / nmax) ** 0.5
        axe.plot([gap - w, gap + w], [i, i], color=C["black"], lw=1.3,
                 solid_capstyle="butt")
        axe.plot(gap, i, "o", color=C["red"], ms=3.2)
        axe.text(0.055, i, f"n={n}", fontsize=6, va="center", ha="left",
                 color=C["grey"])
    axe.axvline(0, color=C["black"], lw=0.8)
    axe.set_yticks(range(len(rows)))
    axe.set_yticklabels([f"{r[0]}|{r[1]}" for r in rows], fontsize=6.5)
    axe.set_xlim(-0.40, 0.22)
    axe.set_ylim(-3.4, len(rows) - 0.3)
    axe.set_xlabel("EC \u2212 non-EC CD5 gap within cell")
    note(axe, -0.385, -1.9, "8/8 cells negative (\u22120.08 to \u22120.25)\n"
         "coverage EC 84.1% / non-EC 67.0%", fs=6.5, va="center")
    ptitle(axe, "e", "Within-cell gaps (Rp | Rq), all negative")

    fig.text(0.075, 0.006, "Context band under c: grey solid = non-EC pool in the "
             "fixed venue set (denominator), 2,747→7,681, +180% since 2017;\n"
             "dark grey dashed = non-EC→EC edges in the set (numerator), "
             "2,964 (2021) → 2,749 (2025)",
             fontsize=6, color=C["grey"], ha="left", va="bottom")
    savefig(fig, "fig1",
            panel_ids={axa: "a", axb: "b", axc: "c", axd: "d", axe: "e"},
            exclude=[axband, axr],
            exemptions=[{"panels": ["c"], "checks": ["all"],
                         "reason": "hero panel spans both columns; numerator/"
                                   "denominator context band is a nested strip, "
                                   "not a comparable panel"}],
            row_groups=[{"id": "row-top", "panels": ["a", "b"]},
                        {"id": "row-bottom", "panels": ["d", "e"]}],
            col_groups=[{"id": "col-left", "panels": ["a", "d"]},
                        {"id": "col-right", "panels": ["b", "e"]}])


def fig2():
    """Fig 2 腿 3：CD5 十五年分化与四类对照（a 主格 cohort 曲线 + n 带）。"""
    dis = load("disruption.json")
    stab = load("stability.json")
    w4a = load("w4a.json")

    fig = plt.figure(figsize=(W183, 5.35))
    gs = gridspec.GridSpec(2, 2, figure=fig, height_ratios=[1.28, 1.0],
                           hspace=0.62, wspace=0.34,
                           left=0.085, right=0.985, top=0.945, bottom=0.085)
    gsa = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=gs[0, 0],
                                           height_ratios=[3.2, 1.0], hspace=0.10)
    axa = fig.add_subplot(gsa[0])
    axn = fig.add_subplot(gsa[1], sharex=axa)
    axb = fig.add_subplot(gs[0, 1])
    axc = fig.add_subplot(gs[1, 0])
    axd = fig.add_subplot(gs[1, 1])

    # a: cohort CD5 三曲线 + 底部 n 带
    for key, color, ls, label in (("EC", C["blue"], "-", "EC"),
                                  ("NON_EC", C["orange"], "-", "non-EC"),
                                  ("A_pure_ec", C["green"], (0, (4, 1, 1, 1)),
                                   "A-tier EC journals")):
        xs, ys = [], []
        for r in dis:
            g = r.get(key)
            if g and g.get("n", 0) >= MIN_N:
                xs.append(r["year"])
                ys.append(g["mean"])
        axa.plot(xs, ys, lw=1.3, color=color, ls=ls, label=label)
    axa.axhline(0, color="grey", lw=0.6, ls="--")
    axa.set_ylabel("CD5 mean (5-yr window)")
    axa.legend(fontsize=6, loc="upper right")
    axa.set_ylim(-0.52, 0.60)
    note(axa, 2002.3, -0.46, "divergence after 2010", fs=6.5)
    ptitle(axa, "a", "Divergence, same corpus")
    for key, color, dx in (("EC", C["blue"], -0.22), ("NON_EC", C["orange"], 0.22)):
        xs, ns = [], []
        for r in dis:
            g = r.get(key)
            if g and g.get("n", 0) >= MIN_N:
                xs.append(r["year"])
                ns.append(g["n"])
        axn.bar([x + dx for x in xs], ns, width=0.42, color=color, alpha=0.7)
    axn.set_ylabel("n (papers)", fontsize=6.5)
    axn.set_xlabel("Publication cohort year")
    axn.set_xticks(list(range(2002, 2021, 3)))
    axn.tick_params(labelsize=6.5)
    plt.setp(axa.get_xticklabels(), visible=False)

    # b: 二维同格两期段差距 + 格内 n
    strata = stab["c_cd5_2d_strata"]

    def cell_gap(era, rp, rq):
        e = strata.get(f"{era}|EC|Rp{rp}|Rq{rq}")
        n = strata.get(f"{era}|NON_EC|Rp{rp}|Rq{rq}")
        if e and n:
            return e["mean"] - n["mean"]
        return None

    order = {"5-10": 0, "11-20": 1, "21-40": 2, ">40": 3}
    cellset = set()
    for k in strata:
        era, grp, rp, rq = k.split("|")
        if era == "2018-20":
            cellset.add((rp[2:], rq[2:]))
    cells = sorted([c for c in cellset if cell_gap("2018-20", *c) is not None],
                   key=lambda t: (order[t[0]], order[t[1]]))
    w = 0.38
    for i, (rp, rq) in enumerate(cells):
        g1 = cell_gap("2018-20", rp, rq)
        n1 = strata[f"2018-20|EC|Rp{rp}|Rq{rq}"]["n"]
        axb.bar(i, g1, width=w, color=C["blue"],
                label="2018–20 gap" if i == 0 else None)
        axb.text(i, g1 - 0.012, f"{n1}", fontsize=6, ha="center", va="top",
                 color=C["grey"])
        g0 = cell_gap("2005-07", rp, rq)
        if g0 is not None:
            axb.bar(i + w, g0, width=w, color=C["grey"],
                    label="2005\u201307 gap" if i == 0 else None)
    axb.axhline(0, color=C["black"], lw=0.8)
    axb.set_ylim(-0.31, 0.09)  # 底部留白容纳条端 n 标签
    axb.set_xticks([i + w / 2 for i in range(len(cells))])
    axb.set_xticklabels([f"{rp}|{rq}" for rp, rq in cells], fontsize=6,
                        rotation=50, ha="right", rotation_mode="anchor")
    axb.set_xlabel("Cited-side Rp | citing-side Rq", labelpad=2)
    axb.set_ylabel("CD5 gap (EC \u2212 non-EC)")
    axb.legend(fontsize=6, loc="upper right")
    ptitle(axb, "b", "Within-stratum gaps (n labelled)")

    # c: 稳定 8 刊对照
    ser = stab["b_stable_control_cd5"]["series"]
    for key, color, ls, label in (
            ("EC", C["blue"], "-", "EC"),
            ("NON_EC_all", C["orange"], "-", "non-EC (all sources)"),
            ("NON_EC_stable", C["green"], "--", "non-EC (8 stable sources)")):
        rows = ser[key]
        axc.plot([r["year"] for r in rows], [r["mean"] for r in rows],
                 lw=1.3, color=color, ls=ls, label=label)
    axc.axhline(0, color="grey", lw=0.6, ls="--")
    axc.set_xlabel("Publication cohort year")
    axc.set_xticks(list(range(2002, 2021, 3)))
    axc.set_ylabel("CD5 mean")
    axc.legend(fontsize=6, loc="lower left")
    ptitle(axc, "c", "Stable-source control")

    # d: 刊内 8/8
    short = {"IEEE Transactions on Evolutionary Computation": "IEEE TEVC",
             "Information Sciences": "Inf. Sci.",
             "Applied Soft Computing Journal": "Appl. Soft Comp.",
             "Lecture Notes in Computer Science (including subseries Lecture Notes in Artificial Intelligence and Lecture Notes in Bioinformatics)": "LNCS",
             "Expert Systems with Applications": "Expert Syst. Appl.",
             "European Journal of Operational Research": "EJOR",
             "Computers and Operations Research": "Comput. Oper. Res.",
             "Computers and Industrial Engineering": "Comput. Ind. Eng."}
    swd = w4a["source_within_decline"]
    items = sorted(swd.items(), key=lambda kv: kv[1]["delta"])
    names = [short.get(k, k[:18]) for k, _ in items]
    deltas = [v["delta"] for _, v in items]
    ypos = range(len(items))
    axd.barh(list(ypos), deltas, height=0.62, color=C["blue"])
    for y, d in zip(ypos, deltas):
        axd.text(d - 0.012, y, f"{d:.2f}", va="center", ha="right", fontsize=6,
                 color=C["black"])
    axd.set_yticks(list(ypos))
    axd.set_yticklabels(names, fontsize=6.5)
    axd.axvline(0, color=C["black"], lw=0.8)
    axd.set_xlim(-0.62, 0.12)
    axd.set_xlabel("\u0394 EC CD5 (2013\u201320 minus 2003\u201310, same source)")
    ptitle(axd, "d", "Within-source decline (8/8)")

    savefig(fig, "fig2",
            panel_ids={axa: "a", axb: "b", axc: "c", axd: "d"},
            exclude=[axn],
            exemptions=[{"panels": ["a"], "checks": ["all"],
                         "reason": "panel a carries a nested sample-size strip "
                                   "sharing its x axis; the strip is not a "
                                   "comparable panel"}],
            row_groups=[{"id": "row-1", "panels": ["a", "b"]},
                        {"id": "row-2", "panels": ["c", "d"]}],
            col_groups=[{"id": "col-1", "panels": ["a", "c"]},
                        {"id": "col-2", "panels": ["b", "d"]}])


def fig3():
    """Fig 3 腿 2：入口重组（家族级主格 + 首选/校正 + 迁移/参与率）。"""
    r3a = load("r3a_results.json", R3A)
    q = load("r3o_quantities.json")
    auth = load("authors.json")
    w6 = load("authors_flow.json", W6)

    fig = plt.figure(figsize=(W183, 5.35))
    gs = gridspec.GridSpec(2, 2, figure=fig, height_ratios=[1.18, 1.0],
                           hspace=0.55, wspace=0.30,
                           left=0.16, right=0.945, top=0.945, bottom=0.085)
    axa = fig.add_subplot(gs[0, :])
    axb = fig.add_subplot(gs[1, 0])
    axc = fig.add_subplot(gs[1, 1])

    # a: 家族级首选变化（资格族 9；不合格族以文字披露）
    disp = {"ga": "Genetic algorithms", "genetic_programming": "Genetic programming",
            "general_ec": "General EC", "evolution_strategies": "Evolution strategies",
            "memetic_hybrid": "Memetic hybrid",
            "other_metaheuristic": "Other metaheuristics", "OTHER": "Other",
            "emo": "Multi-objective (EMO)", "particle_swarm": "Particle swarm"}
    elig = [s for s in r3a["subfamilies"] if s["eligible"]]
    elig.sort(key=lambda s: -s["rel_decline"])
    ypos = list(range(len(elig)))
    vals = [-s["rel_decline"] * 100 for s in elig]
    cols = [C["red"] if v < 0 else C["green"] for v in vals]
    axa.barh(ypos, vals, height=0.62, color=cols)
    for y, v in zip(ypos, vals):
        axa.text(v + (2.5 if v >= 0 else -2.5), y, f"{v:+.1f}%", va="center",
                 ha="left" if v >= 0 else "right", fontsize=6.2, color=C["black"])
    axa.set_yticks(ypos)
    axa.set_yticklabels([disp[s["family"]] for s in elig], fontsize=6.8)
    axa.axvline(0, color=C["black"], lw=0.8)
    axa.set_xlim(-95, 55)
    axa.set_xlabel("Relative change in newcomers' first-direction share, "
                   "2003\u201307 \u2192 2019\u201322 (%)")
    note(axa, 54, 6.6, "not eligible (n<200 per period),\ndisclosure only: "
         "other_swarm_bio\n119\u21921,697 (\u00d74.8); diff._evolution 143\u2192868",
         fs=6.2, va="top", ha="right")
    ptitle(axa, "a", "Entry reorganises, not closes")

    # b: 首选份额 + 构成校正比（双锚双版）
    axbr = axb.twinx()
    axbr.spines["right"].set_visible(True)
    fcs = q["first_choice_share"]
    ys = sorted(int(y) for y in fcs)
    axb.plot(ys, [fcs[str(y)] * 100 for y in ys], color=C["red"], lw=1.4,
             label="first-choice share")
    crp = q["corrected_first_choice_ratio_paper_weight"]
    crs = q["corrected_first_choice_ratio_slot_weight"]
    yp = sorted(int(y) for y in crp)
    axbr.plot(yp, [crp[str(y)] for y in yp], color=C["purple"], lw=1.1, ls="--",
              label="corrected, paper weight")
    axbr.plot(sorted(int(y) for y in crs),
              [crs[str(y)] for y in sorted(int(y) for y in crs)],
              color=C["purple"], lw=1.1, ls=":", label="corrected, slot weight")
    axb.set_ylim(0, 56)
    axbr.set_ylim(0.55, 1.0)
    axb.set_ylabel("first choice (%)", color=C["red"])
    axbr.set_ylabel("corrected ratio", color=C["purple"])
    axb.tick_params(axis="y", labelcolor=C["red"])
    axbr.tick_params(axis="y", labelcolor=C["purple"])
    axb.annotate("44.8% (2005)", xy=(2005.2, 44.8), xytext=(2006.6, 49.5),
                 fontsize=6.5, color=C["grey"],
                 arrowprops=dict(arrowstyle="-", color=C["grey"], lw=0.6))
    axb.annotate("13.5%", xy=(2025, 13.5), xytext=(2021.0, 6.0),
                 fontsize=6.5, color=C["grey"], ha="right",
                 arrowprops=dict(arrowstyle="-", color=C["grey"], lw=0.6))
    note(axb, 2024.8, 55.0, "2003\u21922025 corrected:\npaper 0.930\u21920.663\n"
         "slot 0.906\u21920.714", color=C["purple"], fs=6.2, va="top", ha="right")
    years_ax(axb)
    axb.set_xlabel("Year")
    h1, l1 = axb.get_legend_handles_labels()
    h2, l2 = axbr.get_legend_handles_labels()
    axb.legend(h1 + h2, l1 + l2, fontsize=6, loc="lower left")
    ptitle(axb, "b", "First choice, composition-corrected")

    # c: 迁移期段点 + 新人参与率稳定线
    axcr = axc.twinx()
    axcr.spines["right"].set_visible(True)
    ent = auth["entrants"]
    ey = [r["year"] for r in ent]
    axc.plot(ey, [r["share_papers_with_newcomer"] * 100 for r in ent],
             color=C["green"], lw=1.3, label="newcomer participation")
    per = w6["meta"]["periods"]
    mids, migs = [], []
    for i, flw in enumerate(w6["flow_full"]):
        ec_end = (flw["EC->EC"] + flw["EC->NON"] + flw["EC->mixed"]
                  + flw["EC->absent"])
        mids.append((per[i][1] + per[i + 1][0]) / 2)
        migs.append(flw["EC->NON"] / ec_end * 100)
    axcr.plot(mids, migs, "s", color=C["purple"], ms=4,
              label="EC\u2192non-EC migration (per period)")
    axc.set_ylim(60, 90)
    axcr.set_ylim(0, 14)
    axc.set_ylabel("participation (%)", color=C["green"])
    axcr.set_ylabel("EC\u2192non-EC migration (%)", color=C["purple"])
    axc.tick_params(axis="y", labelcolor=C["green"])
    axcr.tick_params(axis="y", labelcolor=C["purple"])
    note(axc, 2003.6, 63.5, "participation stable 76\u201380%\nmigration 4.6%\u21928.9%; "
         "net flow \u22481.6\u00d7\nname-string identity: ~8% bound", fs=6.2)
    years_ax(axc)
    axc.set_xlabel("Year")
    h1, l1 = axc.get_legend_handles_labels()
    h2, l2 = axcr.get_legend_handles_labels()
    axc.legend(h1 + h2, l1 + l2, fontsize=6, loc="upper right")
    ptitle(axc, "c", "Authors drift outward, entry stays open")

    savefig(fig, "fig3",
            panel_ids={axa: "a", axb: "b", axc: "c"},
            exclude=[axbr, axcr],
            row_groups=[{"id": "row-2", "panels": ["b", "c"]}],
            exemptions=[{"panels": ["a"], "checks": ["all"],
                         "reason": "hero panel spans both columns"}])


def fig4():
    """Fig 4 边界与机制排除：引用年龄 / 议程两侧 / 资金零结果。
    2026-10-05：LLM 渗透格撤出（联合评审 gpt 建议——该格把读者带向另一篇
    "AI 与科学议程"的论文）；LLM/GPT 词组份额改在 §2.4 文字给出（登记值）。"""
    m = load("memory.json")
    r3b = load("r3b_dims.json", R3B)
    fund = load("funding_agenda.json", W8)

    fig = plt.figure(figsize=(W183, 5.15))
    gs = gridspec.GridSpec(2, 2, figure=fig, height_ratios=[1.0, 0.72],
                           hspace=0.42, wspace=0.26,
                           left=0.085, right=0.985, top=0.945, bottom=0.085)
    axa = fig.add_subplot(gs[0, 0])
    axb = fig.add_subplot(gs[0, 1])
    axc = fig.add_subplot(gs[1, :])

    # a: 引用年龄偏好比三源 + 队列口径 inset
    for src, color, ls in (("oc", C["blue"], "-"), ("s2", C["sky"], "--"),
                           ("all", C["grey"], ":")):
        rows = m[f"youth_bias_{src}"]
        axa.plot([r["year"] for r in rows], [r["I1_over_I6"] for r in rows],
                 lw=1.2, color=color, ls=ls, label=src)
    axa.annotate("0.472 (2006)", xy=(2006, 0.472), xytext=(2008.5, 0.35),
                 fontsize=6.5, color=C["grey"],
                 arrowprops=dict(arrowstyle="-", color=C["grey"], lw=0.6))
    axa.set_ylim(0.2, 2.2)
    axa.annotate("1.607 (2024)", xy=(2024, 1.65), xytext=(2024.8, 2.12),
                 fontsize=6.5, color=C["grey"], ha="right", va="top",
                 arrowprops=dict(arrowstyle="-", color=C["grey"], lw=0.6))
    axa.set_ylabel("new-ref preference ratio\n(\u22641 yr / \u22656 yrs citations)")
    axa.legend(fontsize=6, loc="lower right")
    years_ax(axa)
    axa.set_xlabel("Citing year")
    ptitle(axa, "a", "Citation age shifts, three sources")
    axin = axa.inset_axes([0.05, 0.60, 0.40, 0.34])
    rows = [r for r in m["cohort_windows"]
            if r["year"] <= m["cohort_windows_complete_through"]]
    axin.plot([r["year"] for r in rows],
              [r["early_share_01_of_0_3"] * 100 for r in rows],
              lw=1.0, color=C["blue"])
    axin.set_yticks([])
    axa.text(0.05, 0.965, "cohort-fixed, 26.1%\u219237.0%",
             transform=axa.transAxes, ha="left", va="bottom",
             fontsize=6, color=C["grey"])
    axin.tick_params(labelsize=6)
    for s in ("top", "right"):
        axin.spines[s].set_visible(False)

    # b: 议程外部化两侧
    ag = r3b["agenda_external_sum"]
    for key, color, label in (("EC_any", C["red"], "field (EC)"),
                              ("NON_any", C["orange"], "comparison (non-EC)")):
        d = ag[key]
        ys = sorted(int(y) for y in d)
        axb.plot(ys, [d[str(y)]["external_sum"] * 100 for y in ys], lw=1.3,
                 color=color, label=label)
    axb.set_ylim(0, 36)
    note(axb, 2024.8, 35.4, "28.9%", color=C["orange"], fs=6.5, ha="right",
         va="top")
    note(axb, 2024.8, 32.6, "15.4%", color=C["red"], fs=6.5, ha="right", va="top")
    axb.set_ylabel("external-topic share (%)")
    axb.legend(fontsize=6, loc="upper left")
    note(axb, 2001, 13, "both sides externalise;\ncomparison more so", fs=6.2)
    years_ax(axb)
    axb.set_xlabel("Year")
    ptitle(axb, "b", "Agenda externalises on both sides")

    # c: 资金零结果（lag-0 同步）——原 d 格（2026-10-05 LLM 渗透格撤出后顶替）
    ecg = ag["EC_any"]
    fys = sorted(int(y) for y in fund["funded_subset_share"])
    axc.plot(fys, [fund["funded_subset_share"][str(y)]["external_sum"] * 100
                   for y in fys], lw=1.3, color=C["orange"],
             label="funded subset")
    axc.plot(fys, [ecg[str(y)]["external_sum"] * 100 for y in fys], lw=1.3,
             color=C["red"], ls="--", label="all EC papers")
    axc.set_ylabel("external-topic share (%)")
    axc.set_xlabel("Year")
    axc.set_xticks([2016, 2020, 2025])
    axc.set_ylim(0, 19)
    axc.legend(fontsize=6, loc="lower right")
    note(axc, 2016.3, 18.4, "level r = 0.979\u20130.996, max at lag 0\n"
         "first-difference lag-0 r = +0.926\nno funding-led signal", fs=6.2,
         va="top")
    ptitle(axc, "c", "Funding moves with, not ahead of, agenda")

    savefig(fig, "fig4",
            panel_ids={axa: "a", axb: "b", axc: "c"},
            exclude=[axin],
            exemptions=[{"panels": ["a"], "checks": ["all"],
                         "reason": "cohort-fixed variant shown as an inset; "
                                   "not a comparable panel"}])


def fig5():
    """Fig 5 校准与交付：泳道（含窗外带）+ 提前量点带（真坐标轴）+ 协议横条。"""
    t = load("early_warning_table.json")

    fig = plt.figure(figsize=(W183, 5.6))
    gs = gridspec.GridSpec(2, 2, figure=fig, height_ratios=[1.42, 1.0],
                           hspace=0.42, wspace=0.24,
                           left=0.115, right=0.985, top=0.955, bottom=0.085)
    axa = fig.add_subplot(gs[0, :])
    axb = fig.add_subplot(gs[1, 0])
    axc = fig.add_subplot(gs[1, 1])

    # a: 三案例泳道 + 对照行 + 窗外灰带
    lanes = {"expert_systems": 3, "symbolic_ai": 2, "fuzzy_logic": 1}
    events = {"expert_systems": 1987, "symbolic_ai": 1994, "fuzzy_logic": 2000}
    YMIN, YMAX = -1.75, 4.15
    for case, ev in events.items():
        yl = lanes[case]
        lo = (yl - 0.42 - YMIN) / (YMAX - YMIN)
        hi = (yl + 0.42 - YMIN) / (YMAX - YMIN)
        axa.axvspan(1975, ev - 10, ymin=lo, ymax=hi, color="grey", alpha=0.12,
                    lw=0, edgecolor="none", zorder=0)
    axa.text(1975.3, 3.82, "outside the 1\u201310 y window", fontsize=6,
             color=C["grey"], va="bottom")
    metric_lbl = {"m1_median_age": "median cited age", "m1_share_ge5": "share \u22655y",
                  "m3_theme_share": "external-theme share"}
    metric_col = {"m1_median_age": C["blue"], "m1_share_ge5": C["sky"],
                  "m3_theme_share": C["orange"]}
    # 预计算同年/邻年点的标签水平错开（成对：左标签右对齐、右标签左对齐）
    off = {}
    for case in lanes:
        rs = sorted((r for r in t["rows"]
                     if r["case"] == case and r["lead_years"] != -22),
                    key=lambda r: r["turning_year"])
        for r0, r1 in zip(rs, rs[1:]):
            if r1["turning_year"] - r0["turning_year"] < 2:
                off[id(r0)] = (-7, "right")
                off[id(r1)] = (7, "left")
    n22 = 0
    for r in t["rows"]:
        y = lanes[r["case"]]
        hit = r.get("hit")
        x = r["turning_year"]
        if r["lead_years"] == -22:  # 两条超窗读数同年：抖动 + 合并标签
            x += -0.25 if n22 == 0 else 0.25
            n22 += 1
            axa.plot(x, y, "o", ms=4.6, color=C["grey"], mec="none", zorder=3)
            continue
        axa.plot(x, y, "o", ms=4.6,
                 color=metric_col[r["metric"]] if hit else C["grey"],
                 mec="none", zorder=3)
        dx, ha = off.get(id(r), (0, "center"))
        axa.annotate(f"{r['lead_years']:+d}", (x, y),
                     xytext=(dx, 6.5), textcoords="offset points", fontsize=6,
                     ha=ha, color=C["black"] if hit else C["grey"])
    axa.annotate("\u221222 \u00d72", (1978, 1), xytext=(0, 6.5),
                 textcoords="offset points", fontsize=6, ha="center",
                 color=C["grey"])
    for case, y in lanes.items():
        lo = (y - 0.42 - YMIN) / (YMAX - YMIN)
        hi = (y + 0.42 - YMIN) / (YMAX - YMIN)
        axa.axvline(events[case], ymin=lo, ymax=hi, color=C["black"], lw=1.0,
                    ls="--", zorder=2)
        axa.text(events[case], y + 0.55, str(events[case]), fontsize=6,
                 ha="center", color=C["black"])
    lo = (1 - 0.42 - YMIN) / (YMAX - YMIN)
    hi = (1 + 0.42 - YMIN) / (YMAX - YMIN)
    axa.axvline(1991, ymin=lo, ymax=hi, color=C["grey"], lw=0.8, ls=":", zorder=2)
    axa.text(1991, 1.55, "1991*", fontsize=6, ha="center", color=C["grey"])
    seen = {}
    for case, ms in t["negative_controls"].items():
        for m_, d in ms.items():
            yr = d.get("turning_year")
            if yr is None:
                continue
            k = seen.get(yr, 0)
            seen[yr] = k + 1
            axa.plot(yr + (k - 0.5) * 1.1, 0, "x", ms=4.6, color=C["purple"],
                     zorder=3)
    axa.axhline(0.55, color=C["grey"], lw=0.5)
    axa.set_yticks([3, 2, 1, 0])
    axa.set_yticklabels(["expert systems", "symbolic AI", "fuzzy logic",
                         "2 controls"], fontsize=6.8)
    axa.set_xlim(1975, 2012)
    axa.set_ylim(YMIN, YMAX)
    axa.set_xlabel("Year")
    note(axa, 1975.8, -0.95, "6/9 readings turned 1\u201310 y before the event "
         "(median 4.5); the same rule fired 7 false signals (\u00d7) on the two "
         "controls\n1991* = industrial-anchor sensitivity for fuzzy logic; "
         "grey = miss, colours = indicator", fs=6.2, va="center")
    handles = [plt.Line2D([], [], marker="o", ls="", color=metric_col[m_],
                          label=metric_lbl[m_]) for m_ in metric_col]
    handles.append(plt.Line2D([], [], marker="o", ls="", color=C["grey"],
                              label="miss"))
    handles.append(plt.Line2D([], [], marker="x", ls="", color=C["purple"],
                              label="false signal"))
    axa.legend(handles=handles, fontsize=6, frameon=False, loc="upper right",
               bbox_to_anchor=(0.995, 0.80))
    ptitle(axa, "a", "Calibration against three field winters")

    # b: 提前量点带（真坐标轴）
    axb.axhspan(1, 10, color="grey", alpha=0.12, zorder=0)
    axb.text(2.45, 10.4, "1\u201310 y window", fontsize=6, color=C["grey"],
             va="bottom", ha="right")
    case_x = {"expert_systems": 0, "symbolic_ai": 1, "fuzzy_logic": 2}
    jit = {}
    for r in t["rows"]:
        if not r.get("hit"):
            continue
        k = jit.get(r["case"], 0)
        jit[r["case"]] = k + 1
        axb.plot(case_x[r["case"]] + (k - 0.5) * 0.16, abs(r["lead_years"]), "o",
                 ms=4.6, color=metric_col[r["metric"]], mec="none", zorder=3)
    for r in t["rows"]:
        if r.get("hit") is False and abs(r["lead_years"]) > 10:
            k = jit.get(r["case"], 0)
            jit[r["case"]] = k + 1
            axb.plot(case_x[r["case"]] + (k - 0.5) * 0.16, abs(r["lead_years"]),
                     "o", ms=4.6, color=C["grey"], mec="none", zorder=3)
    axb.axhline(4.5, color=C["black"], lw=0.7, ls="--")
    axb.text(2.42, 4.8, "median 4.5", fontsize=6, color=C["black"], ha="right")
    axb.text(0.02, 22.4, "2 misses at 22 y: outside the window,\nnot counted "
             "in 6/9", fontsize=6, color=C["grey"], va="top")
    axb.set_xticks([0, 1, 2])
    axb.set_xticklabels(["expert\nsystems", "symbolic\nAI", "fuzzy\nlogic"],
                        fontsize=6.5)
    axb.set_xlim(-0.5, 2.5)
    axb.set_ylim(0, 24)
    axb.set_ylabel("lead time (years before event)")
    ptitle(axb, "b", "Lead times, window and misses")

    # c: 四级协议横条
    axc.axis("off")
    axc.set_xlim(0, 10)
    axc.set_ylim(0, 10)
    steps = ["Vitality readings\nper field-year",
             "3-yr rolling means;\nturn = sustained\nsign change",
             "Alarm = 2+ dims turned\nin same 3-yr window",
             "Pre-frozen rules;\ncalibration:\ndirection only"]
    pos = [(2.7, 7.6), (7.3, 7.6), (7.3, 3.9), (2.7, 3.9)]
    for (x, y), s in zip(pos, steps):
        axc.text(x, y, s, ha="center", va="center", fontsize=6,
                 bbox=dict(boxstyle="round,pad=0.4", fc=BOXFC, ec=C["grey"],
                           lw=0.8))
    for (x0, y0), (x1, y1) in zip(pos[:-1], pos[1:]):
        if y0 == y1:
            sx = 1.75 if x1 > x0 else -1.75
            axc.annotate("", xy=(x1 - sx, y1), xytext=(x0 + sx, y0),
                         arrowprops=dict(arrowstyle="-|>", color=C["black"],
                                         lw=0.9))
        else:
            axc.annotate("", xy=(x1, y1 + 1.05), xytext=(x0, y0 - 1.05),
                         arrowprops=dict(arrowstyle="-|>", color=C["black"],
                                         lw=0.9))
    axc.text(9.9, 0.9, "rules frozen before the observations; full rule text "
             "in Supplementary Methods", fontsize=6, color=C["grey"],
             va="center", ha="right")
    ptitle(axc, "c", "Monitoring protocol (four stages)")

    savefig(fig, "fig5",
            panel_ids={axa: "a", axb: "b", axc: "c"},
            row_groups=[{"id": "row-2", "panels": ["b", "c"]}],
            exemptions=[{"panels": ["a"], "checks": ["all"],
                         "reason": "swim-lane panel spans both columns"}])


# ============================ Extended Data ============================

def ed1():
    """ED1 测量设计总览（每框挂一个登记数字；b 排布收紧）。"""
    fig, (axa, axb) = plt.subplots(1, 2, figsize=(W183, 3.5),
                                   gridspec_kw={"width_ratios": [1.05, 1]})
    NL = chr(10)
    axa.set_xlim(0, 10)
    axa.set_ylim(0, 10)
    axa.axis("off")
    steps = [
        ("Corpus" + NL + "146,785 papers, 2000\u20132025", C["grey"]),
        ("Field labelling" + NL + "47,834 papers; gold standard n = 200, 97%",
         C["blue"]),
        ("In-corpus citation edges" + NL + "922,842 edges; 607,204 rows "
         "right-censored", C["blue"]),
        ("Four behavioural readings" + NL + "outward strength / first direction / "
         "disruption / citation age", C["black"]),
        ("Comparison design" + NL + "stable 8-venue set; 2-D strata; seven external "
         "panels", C["green"]),
    ]
    ys = [8.9, 6.95, 5.0, 3.05, 1.1]
    for (txt, ec), y in zip(steps, ys):
        axa.text(5, y, txt, ha="center", va="center", fontsize=6.8,
                 bbox=dict(boxstyle="round,pad=0.45", fc=BOXFC, ec=ec, lw=0.8))
    for y0, y1 in zip(ys[:-1], ys[1:]):
        axa.annotate("", xy=(5, y1 + 0.62), xytext=(5, y0 - 0.62),
                     arrowprops=dict(arrowstyle="-|>", color=C["black"], lw=0.9))
    ptitle(axa, "a", "Measurement pipeline")

    axb.set_xlim(0, 10)
    axb.set_ylim(0, 10)
    axb.axis("off")
    bands = [
        ("Citation-channel resolution",
         "0.406 (field) vs 0.151 (comparison), 2025;\ndisruption index monotone in "
         "reference density;\nall comparisons made within strata", C["red"]),
        ("Temporal range",
         "in-corpus 2000\u20132025; cohorts to 2020; benchmark-suite technical "
         "report outside the corpus boundary", C["grey"]),
        ("External panels",
         "96,170 papers across seven fields;\nlow-resolution outline of direction "
         "only;\ncross-database readings not comparable", C["purple"]),
    ]
    ys2 = [8.3, 5.2, 2.1]
    for (head, body, ec), y in zip(bands, ys2):
        axb.text(5, y, head + NL + body, ha="center", va="center", fontsize=6.8,
                 bbox=dict(boxstyle="round,pad=0.45", fc="#FBFBFB", ec=ec, lw=0.9))
    ptitle(axb, "b", "Range and blind spots")
    fig.tight_layout()
    savefig(fig, "ed8")


def ed2():
    """ED2 语料份额与构成（两版权重；构成敏感读数，不作行为读数使用）。"""
    q = load("r3o_quantities.json")
    fig, ax = plt.subplots(figsize=(89 / 25.4, 2.7))
    pw = q["ec_corpus_share_paper_weight"]
    sw = q["ec_corpus_share_slot_weight"]
    yp = sorted(int(y) for y in pw)
    ax.plot(yp, [pw[str(y)] * 100 for y in yp], color=C["blue"], lw=1.2,
            label="paper weight")
    ys = sorted(int(y) for y in sw)
    ax.plot(ys, [sw[str(y)] * 100 for y in ys], color=C["sky"], lw=1.1, ls="--",
            label="slot weight")
    ax.annotate("peak 49.9% (2005)", xy=(2005, 49.9), xytext=(2007.5, 51.5),
                fontsize=6, color=C["grey"],
                arrowprops=dict(arrowstyle="-", color=C["grey"], lw=0.6))
    ax.annotate("20.4%", xy=(2025, 20.4), xytext=(2019.5, 13.5), fontsize=6,
                color=C["grey"],
                arrowprops=dict(arrowstyle="-", color=C["grey"], lw=0.6))
    ax.set_ylim(0, 58)
    ax.set_ylabel("EC share of corpus (%)")
    ax.set_xlabel("Year")
    ax.legend(fontsize=6, loc="lower left")
    note(ax, 2024.8, 57, "composition-sensitive:\nnot used as a\nbehavioural "
         "reading", fs=6, ha="right", va="top")
    fig.tight_layout()
    savefig(fig, "ed2")


def ed3():
    """ED3 CD 窗口变体 + 二维同格热图（原 ED3 + 原 ED6 合并）。"""
    w = load("w4a.json")
    s = load("stability.json")
    strata = s["c_cd5_2d_strata"]
    fig = plt.figure(figsize=(W183, 5.4))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.25], hspace=0.42, wspace=0.30,
                          left=0.09, right=0.895, top=0.94, bottom=0.09)
    ax = fig.add_subplot(gs[0, :])
    axa_heat = [fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])]

    for win, color in (("CD3", C["sky"]), ("CD5", C["blue"]), ("CD10", C["purple"])):
        d = w["cd_window_variants"][win]
        xs, gaps = [], []
        for y in sorted(set(d["EC"]) & set(d["NON_EC"]), key=int):
            xs.append(int(y))
            gaps.append(d["EC"][y]["mean"] - d["NON_EC"][y]["mean"])
        ax.plot(xs, gaps, lw=1.2, color=color, label=win)
    ax.axhline(0, color="grey", lw=0.6, ls="--")
    ax.set_xlabel("Publication cohort year")
    ax.set_ylabel("CD gap (field \u2212 comparison)")
    ax.set_xticks(range(2002, 2021, 3))
    ax.legend(fontsize=6.5, frameon=False, ncol=3)
    ptitle(ax, "a", "Citation-window variants")

    rps = ["5-10", "11-20", "21-40", ">40"]
    rqs = ["5-10", "11-20", "21-40"]
    panels = [("EC", "field"), ("NON_EC", "comparison")]
    allvals = [v["mean"] for v in strata.values() if v["mean"] is not None]
    norm = TwoSlopeNorm(vcenter=0, vmin=min(allvals), vmax=max(allvals))

    def _lum(v):
        rgba = plt.get_cmap("RdBu")(norm(v))
        ch = [rgba[0], rgba[1], rgba[2]]

        def rel(c):
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        L = 0.2126 * rel(ch[0]) + 0.7152 * rel(ch[1]) + 0.0722 * rel(ch[2])
        return 0.0 if 1.05 / (L + 0.05) >= (L + 0.05) / 0.05 else 1.0

    xv = np.arange(len(rqs) + 1) - 0.5
    yv = np.arange(len(rps) + 1) - 0.5
    meshes = []
    for k, ((grp, gname), a) in enumerate(zip(panels, axa_heat)):
        mat = np.full((len(rps), len(rqs)), np.nan)
        nn = [[None] * len(rqs) for _ in rps]
        for i, rp in enumerate(rps):
            for j, rq in enumerate(rqs):
                v = strata.get(f"2018-20|{grp}|Rp{rp}|Rq{rq}")
                if v:
                    mat[i, j] = v["mean"]
                    nn[i][j] = v["n"]
        m = a.pcolormesh(xv, yv, np.ma.masked_invalid(mat), cmap="RdBu",
                         norm=norm, edgecolors="white", linewidth=0.5)
        meshes.append(m)
        for i in range(len(rps)):
            for j in range(len(rqs)):
                if nn[i][j] is None:
                    a.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1,
                                              facecolor="#E4E4E4",
                                              edgecolor="#BFBFBF",
                                              lw=0.4, zorder=2))
                    a.text(j, i, "n<30", ha="center", va="center",
                           fontsize=6.5, color="#5A5A5A", zorder=3)
        for i in range(len(rps)):
            for j in range(len(rqs)):
                if nn[i][j] is not None:
                    tc = "black" if _lum(mat[i, j]) else "white"
                    val = f"{mat[i, j]:.2f}".replace("-", "\u2212")
                    a.text(j, i, val + chr(10) + f"(n={nn[i][j]})",
                           ha="center", va="center", fontsize=6.5, color=tc,
                           zorder=3)
        a.set_xticks(range(len(rqs)))
        a.set_xticklabels(rqs, fontsize=6.5)
        a.set_yticks(range(len(rps)))
        a.set_yticklabels(rps if k == 0 else [""] * len(rps), fontsize=6.5)
        a.set_xlabel("Citing-side median refs", fontsize=6.5)
        if k == 0:
            a.set_ylabel("Cited-side refs (Rp)", fontsize=6.5)
        ptitle(a, "b" if k == 0 else "c", f"{gname} (2018\u201320)")
    fig.canvas.draw()
    _bb = axa_heat[0].get_position()
    _h = (_bb.y1 - _bb.y0) * 0.86
    _y0 = _bb.y0 + (_bb.y1 - _bb.y0 - _h) / 2
    cax = fig.add_axes([0.915, _y0, 0.012, _h])
    cb = fig.colorbar(meshes[0], cax=cax)
    cb.set_label("CD5 mean", fontsize=6.5)
    cb.ax.tick_params(labelsize=6.5)
    savefig(fig, "ed3",
            panel_ids={ax: "a", axa_heat[0]: "b", axa_heat[1]: "c"},
            exclude=[cax],
            row_groups=[{"id": "row-2", "panels": ["b", "c"]}],
            exemptions=[{"panels": ["a"], "checks": ["all"],
                         "reason": "window-variant panel spans both columns"}])


def ed4():
    """ED4 团队规模分桶 CD5（两 era × 桶 × 组）。"""
    w = load("w4a.json")
    buckets = w["team_size"]["buckets"]
    bkeys = ["1-2", "3-4", "5-6", "7+"]
    series = [("2005-07", "EC", C["sky"], "2005\u201307 EC"),
              ("2005-07", "NON_EC", "#F8BD6E", "2005\u201307 non-EC"),
              ("2018-20", "EC", C["blue"], "2018\u201320 EC"),
              ("2018-20", "NON_EC", C["orange"], "2018\u201320 non-EC")]
    fig, ax = plt.subplots(figsize=(89 / 25.4, 2.8))
    x = list(range(len(bkeys)))
    nb = len(series)
    width = 0.8 / nb
    for i, (era, grp, color, label) in enumerate(series):
        vals = [buckets.get(f"{era}|{grp}|{b}", {}).get("mean") for b in bkeys]
        pos = [xi + (i - (nb - 1) / 2) * width for xi in x]
        ax.bar(pos, [v if v is not None else 0 for v in vals], width=width * 0.92,
               color=color, label=label)
        for xi, v in zip(pos, vals):
            if v is None:  # 早期无该规模论文入 CD5 计票：与 ed3 同约定明示
                ax.text(xi, 0.02, "n<30", fontsize=6, color="#5A5A5A",
                        ha="center", va="bottom", rotation=90)
    ax.axhline(0, color=C["black"], lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(bkeys, fontsize=6.5)
    ax.set_xlabel("Team size (authors per paper)")
    ax.set_ylabel("CD5 mean")
    ax.legend(fontsize=6, frameon=False, ncol=2)
    fig.tight_layout()
    savefig(fig, "ed4")


def ed5():
    """ED5 腿 1 口径稳健性：三归一比 + 固定 8 刊出口率全序列。"""
    trade = load("trade.json")
    checks = load("checks.json")
    fig, (axa, axb) = plt.subplots(1, 2, figsize=(W183, 2.9))
    flow = [r for r in trade["flow"] if not r["a_tier_only"]]
    fy = [r["year"] for r in flow]
    axa.plot(fy, [r["ratio_raw_edges"] for r in flow], lw=1.2, color=C["blue"],
             label="raw edge ratio")
    axa.plot(fy, [r["ratio_citing_side_pools"] for r in flow], lw=1.2,
             color=C["green"], label="per citing-side pool")
    axa.plot(fy, [r["ratio_cited_side_pools"] for r in flow], lw=1.2,
             color=C["purple"], ls="--", label="per cited-side pool")
    axa.axhline(1.0, color="grey", lw=0.6, ls=":")
    axa.set_ylim(0, 4.2)
    axa.set_ylabel("EC\u2192non-EC / non-EC\u2192EC ratio")
    axa.set_xlabel("Year")
    axa.legend(fontsize=6, loc="upper right")
    note(axa, 2000.6, 4.1, "three normalisations,\none conclusion", fs=6, va="top")
    ptitle(axa, "a", "Knowledge balance, three normalisations")

    rows = checks["c2_fixed_venue_export"]
    axb.plot([r["year"] for r in rows], [r["rate"] for r in rows], lw=1.2,
             color=C["blue"])
    peak = max(rows, key=lambda r: r["rate"])
    axb.annotate("2021 peak 0.830", xy=(peak["year"], peak["rate"]),
                 xytext=(2010.5, 0.90), fontsize=6,
                 arrowprops=dict(arrowstyle="-", color=C["grey"], lw=0.6))
    axb.set_xlabel("Year")
    axb.set_xticks([2005, 2010, 2015, 2020, 2025])
    axb.set_ylabel("Fixed-8-venue export rate")
    axb.set_ylim(0, 1.0)
    axb.text(0.97, 0.06, "Fixed 8 venues: ASC, C&IE, C&OR, EAAI,\nEJOR, ESWA, "
             "IEEE TFS, InfSci", transform=axb.transAxes, ha="right",
             va="bottom", fontsize=6, color=C["grey"],
             bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=C["grey"],
                       lw=0.6))
    ptitle(axb, "b", "Export rate, full series")
    fig.tight_layout()
    savefig(fig, "ed1")


def ed6():
    """ED6 四维相关矩阵（水平 r 与一阶差分 r；不合成单一指数的依据）。"""
    v = load("vitality.json")
    keys = ["D1_disruption", "D2_outflow", "D3_youth", "D4_external"]
    labels = ["D1 disruption", "D2 outflow", "D3 youth", "D4 external"]

    def mat(src, field):
        m = [[1.0] * 4 for _ in range(4)]
        for i, a in enumerate(keys):
            for j, b in enumerate(keys):
                if i != j:
                    m[i][j] = src[f"{a}~{b}"][field]
        return m

    m1 = mat(v["corr"], "pearson")
    m2 = mat(v["corr_first_difference"], "pearson")
    fig, axes = plt.subplots(1, 2, figsize=(W183, 3.2))
    for ax, m, t, letter in ((axes[0], m1, "Level correlation (Pearson r)", "a"),
                             (axes[1], m2, "First-difference correlation", "b")):
        mesh = ax.pcolormesh(m, cmap="RdBu_r", vmin=-1, vmax=1,
                             edgecolors="white", linewidth=0.5)
        for i in range(4):
            for j in range(4):
                txt_color = "white" if abs(m[i][j]) >= 0.6 else "black"
                ax.text(j + 0.5, i + 0.5, f"{m[i][j]:.2f}", ha="center",
                        va="center", fontsize=6.2, color=txt_color)
        ax.set_xticks([i + 0.5 for i in range(4)])
        ax.set_xticklabels(labels, fontsize=6, rotation=30, ha="right")
        ax.set_yticks([i + 0.5 for i in range(4)])
        ax.set_yticklabels(labels, fontsize=6)
        ptitle(ax, letter, t)
    fig.subplots_adjust(left=0.15, right=0.84, top=0.86, bottom=0.28, wspace=0.55)
    cax = fig.add_axes([0.875, 0.24, 0.015, 0.56])
    cb = fig.colorbar(mesh, cax=cax)
    cb.set_label("Pearson r", fontsize=6.5)
    cb.ax.tick_params(labelsize=6)
    savefig(fig, "ed10")


def ed7():
    """ED7 自引率与互引率（姓名字符串口径，上界估计）。"""
    a = load("authors.json")
    fig, axes = plt.subplots(1, 2, figsize=(W183, 2.4))
    rows = a["self_citation"]
    axes[0].plot([r["year"] for r in rows], [r["rate"] * 100 for r in rows],
                 lw=1.2, color=C["blue"])
    axes[0].set_xlabel("Citing year")
    axes[0].set_ylabel("Self-citation share of\nin-corpus citations (%)")
    ptitle(axes[0], "a", "Self-citation rate")
    rows = a["reciprocity"]
    axes[1].plot([r["year"] for r in rows], [r["rate"] * 100 for r in rows],
                 lw=1.2, color=C["orange"])
    axes[1].set_xlabel("Citing year")
    axes[1].set_ylabel("Reciprocal edge share (%)")
    ptitle(axes[1], "b", "Reciprocity rate")
    fig.tight_layout()
    savefig(fig, "ed7")


def ed8():
    """ED8 主题份额热图（全部模式 × 年，EC 口径，三组分隔）。"""
    t = load("terms.json")
    groups = [
        ("EC classic methods", ["genetic algorithm", "particle swarm",
                                "differential evolution", "multi-objective",
                                "simulated annealing", "metaheuristic(s)",
                                "estimation of distribution", "neuroevolution",
                                "hyperheuristic", "no free lunch", "surrogate",
                                "novelty/quality-diversity"]),
        ("Theory terms", ["computational complexity", "convergence analysis",
                          "artificial intelligence", "constraint handling"]),
        ("External topics", ["deep learning", "reinforcement learning",
                             "transformer", "LLM/GPT", "prompt",
                             "explainable AI"]),
    ]
    modes = [m for _, ms in groups for m in ms]
    years = sorted(int(y) for y in t["denom"])
    mat = [[t["share"][m][str(y)]["ec"] * 100 for y in years] for m in modes]
    fig, ax = plt.subplots(figsize=(W183, 6.2))
    mesh = ax.pcolormesh(mat, cmap="viridis")
    ax.set_xticks([i + 0.5 for i, y in enumerate(years) if y % 2 == 0])
    ax.set_xticklabels([str(y) for y in years if y % 2 == 0], fontsize=6)
    ax.set_yticks([i + 0.5 for i in range(len(modes))])
    ax.set_yticklabels(modes, fontsize=6)
    ax.invert_yaxis()
    cuts = [len(groups[0][1]), len(groups[0][1]) + len(groups[1][1])]
    for c in cuts:
        ax.axhline(c, color="white", lw=2.0)
    for y0, y1, (gname, _) in ((0, cuts[0], groups[0]),
                               (cuts[0], cuts[1], groups[1]),
                               (cuts[1], len(modes), groups[2])):
        ax.text(len(years) + 0.3, (y0 + y1) / 2, gname, fontsize=6,
                rotation=270, rotation_mode="anchor", va="center", ha="left",
                color=C["grey"])
    ax.set_xlabel("Year")
    cb = fig.colorbar(mesh, ax=ax, shrink=0.7, pad=0.10)
    cb.set_label("Share of EC papers (%)", fontsize=6.5)
    cb.ax.tick_params(labelsize=6)
    fig.tight_layout()
    savefig(fig, "ed6")


def ed9():
    """ED9 参考文献解析率年度序列（仪器量程）。"""
    s = load("stability.json")
    fig, ax = plt.subplots(figsize=(89 / 25.4, 2.6))
    for grp, color, label in (("EC", C["blue"], "Field"),
                              ("NON_EC", C["orange"], "Comparison")):
        rows = s["a_resolution_rate"][grp]
        ax.plot([r["year"] for r in rows], [r["mean_rate"] * 100 for r in rows],
                lw=1.2, color=color, label=label)
    ax.set_xlabel("Publication year")
    ax.set_ylabel("Reference-list\nresolution rate (%)")
    ax.legend(fontsize=6, frameon=False)
    fig.tight_layout()
    savefig(fig, "ed9")


def ed10():
    """ED10 颠覆指数附加稳健性：桥接窗与固定施引池下的 gap 序列。"""
    cd = load("r3b_cd.json", R3B)
    fig, ax = plt.subplots(figsize=(89 / 25.4, 2.9))
    for key, color, ls, label in (("cd5", C["blue"], "-", "CD5 (to 2020)"),
                                  ("cd3", C["sky"], "--", "CD3 bridge"),
                                  ("cd2", C["purple"], ":", "CD2 bridge"),
                                  ("cd5_NONciter", C["green"], "-.",
                                   "CD5, non-EC citers only")):
        d = cd[key]
        ys = sorted(int(y) for y in d)
        ax.plot(ys, [d[str(y)]["gap"] for y in ys], lw=1.2, color=color, ls=ls,
                label=label)
    ax.axhline(0, color="grey", lw=0.6, ls="--")
    ax.set_ylim(-1.0, 0.35)
    note(ax, 2022.5, -0.72, "cd2 2023: \u22120.616", fs=6, ha="right", va="top")
    ax.set_xlabel("Publication cohort year")
    ax.set_ylabel("CD gap (EC \u2212 non-EC)")
    ax.legend(fontsize=6, loc="upper right")
    note(ax, 2004.5, -0.35, "fixed citing pool: 2009\u201323\nall negative; "
         "within-cell /\nunstratified ratio 15\u201368%", fs=6, va="top")
    fig.tight_layout()
    savefig(fig, "ed5")


# 2026-10-06 引用序重排（用户裁定）：内容块旧→新 ed5→ed1, ed10→ed5, ed8→ed6, ed1→ed8, ed6→ed10；
# 函数名为历史名，savefig 与注册表键为新编号（与 FIG_SOURCES.md / supplementary.tex 同步）。
FIGS = {"fig1": fig1, "fig2": fig2, "fig3": fig3, "fig4": fig4, "fig5": fig5,
        "ed1": ed5, "ed2": ed2, "ed3": ed3, "ed4": ed4, "ed5": ed10,
        "ed6": ed8, "ed7": ed7, "ed8": ed1, "ed9": ed9, "ed10": ed6}

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    todo = FIGS if which == "all" else {which: FIGS[which]}
    for name, fn in todo.items():
        fn()
