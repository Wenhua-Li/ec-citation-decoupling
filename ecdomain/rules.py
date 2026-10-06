"""规则层：对 B/C 两档 venue 的论文做确定性预判（双向）。

判定口径（用户确认：广义元启发式，纯二分类）：
  EC    = 主方法是元启发式（EA 家族/群智能/新型自然启发/SA/禁忌搜索/VNS/GRASP/memetic
          及其混合），无论方法改进还是应用。
  非EC  = 纯精确方法（MILP/分支定界/DP）、纯 ML/DL/统计学习、纯模糊控制、
          演化生物学/演化博弈（名字撞车）、元启发式仅作 baseline 或调参工具的论文。

输出三桶：auto_ec / auto_non / todo（todo 交给 LLM 层）。
阈值宁可保守：拿不准一律 todo。rule_ver 记录在 domain_meta。
"""
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from . import LABEL_EC, LABEL_NON, TIER_B, TIER_C
from . import _db

RULE_VER = "R1"

NAME, GEN = "name", "gen"

# (regex, 标签, 强度) —— NAME=具体算法名（标题单命中即可判EC），
# GEN=泛措辞（evolutionary X / swarm X / metaheuristic，标题单命中判EC、置信略低）
PATTERNS = [
    ("genetic algorithm", "genetic_algorithm", NAME),
    ("genetic program", "genetic_programming", NAME),
    ("differential evolution", "differential_evolution", NAME),
    ("particle swarm", "particle_swarm", NAME),
    (r"\bPSO\b", "pso", NAME),
    (r"\bACO\b", "aco", NAME),
    ("ant colony", "ant_colony", NAME),
    ("ant ?lion", "ant_lion", NAME),
    ("artificial bee|bee colony|bee algorithm", "bee", NAME),
    ("artificial immune system|immune algorithm", "immune", NAME),
    ("bacterial forag", "bacterial_foraging", NAME),
    ("biogeograph", "bbo", NAME),
    ("cuckoo search|cuckoo algorithm|cuckoo optimi", "cuckoo", NAME),
    ("firefly", "firefly", NAME),
    (r"bat (algorithm|inspired)", "bat", NAME),
    ("(grey|gray) wolf", "gwo", NAME),
    ("whale optimi", "woa", NAME),
    ("moth.?flame", "mfo", NAME),
    ("salp swarm", "ssa", NAME),
    ("sine cosine", "sca", NAME),
    ("dragonfly (algorithm|optimi)", "dragonfly", NAME),
    ("harris hawk", "hho", NAME),
    ("flower pollination", "fpa", NAME),
    ("teaching.?learning.?based", "tlbo", NAME),
    ("jaya (algorithm|optimi)", "jaya", NAME),
    ("harmony search", "harmony_search", NAME),
    (r"\bmemetic\b", "memetic", NAME),
    ("estimation of distribution", "eda", NAME),
    ("co.?evolutionar|cooperative coevolution", "coevolution", NAME),
    ("neuroevolution", "neuroevolution", NAME),
    (r"\bNSGA", "nsga", NAME),
    (r"\bMOEA", "moea", NAME),
    (r"\bSPEA", "spea", NAME),
    (r"\bIBEA\b", "ibea", NAME),
    ("CMA-?ES", "cma_es", NAME),
    ("hyper-?heuristic", "hyper_heuristic", NAME),
    ("scatter search", "scatter_search", NAME),
    (r"variable neighbou?rhood search|\bVNS\b", "vns", NAME),
    (r"greedy randomized adaptive search|\bGRASP\b", "grasp", NAME),
    (r"tabu search|\btabu\b", "tabu", NAME),
    ("simulated annealing", "simulated_annealing", NAME),
    ("cross.?entropy method", "cem", NAME),
    ("invasive weed", "invasive_weed", NAME),
    ("frog leaping", "frog_leaping", NAME),
    ("imperialist competitive", "ica", NAME),
    ("cultural algorithm", "cultural_algorithm", NAME),
    ("evolutionary (algorithm|comput|optimi|search|design|learning|neural|fuzzy"
     "|multiobjective|framework|approach|method|technique|strategy|heurist)",
     "evolutionary_x", GEN),
    ("swarm intelligen|swarm optimi|swarm algorithm|swarm-based", "swarm_x", GEN),
    (r"\bmeta-?heuristic", "metaheuristic", GEN),
]

