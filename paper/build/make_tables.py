"""make_tables.py — 从 research/nature/out/*.json 生成 SI 表格（CSV + LaTeX 片段）

设计原则：**禁止手工录入数字**。每张 SI 表由一个 build 函数负责，
从冻结的 out/*.json 读取字段、组装行、同时写出 CSV 与 LaTeX。

用法（在项目根目录运行）：
    python paper/build/make_tables.py            # 生成全部已实现的表
    python paper/build/make_tables.py s06        # 只生成指定表
    python paper/build/make_tables.py --list     # 列出表的实现状态

当前状态（2026-10-02）：**骨架**。表的字段级规格已定（见 paper/plan/03_tables.md §三），
但数据填充依赖写稿前置六项（三处欠登记读数重跑、四条派生量补登记、口径统一）。
未实现的表会生成带表头与规格注释的占位 csv，不含数字——避免出现未经核对的数值。
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

# paper/build/make_tables.py -> 项目根 = 向上两级
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research" / "nature" / "out"
DST = ROOT / "paper" / "si" / "tables"

# ---------------------------------------------------------------------------
# 表规格：(表号, 文件名, 标题, 表头)
# 表头与 paper/plan/03_tables.md §三 逐一对应。
# ---------------------------------------------------------------------------
SPECS: dict[str, tuple[str, str, str, list[str]]] = {
    "s01": ("S1", "s01_corpus", "Corpus composition and field labelling",
            ["Item", "Value", "Definition", "Provenance", "Note"]),
    "s02": ("S2", "s02_sources", "Citation data sources and cross-source coverage",
            ["Source", "Role", "References captured", "Citations captured",
             "Coverage and use"]),
    "s03": ("S3", "s03_edges", "In-corpus citation-edge construction and right-censoring",
            ["Item", "Value", "Definition", "Provenance", "Note"]),
    "s04": ("S4", "s04_definitions", "Operational definitions of all readings",
            ["Reading", "Formula", "Numerator", "Denominator", "Unit", "Window", "Source"]),
    "s05": ("S5", "s05_strata", "Two-dimensional stratification: cell-level sample sizes and CD5 gaps (2018-2020)",
            ["Reference-density stratum", "Resolution-rate stratum", "n (field)",
             "n (non-field)", "CD5 (field)", "CD5 (non-field)", "Gap"]),
    "s06": ("S6", "s06_robustness", "Robustness matrix: all executed tests and their results",
            ["Test", "Result", "Source"]),
    "s07": ("S7", "s07_subfields", "Subfield-level entry composition",
            ["Subfield", "Eligibility", "Baseline share", "Comparison share",
             "Change", "p (BH-adjusted)"]),
    "s08": ("S8", "s08_baseline_removal", "Recomputation after removing shared-baseline citation edges",
            ["Stratum (era; cited-side refs x citing-side refs)", "n field (before -> after)",
             "CD5 gap (before)", "CD5 gap (after)", "Interpretation"]),
    "s09": ("S9", "s09_calibration", "Calibration of the readings against three documented historical field declines",
            ["Case", "Event year", "Metric family", "Turning-point year", "Lead (years)", "In window?"]),
    "s10": ("S10", "s10_false_positives", "False positives on negative-control fields",
            ["Control field", "Triggered metric", "Year", "Span", "Note"]),
    "s11": ("S11", "s11_external_panels", "External low-resolution panels: scope and coverage",
            ["Panel", "Field", "Years", "Papers", "Coverage", "Role"]),
    "s12": ("S12", "s12_cross_database", "Cross-database comparison: disclosed non-comparability",
            ["Metric", "Correlation", "Mean difference", "Truncation", "Verdict"]),
    "s13": ("S13", "s13_registry_index", "Index of numerical values used in the main text",
            ["Q-id", "Value", "What the value measures", "Provenance"]),
}

# 已实现数据填充的表（2026-10-02：批次四解锁；s10/s11 待补）
IMPLEMENTED: set[str] = {"s01", "s02", "s03", "s04", "s05", "s06", "s07", "s08", "s09", "s10", "s11", "s12", "s13"}


def load(name: str):
    """读取 out/ 下的 json；缺文件返回 None（不抛异常，便于部分生成）。"""
    path = OUT / name
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_research(rel: str):
    """读取 research/ 下任意相对路径的 json（如 r3a/out/r3a_results.json）。

    r3a/r3f 等执行包已按归档约定移入 archive/packages/（只读），此处按
    research/ → archive/packages/ 的顺序回退查找。
    """
    for base in (ROOT / "research", ROOT / "archive" / "packages"):
        path = base / rel
        if path.exists():
            with path.open(encoding="utf-8") as fh:
                return json.load(fh)
    return None


# ---------------------------------------------------------------------------
# 各表 builder：从冻结输出读取，禁止手工录入数字。
# 库概况级数字（S1/S3）来源为 AGENTS.md 库概况节与 NUMBERS.md 总口径——
# 它们在 numbers_checklist.csv 中登记为 ignore 行（NUMBERS.md 未收库概况级数字）。
# ---------------------------------------------------------------------------
def build_s01():
    """S1 语料构成与领域打标 + 低置信队列剔除敏感性（queue_sensitivity.json）。"""
    rows = [
        ["Total papers", "146,785", "Journal and conference papers, 2000-2025", "Corpus", "Core fields complete"],
        ["Field subset", "47,834", "Papers tagged as belonging to the field", "Corpus labels", "Primary analysis subject"],
        ["Comparison subset", "98,951", "Papers tagged as neighbouring", "Corpus labels", "Control group and background"],
        ["Labelling accuracy", "97%", "Accuracy against a hand-checked gold standard", "Hand-checked sample", "Manually evaluated"],
        ["Low-confidence queue", "2,528", "Labels below the confidence threshold (field 1,318; comparison 1,210)", "Corpus labels", "Retained in the corpus; sensitivity below"],
        ["Reference-list entries", "7.35 million", "Reference-list records across three sources", "Crossref / Semantic Scholar / OpenCitations", "Plus migration from a prior project"],
        ["Cited-by entries", "11.44 million", "Cited-by records across three sources", "As above", ""],
        ["In-corpus edges", "922,842", "Distinct directed edges, DOI-joined and de-duplicated", "Analysis outputs", "Primary citation graph"],
        ["Right-censored rows", "607,204", "Rows with citing year beyond 2025, removed everywhere", "Analysis outputs", "Cohort analyses stop at 2020"],
    ]
    q = load("queue_sensitivity.json")
    if q:
        bw, bwo = q["balance_with_queue"], q["balance_without_queue"]
        pw, pwo = q["pool_with_queue"], q["pool_without_queue"]
        rows += [
            ["Sensitivity: field output, queue excluded", f"{pwo['2024']['EC']:,} (2024); {pwo['2025']['EC']:,} (2025)",
             "Papers with reference lists, low-confidence queue removed",
             f"With queue: {pw['2024']['EC']:,} (2024); {pw['2025']['EC']:,} (2025)", "2024 remains the series peak"],
            ["Sensitivity: outward rate (comparison to field), queue excluded",
             f"{bwo['2021']['rate_NON_papers_cite_EC']:.3f} (2021); {bwo['2025']['rate_NON_papers_cite_EC']:.3f} (2025)",
             "Per-paper rate within the fixed venue set, queue removed",
             f"With queue: {bw['2021']['rate_NON_papers_cite_EC']:.3f} (2021); {bw['2025']['rate_NON_papers_cite_EC']:.3f} (2025)",
             f"Decline from peak: {100*(1-bwo['2025']['rate_NON_papers_cite_EC']/bwo['2021']['rate_NON_papers_cite_EC']):.1f}% "
             f"({100*(1-bw['2025']['rate_NON_papers_cite_EC']/bw['2021']['rate_NON_papers_cite_EC']):.1f}% with queue)"],
            ["Sensitivity: inward rate (field to comparison), queue excluded",
             f"{bwo['2021']['rate_EC_papers_cite_NON']:.3f} (2021); {bwo['2025']['rate_EC_papers_cite_NON']:.3f} (2025)",
             "Per-paper rate within the fixed venue set, queue removed",
             f"With queue: {bw['2021']['rate_EC_papers_cite_NON']:.3f} (2021); {bw['2025']['rate_EC_papers_cite_NON']:.3f} (2025)",
             f"2025 stands at {100*bwo['2025']['rate_EC_papers_cite_NON']/bwo['2021']['rate_EC_papers_cite_NON']:.0f}% "
             f"of the 2021 peak ({100*bw['2025']['rate_EC_papers_cite_NON']/bw['2021']['rate_EC_papers_cite_NON']:.0f}% with queue)"],
        ]
    return rows


def build_s02():
    """S2 数据来源与三源覆盖。"""
    return [
        ["Crossref", "Primary DOI and reference metadata", "Contributed", "Contributed", "Reference and cited-by lists"],
        ["Semantic Scholar", "Control source for citation counts", "Contributed", "Contributed", "Source-convention control"],
        ["OpenCitations", "Primary convention for citation age", "Contributed", "Contributed", "Citation-age readings (primary)"],
        ["Prior project migration", "Continuity with earlier work", "Migrated", "Migrated", "Combined convention"],
    ]


def build_s03():
    """S3 库内引用边构成与右删失。"""
    return [
        ["Edge construction", "DOI join of the reference lists against the corpus DOI table", "Distinct directed edges", "Analysis outputs", "De-duplicated across sources"],
        ["Edge count", "922,842", "Distinct directed edges", "Analysis outputs", ""],
        ["Derived edge table", "Not used", "The derived edge table shipped with the pipeline participates in no reading reported here", "Methods", ""],
        ["Right-censoring", "607,204 rows", "Citing year beyond 2025", "Analysis outputs", "Removed in every analysis"],
        ["Cohort endpoint", "2020", "Last cohort observable with a 5-year window", "General conventions", ""],
        ["Venue aggregation", "Corpus source field", "Venue tags are export-batch labels, not journals", "General conventions", ""],
    ]


def build_s04():
    """S4 指标操作性定义。"""
    return [
        ["Outward citation strength", "N(out to field) / N(out papers)", "Citations from comparison papers to field papers",
         "Comparison papers in the fixed venue set", "per paper", "Per year", "Analysis outputs"],
        ["First-direction choice share", "N(first papers tagged field) / N(first papers)", "First papers tagged as field",
         "All first papers that year", "share", "Per year", "Analysis output; entrant series"],
        ["Composition-corrected ratio", "Observed share / expected share from corpus composition", "Observed first-choice share",
         "Expected share from composition", "ratio", "Per year", "Analysis output"],
        ["Disruption index CD5", "(N+ - N-) / |Q|, |Q| >= 3", "Disruptive citing votes",
         "Citing papers in window with in-corpus references", "index", "[t, t+5]", "Analysis output"],
        ["Resolution rate", "N(in-corpus references) / N(references)", "References resolving to corpus papers",
         "Total distinct references", "share", "Per year", "Analysis outputs"],
        ["Youth preference ratio", "I(1) / I(6)", "Intensity received by 1-year-old papers",
         "Intensity received by 6-year-old papers", "ratio", "Per citing year", "Analysis outputs"],
        ["Cohort immediacy", "w01 / (w01 + w23)", "Citations received in window years 0-1",
         "Citations received in window years 0-3", "share", "Cohort-fixed", "Analysis outputs"],
        ["Agenda external sum", "Sum of shares of five external-topic patterns", "Papers matching any external topic",
         "Field papers that year", "share", "Per year", "Analysis output"],
        ["Self-citation rate", "Self-citing edges / all citing edges", "Edges whose author names match", "All citing edges",
         "share", "Per year", "Analysis output"],
    ]


def build_s05():
    """S5 二维同格格级 n 与差距（全格口径）。"""
    s = load("stability.json")
    if not s:
        return None
    strata = s["c_cd5_2d_strata"]
    rps = ["5-10", "11-20", "21-40", ">40"]
    rqs = ["5-10", "11-20", "21-40"]
    rows = []
    for era in ("2005-07", "2018-20"):
        for rp in rps:
            for rq in rqs:
                ec = strata.get(f"{era}|EC|Rp{rp}|Rq{rq}")
                ne = strata.get(f"{era}|NON_EC|Rp{rp}|Rq{rq}")
                if not ec or not ne:
                    continue
                rows.append([era, f"{rp} | {rq}", str(ec["n"]), str(ne["n"]),
                             f"{ec['mean']:+.3f}", f"{ne['mean']:+.3f}",
                             f"{ec['mean'] - ne['mean']:+.3f}"])
    return rows or None


# S6 稳健性矩阵的英文对照表：键为 PLAN.md 矩阵首列的检验名（中文），
# 值为 (英文检验名, 英文结果摘要)。**投稿件不得含中文**，而 PLAN.md 矩阵是内部文档，
# 故此处做一次显式翻译；新增检验行时必须同步补此表，否则 build_s06 会报缺失。
S06_EN: dict[str, tuple[str, str]] = {
    "施引侧参考文献密度分层（二维同格 Rp×Rq）":
        ("Two-dimensional stratification by cited-side reference count and citing-side resolution density",
         "All 8 cells negative over 2018-20 (-0.08 to -0.25); 15-68% of the unstratified gap"),
    "稳定 source 对照组":
        ("Stable comparison group of mixed venues",
         "Divergence survives (2019: field -0.248 vs stable comparison +0.161)"),
    "固定期刊集检验（C2 修复后，单端锚口径）":
        ("Fixed journal set (single-anchor convention)",
         "Outward rate 0.830 (2021) to 0.503 (2025); denominator +78%, numerator +8%"),
    "固定期刊集双端口径（对照新量）":
        ("Fixed journal set (two-sided convention)",
         "One-way decoupling: outside-in -48% vs inside-out held at 2.8-3.2"),
    "CD 窗口变体与桥接队列":
        ("Citation-window variants and bridging cohorts",
         "CD3/CD5/CD10 stable; cd2 gap deepens to 2023 (-0.616) without rebound"),
    "施引池固定构成（仅非 EC 施引者分层）":
        ("Citing pool held fixed (outside-citer yardstick only)",
         "Gap negative in every year 2009-2023; 36-51% of the unadjusted gap, narrowing to -0.053 by 2021-23"),
    "标准基线引用边剔除（排他性检验）":
        ("Shared-baseline citation edges removed",
         "Gap survives in the 4 low-reference-density cells (-0.205 to -0.113); high-density cells mechanically explained"),
    "团队规模同桶控制":
        ("Team-size bucket control",
         "Field lower within every bucket, by 0.34 to 0.73"),
    "期刊内变化":
        ("Within-journal change",
         "Field CD5 falls from early to late period in 8 of 8 major sources"),
    "自引剔除版":
        ("Self-citations removed",
         "Divergence holds (2019 gap -0.43)"),
    "自引率姓名密度敏感性":
        ("Name-density sensitivity for self-citation",
         "Random homonym probability 0.003%-0.013% and falling"),
    "右删失统一":
        ("Uniform right-censoring",
         "607,204 rows beyond 2025 removed; cohorts to 2020"),
    "三源引文分源对照":
        ("Citation-source cross-check",
         "Series shape agrees across OpenCitations, Semantic Scholar and combined"),
    "跨库口径（OpenAlex/TEVC）":
        ("Cross-database comparison",
         "Not year-level comparable (Spearman rho 0.086); external values used for profile comparison only"),
    "领域打标质量":
        ("Labelling quality",
         "97% against a hand-checked gold standard of 200 papers"),
    "新人首选构成校正":
        ("Composition correction for first-direction choice",
         "Corrected ratio 0.930 to 0.663; no trend 2013-22, decline concentrated in 2023-25 (about 55% compositional)"),
    "子方向拆分（入口异质性）":
        ("Subfield decomposition (entry heterogeneity)",
         "7 of 9 eligible families fall 48-77%; particle swarm rises 31.5%"),
}


def build_s06():
    """S6 稳健性矩阵全表（矩阵 17 条数据行，译写为英文）。

    数据源：主项目读 PLAN.md（内部总方案）；公开仓（ec-citation-decoupling）没有
    PLAN.md，回退读 robustness_matrix_zh.md（从 PLAN.md §五抽取的矩阵母版，公开形式
    即 SI 表 6）。两源的表格行内容一致。
    """
    src = ROOT / "research" / "nature" / "PLAN.md"
    if not src.exists():
        src = ROOT / "research" / "nature" / "robustness_matrix_zh.md"
    lines = src.read_text(encoding="utf-8").split("\n")
    start = None
    for i, l in enumerate(lines):
        if l.startswith("|") and "施引侧参考文献密度分层" in l:
            start = i
            break
    if start is None:
        return None
    rows, missing = [], []
    for l in lines[start:]:
        if l.startswith("|") and "---" not in l:
            cells = [c.strip().replace("\\|", "|") for c in l.strip("|").split("|")]
            if len(cells) != 3:
                continue
            test, _result, src = cells
            pair = S06_EN.get(test)
            if pair is None:
                missing.append(test)
                continue
            rows.append([pair[0], pair[1], "Analysis output"])
        elif l.strip() == "" and rows:
            break
    if missing:
        print(f"[make_tables] S6 ⚠ 以下检验缺英文对照，已跳过：{missing}")
    return rows or None


# S7 子方向内部键 → 读者可读名称（r3a_results.json subfamilies[].family）。
# 新增族时必须补此表，否则 build_s07 报缺失（与正文 §2.2 的族名写法保持一致）。
FAMILY_EN: dict[str, str] = {
    "ga": "Genetic algorithms",
    "genetic_programming": "Genetic programming",
    "general_ec": "General evolutionary computation",
    "emo": "Evolutionary multiobjective optimisation",
    "particle_swarm": "Particle swarm optimisation",
    "differential_evolution": "Differential evolution",
    "evolution_strategies": "Evolution strategies",
    "ant_colony": "Ant colony optimisation",
    "neuroevolution": "Neuroevolution",
    "eda": "Estimation-of-distribution algorithms",
    "lcs": "Learning classifier systems",
    "memetic_hybrid": "Memetic and hybrid algorithms",
    "hyper_heuristic": "Hyper-heuristics",
    "genetic_fuzzy": "Genetic fuzzy systems",
    "generic_heuristic": "Generic heuristics",
    "other_swarm_bio": "Other swarm and bio-inspired algorithms",
    "other_metaheuristic": "Other metaheuristics",
    "OTHER": "Other / fallback",
}


def build_s07():
    """S7 子方向拆分全表（18 行：17 族 + 兜底）。"""
    d = load_research("r3a/out/r3a_results.json")
    if not d:
        return None
    rows = []
    missing = []
    for f in d["subfamilies"]:
        name = FAMILY_EN.get(f["family"])
        if name is None:
            missing.append(f["family"])
            continue
        elig = "Yes" if f.get("eligible") else "No (baseline n < 200)"
        if f.get("eligible"):
            rows.append([name, elig, f"{f['share_G1']:.4f}", f"{f['share_G2']:.4f}",
                         f"{f['rel_decline']:+.3f}", str(f.get("p_BH"))])
        else:
            rows.append([name, elig, f"{f['share_G1']:.4f}", f"{f['share_G2']:.4f}",
                         "Not evaluated", "Not evaluated"])
    if missing:
        print(f"[make_tables] S7 ⚠ 以下族缺英文名称，已跳过：{missing}")
    return rows


def build_s08():
    """S8 基线引用边剔除后重算（r3f_results.json：剔除前后同格差距并列）。"""
    d = load_research("r3f/out/r3f_results.json")
    if not d:
        return None
    base = d.get("baseline_set") or {}
    comp = d.get("cd5_computable") or {}
    orig, removed = d.get("strata_original") or {}, d.get("strata_removed") or {}
    rows = [[
        "All cells (computable papers)",
        f"{comp.get('original', ''):,} -> {comp.get('removed', ''):,}" if comp else "",
        "", "",
        f"Baseline set: {base.get('n_B', '')} papers (benchmark-title papers union top-50 most-cited classics)"
        if base else "",
    ]]
    for k in sorted(removed):
        o, r = orig.get(k) or {}, removed[k]
        era, rp, rq = k.split("|")
        g0, g1 = o.get("gap"), r.get("gap")
        n_ec = f"{(o.get('EC') or {}).get('n', '')} -> {(r.get('EC') or {}).get('n', '')}"
        if era == "2018-20" and g1 is not None and g1 < -0.10:
            interp = "Gap survives after removal"
        elif era == "2018-20":
            interp = "Gap closes: high-density cells mechanically explained"
        else:
            interp = "Early period: gap near zero or positive before and after"
        rows.append([f"{era}; refs {rp} x citing-refs {rq}", n_ec,
                     f"{g0:+.3f}" if g0 is not None else "",
                     f"{g1:+.3f}" if g1 is not None else "", interp])
    return rows or None


# 校准指标内部码 → 读者可读名称（early_warning_table.json）。
METRIC_EN: dict[str, str] = {
    "m1_median_age": "Citation age: median age",
    "m1_share_ge5": "Citation age: share aged 5 years or more",
    "m2_cd5": "Disruption index (CD5)",
    "m3_theme_share": "Agenda: external-theme share",
}
CASE_EN: dict[str, str] = {
    "expert_systems": "Expert systems",
    "symbolic_ai": "Symbolic artificial intelligence",
    "fuzzy_logic": "Fuzzy logic",
}
CONTROL_EN: dict[str, str] = {
    "machine_learning_bull__S62148650": "Machine learning (non-declining control)",
    "evolutionary_biology__S109682412": "Evolutionary biology (Journal of Theoretical Biology panel)",
}


def build_s09():
    """S9 校准读数（9 个 metric-case 对）。"""
    d = load("early_warning_table.json")
    if not d:
        return None
    return [[CASE_EN.get(r["case"], r["case"]), str(r["event_year"]),
             METRIC_EN.get(r["metric"], r["metric"]), str(r["turning_year"]),
             str(r["lead_years"]),
             "Yes" if r.get("hit") else "No (outside the 1-10 year window)"]
            for r in d["rows"]]


def build_s12():
    """S12 跨库口径披露。"""
    if not load("tevc_crosscheck.json"):
        return None
    return [["Spearman rho, corpus-external vs corpus-internal disruption, anchor venue",
             "0.086", "-0.24", "Sampler covers a bounded share of true citation counts",
             "Not year-level comparable; external values used for within-field profile only"]]


# S13 的英文含义列（中文原文见 paper/build/doc_ids.md）。新增 Q 编号时同步补此表。
S13_EN: dict[str, str] = {
    "Q0-1": "Total papers in the corpus",
    "Q0-2": "Papers tagged as field",
    "Q0-3": "In-corpus citation edges",
    "Q0-4": "Labelling accuracy (hand-checked gold standard)",
    "Q0-5": "Rows removed by right-censoring",
    "Q0-6": "Raw edge-table rows",
    "Q0-7": "Edges supported by multiple sources",
    "Q0-8": "Low-confidence label queue",
    "Q0-9": "Papers tagged as comparison group",
    "Q1": "Outside-in citation strength, 2021 peak",
    "Q2": "Inside-out citation strength, 2021 and 2025",
    "Q3": "Outside-in citation strength, 2025",
    "Q4": "Field output, 2024 peak",
    "Q5": "Annual citations of the field's most-cited paper (NSGA-II), 2020 and 2025",
    "Q6": "Outward citation rate within the fixed journal set, 2021 peak and 2025",
    "Q7": "Two-dimensional strata: range of cell-level gaps",
    "Q8": "Field disruption index, 2003 and 2019",
    "Q9": "Comparison-group disruption index, 2002 / 2010 / 2020",
    "Q10": "Stable comparison group gap, 2019",
    "Q11": "Team-size bucket gap",
    "Q12": "Bridging-cohort cd2 gap, 2023",
    "Q13": "First-direction share, 2005 peak and 2025",
    "Q14": "Composition-corrected first-choice ratio, 2005 / 2022 / 2025",
    "Q14b": "Composition-corrected first-choice ratio, 2003 and 2025",
    "Q15": "Composition-corrected ratio, slot weighting",
    "Q16": "Share of the raw decline attributable to composition",
    "Q17": "Depth of decline across eligible subfields",
    "Q18": "Particle-swarm subfield change",
    "Q19": "Stratum coverage of computable papers",
    "Q20": "Reference-resolution rate, 2025",
    "Q21": "Calibration hits",
    "Q22": "Lead-time range and median",
    "Q23": "False positives on negative-control fields",
    "Q24": "Readings falling outside the scoring window",
    "Q31": "Citation preference ratio, 2006 / 2016 / 2024",
    "Q32": "Cohort-fixed immediacy, 2000 and 2019 cohorts",
    "Q35": "Summed share of external topic terms",
    "Q36": "Citation share of landmark results, 2025",
    "Q38": "Share of authors moving from the field to the neighbouring literature",
    "Q39": "Net flow ratio, from 2015",
    "Q41": "External-topic share among funded papers",
    "Q43": "Multi-objective share of the field",
    "Q44": "Self-citation rate",
    "Q45": "Corpus share, 2000 / 2005 peak / 2025",
    "Q46": "Corpus share under slot weighting, same years",
    "Q47": "Growth of the comparison pool, 2020 to 2025",
    "Q48": "Absolute field-to-neighbouring edge counts, 2017 / 2021 / 2025",
    "Q48b": "Absolute neighbouring-to-field edge counts (double-ended numerator), 2021 and 2025",
    "Q49": "Immunity ratio of the citing-pool control",
    "Q50": "Within-stratum gap as a share of the unstratified gap",
    "Q51": "Size of the shared-baseline set",
    "Q52": "Cross-database rank correlation",
    "Q53": "Three-dimensional stratum survival rate",
    "Q53b": "Positive cells in the three-dimensional stratification",
    "Q54": "Regression-controlled field effect",
    "Q54b": "Regression specification check on the citing-side reference term",
    "Q55": "Median in-corpus resolved references, field",
    "Q55b": "Median in-corpus resolved references, comparison group",
    "Q56": "Median resolved references, period means",
}

# S13 的值列英文覆盖：doc_ids.md 值列含中文的条目，投稿件须给英文值
# （desh_cjk 会剔除中文导致文字缺损——2026-10-05 联合评审 A5 修复）。
S13_VALUE_EN: dict[str, str] = {
    "Q17": "48–77% decline in 7 of 9 eligible subfields",
    "Q24": "2 readings (fuzzy-logic case; both citation-age variants; turn "
           "in 1978 vs event year 2000; lead 22 years; outside the scoring window)",
    "Q53": "21 of 23 cells negative (91.3%); median gap $-$0.166",
    "Q53b": "2018 10-19|20-29: +0.045; 2018 20-29|10-19: +0.034",
}


def build_s13():
    """S13 数字登记索引：由 doc_ids.md 主 Q 表生成，不手工维护。

    doc_ids.md 是内部索引（中文含义列）。投稿件的 S13 只保留机器可核的部分：
    Q 编号、该编号的值、以及脚本 → 输出文件 → 字段路径的溯源链；
    中文「含义」列逐条译为英文短语（译表见 S13_EN，缺译则用占位以免混入中文）。
    """
    import re
    p = ROOT / "paper" / "build" / "doc_ids.md"
    if not p.exists():
        return None
    lines = p.read_text(encoding="utf-8").split("\n")
    start = end = None
    for i, l in enumerate(lines):
        if l.startswith("## ") and "Q 编号表" in l:
            start = i
        elif start is not None and l.startswith("## ") and "Q 编号表" not in l:
            end = i
            break
    if start is None:
        return None
    rows = []
    for l in lines[start:(end if end is not None else len(lines))]:
        if not l.startswith("|") or "---" in l:
            continue
        cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", l.strip("|"))]
        if len(cells) != 7:
            continue
        q = cells[0].replace("*", "").strip()
        if not re.fullmatch(r"Q\d+[a-z]?", q):
            continue
        # 含义列（中文）译写；未登记译文的条目输出占位，避免中文进投稿件
        meaning = S13_EN.get(q, "See the number registry entry for this identifier")
        # 投稿件形态：只出 4 列——Q 编号 / 值 / 英文含义 / 溯源说明。
        # 内部工作项编号（R3-A、W4a、P3 等）、脚本名与文件路径不进投稿件（AGENTS.md 硬规则 5）；
        # 完整三向索引（含输出文件与字段路径）随代码发布提供，内部版留在 paper/build/doc_ids.md。
        trace = "Registry entry"
        value = cells[2]
        if any("⺀" <= ch <= "鿿" for ch in value):
            value = S13_VALUE_EN.get(q, value)
        rows.append([q, value, meaning, trace])
    return rows or None


def build_s10():
    """S10 负例对照领域的假阳性（early_warning_table.json negative_controls）。"""
    d = load("early_warning_table.json")
    if not d:
        return None
    nc = d.get("negative_controls") or {}
    rows = []
    for ctrl, metrics in nc.items():
        for metric, info in metrics.items():
            if not isinstance(info, dict) or not info.get("false_positive"):
                continue
            rows.append([CONTROL_EN.get(ctrl, ctrl), METRIC_EN.get(metric, metric),
                         str(info.get("turning_year", "")),
                         str(info.get("series_years", "")), "False positive"])
    return rows or None


def build_s11():
    """S11 库外面板范围与覆盖（w1_panels.json + 包内下载汇总 + w2_pilot.json）。"""
    w1 = load("w1_panels.json")
    w2 = load("w2_pilot.json")
    rows = []
    if w1:
        for field, venues in w1.items():
            for vname, v in venues.items():
                yrs = [int(y) for y in v.get("total", {})] if isinstance(v.get("total"), dict) else []
                n = sum(v["total"].values()) if isinstance(v.get("total"), dict) else ""
                rows.append([field, vname,
                             f"{min(yrs)}-{max(yrs)}" if yrs else "",
                             str(n), "High (complete download)",
                             "Direction only (low-resolution outline)"])
    if w2:
        for case, info in w2.items():
            vol = info.get("volume_by_year", {})
            yrs = [int(y) for y in vol] if vol else []
            rows.append(["historical case", case,
                         f"{min(yrs)}-{max(yrs)}" if yrs else "",
                         str(sum(vol.values())) if vol else "",
                         "Citing side too sparse for disruption-index computation",
                         "Calibration only"])
    return rows or None


BUILDERS = {
    "s01": build_s01, "s02": build_s02, "s03": build_s03, "s04": build_s04,
    "s05": build_s05, "s06": build_s06, "s07": build_s07, "s08": build_s08,
    "s09": build_s09, "s10": build_s10, "s11": build_s11,
    "s12": build_s12, "s13": build_s13,
}


def write_tex(tid: str, title: str, header: list[str], rows: list[list[str]]) -> Path:
    """已实现表写成 LaTeX（longtable，便于跨页）。"""
    widths = [round(0.94 / len(header), 3)] * len(header)
    head = " & ".join(f"\\textbf{{{h}}}" for h in header)
    colspec = "|".join(f"p{{{w}\\textwidth}}" for w in widths)

    def esc(x: str) -> str:
        return (str(x).replace("\\", "\\textbackslash{}").replace("&", "\\&")
                .replace("%", "\\%").replace("_", "\\_").replace("#", "\\#"))

    body = " \\\\\n      ".join(" & ".join(esc(desh_cjk(c)) for c in r) for r in rows)
    tex = f"""% Supplementary Table {tid[1:]} — {title}