# 负向守卫：命中即放弃自动判定（送 LLM），压掉演化生物学/演化博弈等名字撞车
NEG_PATTERNS = [
    "evolutionary biolog", "phylogenetic", "evolutionary tree",
    "viral evolution", "virus evolution", "(cancer|tumor|tumour) evolution",
    "human evolution", "brain evolution", "genom(e|ic) evolution",
    "evolutionary histor", "evolutionary relationship", "evolutionary distance",
    "evolutionary dynamics", "evolutionary game", "evolutionary epidemiolog",
    "evolutionary pathway", "evolutionary trajector", "evolutionary origin",
]

# EC 家族词（宽网）：标题+摘要+关键词全部都不出现才允许 auto-非EC
FAMILY_PATTERNS = [
    "genetic algorithm", "genetic program", "differential evolution", "evolution",
    "swarm", "ant colon", "ant ?lion", "bee colon", "artificial bee", "cuckoo",
    "firefly", "bat algorithm", "bat.?inspired", "(grey|gray) wolf", "whale optimi",
    "moth.?flame", "salp", "dragonfly", r"\bmemetic\b", "heuristic", "tabu",
    "anneal", "local search", "neighbou?rhood search", "hill.?climb",
    "scatter search", "greedy randomized", r"\bgrasp\b", r"\bpso\b", r"\baco\b",
    r"\bvns\b", r"\bga\b", "nsga", "moea", "spea", "ibea", "cma-?es",
    "estimation of distribution", "immune algorithm", "artificial immune",
    "bacterial forag", "biogeograph", "invasive weed", "frog leaping",
    "imperialist competitive", "teaching.?learning", "jaya", "flower pollination",
    "harris hawk", "sine cosine", "cross.?entropy method", "cultural algorithm",
]


def _combine(patterns):
    return re.compile("|".join("(?:%s)" % p for p in patterns), re.IGNORECASE)


EC_RE = _combine([p for p, _, _ in PATTERNS])
NEG_RE = _combine(NEG_PATTERNS)
FAMILY_RE = _combine(FAMILY_PATTERNS)
_STRENGTH = {lab: s for _, lab, s in PATTERNS}

# EI 受控词（小写精确匹配）。STRONG 出现即强信号；WEAK 只阻止 auto-非EC。
CTL_STRONG = {
    "genetic algorithms", "evolutionary algorithms", "evolutionary computation",
    "particle swarm optimization (pso)", "swarm intelligence", "genetic programming",
    "simulated annealing", "ant colony optimization", "tabu search",
    "invasive weed optimization", "cultural algorithms",
}
CTL_WEAK = {
    "heuristic algorithms", "heuristic methods", "heuristic programming",
    "local search (optimization)", "multiobjective optimization",
}


def _hits(text, rex, strength_map=None):
    """返回命中的模式标签集合（去重）。"""
    if not text:
        return set()
    out = set()
    for m in rex.finditer(text):
        # 找到命中的分支：逐组探测（combined 里每个分支是一个非捕获组，
        # 无法直接定位分支名，用逐段回退：对候选标签逐个 re.search）
        out.add(_which(m.group(0)))
    return out


_WHICH_CACHE = {}


def _which(frag):
    """命中片段 -> 模式标签（片段可能横跨分支，用各模式原 regex 单测）。"""
    lab = _WHICH_CACHE.get(frag.lower())
    if lab is not None:
        return lab
    for pat, name, _ in PATTERNS:
        if re.search("(?:%s)" % pat, frag, re.IGNORECASE):
            _WHICH_CACHE[frag.lower()] = name
            return name
    return "?"


def classify(title, abstract, ctl_terms, unc_terms):
    """返回 (decision, confidence, evidence)；decision ∈ {EC, NON_EC, None}。"""
    tl = title or ""
    ab = abstract or ""
    kw = "; ".join(ctl_terms) + "; " + "; ".join(unc_terms)

    neg = bool(NEG_RE.search(tl) or NEG_RE.search(ab))
    t_name = {l for l in _hits(tl, EC_RE) if _STRENGTH.get(l) == NAME}
    t_gen = {l for l in _hits(tl, EC_RE) if _STRENGTH.get(l) == GEN}
    a_name = {l for l in _hits(ab, EC_RE) if _STRENGTH.get(l) == NAME}
    a_gen = {l for l in _hits(ab, EC_RE) if _STRENGTH.get(l) == GEN}
    kw_name = {l for l in _hits(kw, EC_RE) if _STRENGTH.get(l) == NAME}
    ctl_s = {t for t in ctl_terms if t.lower() in CTL_STRONG}
    ctl_w = {t for t in ctl_terms if t.lower() in CTL_WEAK}

    ev = []
    if t_name or t_gen:
        ev.append("T:" + ",".join(sorted(t_name | t_gen)))
    if a_name or a_gen:
        ev.append("A:" + ",".join(sorted(a_name | a_gen)))
    if kw_name:
        ev.append("KW:" + ",".join(sorted(kw_name)))
    if ctl_s:
        ev.append("CTL:" + ",".join(sorted(ctl_s)))
    evidence = " ".join(ev)[:250]

    if not neg:
        all_name = t_name | a_name | kw_name
        all_gen = t_gen | a_gen
        if t_name:
            return LABEL_EC, 0.97, evidence
        if t_gen:
            return LABEL_EC, 0.93, evidence
        if all_name and len(all_name | all_gen) >= 2:
            return LABEL_EC, 0.95, evidence
        if len(ctl_s) >= 2:
            return LABEL_EC, 0.95, evidence
        if ctl_s and (all_name | all_gen):
            return LABEL_EC, 0.94, evidence
        if ctl_s and kw_name:
            return LABEL_EC, 0.94, evidence
        if kw_name and all_gen:
            return LABEL_EC, 0.92, evidence
        if kw_name:
            return LABEL_EC, 0.90, evidence

    # auto-非EC：全文无任何 EC 家族词、无受控 EC 词
    if not (FAMILY_RE.search(tl) or FAMILY_RE.search(ab) or FAMILY_RE.search(kw)) \
            and not ctl_s and not ctl_w:
        return LABEL_NON, 0.96, "no_family_token"
    return None, None, evidence


def scope_tags(conn):
    rows = conn.execute(
        "SELECT venue_tag FROM venue_tier WHERE tier IN (?,?)", (TIER_B, TIER_C))
    return [r[0] for r in rows]


def _classify_where(conn, where_sql, params):
    """对满足 where_sql 的 papers 集合跑 classify，返回 [(acc, tag, dec, conf, ev)]。"""
    papers = conn.execute(
        f"SELECT p.accession_no, p.venue_tag, p.title, p.abstract "
        f"FROM papers p JOIN venue_tier vt ON vt.venue_tag = p.venue_tag "
        f"WHERE {where_sql}", params).fetchall()
    terms = defaultdict(lambda: {True: [], False: []})
    accs = [p["accession_no"] for p in papers]
    for j in range(0, len(accs), 800):
        ph = ",".join("?" * len(accs[j:j + 800]))
        for r in conn.execute(
                f"SELECT accession_no, kind, term FROM paper_terms "
                f"WHERE accession_no IN ({ph})", accs[j:j + 800]):
            terms[r[0]][r[1] == "controlled"].append(r[2])
    out = []
    for p in papers:
        ctl = terms[p["accession_no"]][True]
        unc = terms[p["accession_no"]][False]
        dec, conf, ev = classify(p["title"], p["abstract"], ctl, unc)
        out.append((p["accession_no"], p["venue_tag"], dec, conf, ev))
    return out


def classify_all():
    """对全部 B/C 论文分类，返回 [(accession_no, venue_tag, decision, conf, evidence)]。"""
    conn = _db.connect_ro()
    try:
        tags = scope_tags(conn)
        results = []
        for tag in tags:
            results.extend(_classify_where(conn, "p.venue_tag = ?", (tag,)))
        return results
    finally:
        conn.close()


def classify_venue_a():
    """对 A 档论文跑同一套规则（不写库）。
    用于抓"纯EC刊源里跑题"的论文：规则判 NON_EC 的送 LLM 复核。"""
    conn = _db.connect_ro()
    try:
        return _classify_where(conn, "vt.tier = 'A_pure_ec'", ())
    finally:
        conn.close()