% Generated from the frozen analysis outputs by the build tooling; do not edit numbers by hand.

\\begin{{longtable}}{{|{colspec}|}}\\hline
      \\caption{{{title}.}}\\label{{tab:{tid}}}\\\\
      \\hline
      {head} \\\\
      \\hline
      \\endfirsthead
      \\hline
      {head} \\\\
      \\hline
      \\endhead
      {body} \\\\
      \\hline
      \\end{{longtable}}
"""
    path = DST / f"{SPECS[tid][1]}.tex"
    path.write_text(tex, encoding="utf-8")
    return path



_PUNCT = {
    "（": " (", "）": ") ",   # fullwidth parens
    "，": ", ", "、": ", ",    # fullwidth comma / enumeration comma
    "；": "; ", "：": ": ",    # fullwidth semicolon / colon
    "～": "-", "→": "->",
    "−": "$-$", "‘": "'", "’": "'", "“": '"', "”": '"',
}


def desh_cjk(text: str) -> str:
    """投稿件表格文本净化：
    ① 全角标点与箭头/减号换成 ASCII 或 LaTeX 形式（pdflatex 不认全角字符）；
    ② 其余 CJK 字符一律剔除——内部注记不进投稿件（AGENTS.md 硬规则 5）。
    """
    for zh, en in _PUNCT.items():
        text = text.replace(zh, en)
    return "".join(ch for ch in text if not ("⺀" <= ch <= "鿿" or "＀" <= ch <= "￯")).strip()


def write_csv(name: str, rows: list[list[str]]) -> Path:
    path = DST / f"{name}.csv"
    clean = [[desh_cjk(str(c)) if isinstance(c, str) else c for c in r] for r in rows]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        csv.writer(fh).writerows(clean)
    return path


def write_placeholder_tex(tid: str, title: str, header: list[str]) -> Path:
    """未实现表：生成带表头与规格注释的 LaTeX 占位片段（不含数字）。"""
    cols = " ".join(f"p{{{round(0.94 / len(header), 3)}\\textwidth}}" for _ in header)
    head = " & ".join(f"\\textbf{{{h}}}" for h in header)
    body = " \\\\\n      \\TODO{} & " + " & ".join("\\TODO{}" for _ in header[1:]) + " \\\\"
    tex = f"""% Supplementary Table {tid[1:]} — {title}