def run_rules(report_samples=15):
    """跑规则层：auto 桶写 paper_domain（tier='rule'），todo 留给 LLM。"""
    conn = _db.connect_rw()
    try:
        _db.ensure_schema(conn)
        if conn.execute("SELECT COUNT(*) FROM venue_tier").fetchone()[0] == 0:
            raise SystemExit("venue_tier 为空：先运行 python -m ecdomain venues")
        conn.close()
    except SystemExit:
        raise
    except Exception:
        conn.close()
        raise

    results = classify_all()
    auto = [(a, d, c, e) for a, _, d, c, e in results if d is not None]
    n_todo = sum(1 for r in results if r[2] is None)
    buckets = Counter(r[2] for r in results)

    conn = _db.connect_rw()
    try:
        _db.ensure_schema(conn)
        conn.execute("DELETE FROM paper_domain WHERE tier='rule'")
        now = _db.utcnow()
        for j in range(0, len(auto), 5000):
            conn.executemany(
                "INSERT OR REPLACE INTO paper_domain"
                "(accession_no, label, tier, confidence, evidence, model, rule_ver, judged_at) "
                "VALUES(?,?, 'rule', ?, ?, NULL, ?, ?)",
                [(a, d, c, e, RULE_VER, now) for a, d, c, e in auto[j:j + 5000]])
        _db.set_meta(conn, "rules_run", json.dumps({
            "rule_ver": RULE_VER, "scope_papers": len(results),
            "auto_ec": buckets.get(LABEL_EC, 0), "auto_non": buckets.get(LABEL_NON, 0),
            "todo": n_todo, "written": len(auto), "ts": now}))
        conn.commit()
    finally:
        conn.close()

    _write_report(results, buckets, n_todo, report_samples)
    print(f"[rules] {RULE_VER}: 范围 {len(results):,} 篇 | "
          f"auto-EC {buckets.get(LABEL_EC, 0):,} | auto-非EC {buckets.get(LABEL_NON, 0):,} | "
          f"todo→LLM {n_todo:,}")


def _write_report(results, buckets, n_todo, n_samples):
    per_venue = defaultdict(Counter)
    for _, tag, dec, _, _ in results:
        per_venue[tag][dec or "todo"] += 1
    rng = random.Random(20260927)
    by_dec = defaultdict(list)
    for a, tag, dec, _, _ in results:
        if dec is not None:
            by_dec[dec].append((a, tag))
    samples = {}
    conn = _db.connect_ro()
    try:
        for dec, pool in by_dec.items():
            rng.shuffle(pool)
            picked = pool[:n_samples]
            ph = ",".join("?" * len(picked))
            titles = {r["accession_no"]: r["title"] for r in conn.execute(
                f"SELECT accession_no, title FROM papers WHERE accession_no IN ({ph})",
                [a for a, _ in picked])} if picked else {}
            samples[dec] = [(tag, titles.get(a, "")) for a, tag in picked]
    finally:
        conn.close()

    lines = [
        f"# 规则层报告（{RULE_VER}）\n",
        f"范围：B/C 两档 venue，共 {len(results):,} 篇。",
        f"- auto-EC：**{buckets.get(LABEL_EC, 0):,}** 篇（tier=rule, label=EC）",
        f"- auto-非EC：**{buckets.get(LABEL_NON, 0):,}** 篇（tier=rule, label=NON_EC）",
        f"- todo（交给 LLM）：**{n_todo:,}** 篇\n",
        "## 各 venue 分桶",
        "| venue_tag | 篇数 | auto-EC | auto-非EC | todo | EC占比(自动) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for tag, c in sorted(per_venue.items(), key=lambda kv: -sum(kv[1].values())):
        tot = sum(c.values())
        lines.append(f"| {tag} | {tot:,} | {c.get(LABEL_EC,0):,} | "
                     f"{c.get(LABEL_NON,0):,} | {c.get('todo',0):,} | "
                     f"{c.get(LABEL_EC,0)/tot:.0%} |")
    for dec, title in ((LABEL_EC, "auto-EC 抽样（人工核对精度）"),
                       (LABEL_NON, "auto-非EC 抽样（人工核对精度）")):
        lines += [f"\n## {title}\n"]
        for tag, t in samples[dec]:
            lines.append(f"- [{tag}] {t}")
    root = Path(_db.db_path()).parent.parent
    out = root / "reports" / "domain_rules_report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[rules] 报告 -> {out}")