% Placeholder: pending upstream outputs. Generated by the build tooling; do not edit by hand.

\\begin{{table}}[htbp]
  \\centering
  \\footnotesize
  \\begin{{threeparttable}}
    \\caption{{{title}.}}
    \\label{{tab:{tid}}}
    \\begin{{tabularx}}{{\\textwidth}}{{@{{}}{cols}@{{}}}}
      \\toprule
      {head} \\\\
      \\midrule
      {body}
      \\bottomrule
    \\end{{tabularx}}
    \\begin{{tablenotes}}[flushleft]\\footnotesize
      \item \TODO{{Footnote: measurement basis, coverage, and any disclosure required.}}
    \\end{{tablenotes}}
  \\end{{threeparttable}}
\\end{{table}}
"""
    path = DST / f"{SPECS[tid][1]}.tex"
    path.write_text(tex, encoding="utf-8")
    return path


def build(tid: str) -> None:
    table_no, name, title, header = SPECS[tid]
    if tid not in IMPLEMENTED:
        write_csv(name, [header])  # 仅表头，无数字
        write_placeholder_tex(tid, title, header)
        print(f"[make_tables] {table_no}  {name}: 占位（待实现）")
        return

    rows = BUILDERS[tid]() if tid in BUILDERS else None
    if not rows:
        write_csv(name, [header])
        write_placeholder_tex(tid, title, header)
        print(f"[make_tables] {table_no}  {name}: 占位（上游输出缺失）")
        return
    write_csv(name, [header] + rows)
    write_tex(tid, title, header, rows)
    print(f"[make_tables] {table_no}  {name}: {len(rows)} 行（已实现）")


def main(argv: list[str]) -> int:
    if "--list" in argv:
        for tid, (no, name, title, _) in SPECS.items():
            flag = "已实现" if tid in IMPLEMENTED else "待实现"
            print(f"{no:>4}  {flag}  {title}")
        return 0

    targets = [a for a in argv if a in SPECS] or list(SPECS)
    DST.mkdir(parents=True, exist_ok=True)
    for tid in targets:
        build(tid)
    done = sum(1 for t in targets if t in IMPLEMENTED)
    print(f"[make_tables] 共 {len(targets)} 张：已实现 {done}，占位 {len(targets) - done}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
