# -*- coding: utf-8 -*-
"""R3-E' 设计期诊断：EC 子方向互斥归属的覆盖率检验（只读，不写库）。

纪律：本脚本只做**语料构成**诊断（EC 论文按候选关键词优先级序列的归属分布），
**不连接任何作者/新人数据**——新人首选份额按子方向的拆分是 R3-A 的执行内容，
冻结前不得计算。设计期用途：验证"不可判定率 ≤10%"门槛在诚实规则下可达，
并把模式集迭代过程留痕（json 内 iterations 表）供预注册审计。

用法：python research/nature/r3e_coverage.py
输出：research/nature/out/r3e_coverage.json + 控制台摘要
"""
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ecdb

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------------------
# 候选模式集（优先级 = 列表顺序；先匹配先归属，互斥）。
# 设计原则：特异进化方法族 -> 群智能族 -> 融合族 -> 问题类族(EMO) -> 最大通用族(GA)
#           -> 特征词残余族(其他元启发式) -> 通用进化兜底 -> 泛启发式兜底 -> OTHER。
# 文本口径与 terms.py 一致：(title + "\\n" + abstract).lower()，re.I。
# ---------------------------------------------------------------------------

FAMILIES_V1 = [
    ("neuroevolution", r"neuroevolution|neuro-evolution|evolutionary neural|evolving neural|evolved neural|genetic neural"),
    ("genetic_programming", r"genetic programming"),
    ("eda", r"estimation of distribution|probabilistic model.?building|PMBGA"),
    ("evolution_strategies", r"evolution strateg|evolutionary strateg"),
    ("differential_evolution", r"differential evolution"),
    ("particle_swarm", r"particle swarm|\bPSO\b"),
    ("ant_colony", r"ant colony|\bACO\b"),
    ("other_swarm_bio", r"swarm intelligence|artificial bee|bee colony|bees algorithm|bee swarm|cuckoo search|firefly algorithm|bat algorithm|grey wolf|gray wolf|wolf optimi|whale optimi|harmony search|flower pollination|ant lion|grasshopper optimi|salp swarm|krill herd|bacterial foraging|glowworm|social spider|cat swarm|shuffled frog|locust swarm|artificial fish"),
    ("lcs", r"learning classifier system|\bXCS\b|Michigan.style"),
    ("memetic_hybrid", r"memetic|hybrid genetic|hybrid evolutionary|lamarckian|hybrid meta.?heuristic"),
    ("hyper_heuristic", r"hyper.?heuristic"),
    ("genetic_fuzzy", r"(genetic|evolutionary|evolved|evolving) fuzzy|fuzzy (genetic|evolutionary)|fuzzy rule base.{0,40}(genetic|evolution)"),
    ("emo", r"multi.?objective (evolutionary|genetic|memetic)|many.?objective|multiobjective (evolutionary|genetic)|NSGA|MOEA|SPEA|Pareto (evolutionary|dominan|front|set|rank|archive|sort|based)"),
    ("ga", r"genetic algorithm"),
    ("general_ec", r"evolutionary (algorithm|computation|computing|programming|optimi|search|approach|method|technique|framework|model|process|procedure|scheme|operator|strategy)|evolutionary.based|evolution.based|genetic operator|crossover|fitness landscape|fitness function|population.based (algorithm|optimi|search|method)|evolv(ed|ing) (algorithm|population|operator|heuristic)"),
]

# v2（依据 v1 的 OTHER 抽样 40 例人工归因设计；抽样过程见 R3E_FREEZE.md 迭代表）：
#  + 新增 other_metaheuristic（禁忌/模拟退火/GRASP/VNS/LNS/人工免疫/膜计算/新兴隐喻算法等特征词，置于 GA 后、通用进化前）
#  + 新增 generic_heuristic（裸 heuristic/metaheuristic 最后兜底，置于通用进化后——避免抢占自称进化的论文）
#  + emo 放宽至裸 multi-objective/many-objective 措辞（EC 语料内＝EMO 社区去向）
#  + ga 扩展 genetic-based/quantum genetic 等措辞
#  + general_ec 增补 coevolution、裸 evolutionary/genetic/evolution 兜底
FAMILIES_V2 = [
    ("neuroevolution", r"neuroevolution|neuro-evolution|evolutionary neural|evolving neural|evolved neural|genetic neural"),
    ("genetic_programming", r"genetic programming"),
    ("eda", r"estimation of distribution|probabilistic model.?building|PMBGA"),
    ("evolution_strategies", r"evolution strateg|evolutionary strateg"),
    ("differential_evolution", r"differential evolution"),
    ("particle_swarm", r"particle swarm|\bPSO\b"),
    ("ant_colony", r"ant colony|\bACO\b"),
    ("other_swarm_bio", r"swarm intelligence|artificial bee|bee colony|bees algorithm|bee swarm|cuckoo search|firefly algorithm|bat algorithm|grey wolf|gray wolf|wolf optimi|whale optimi|harmony search|flower pollination|ant lion|grasshopper optimi|salp swarm|krill herd|bacterial foraging|glowworm|social spider|cat swarm|shuffled frog|locust swarm|artificial fish"),
    ("lcs", r"learning classifier system|\bXCS\b|Michigan.style"),
    ("memetic_hybrid", r"memetic|hybrid genetic|hybrid evolutionary|lamarckian|hybrid meta.?heuristic"),
    ("hyper_heuristic", r"hyper.?heuristic"),
    ("genetic_fuzzy", r"(genetic|evolutionary|evolved|evolving) fuzzy|fuzzy (genetic|evolutionary)|fuzzy rule base.{0,40}(genetic|evolution)"),
    ("emo", r"multi.?objective|many.?objective|multiobjective|NSGA|MOEA|SPEA|Pareto"),
    ("ga", r"genetic algorithm|genetic.based|genetic (search|method|approach|technique|encoding|representation)|quantum genetic|quantum.ga\b"),
    ("other_metaheuristic", r"tabu|simulated annealing|greedy randomized adaptive|GRASP|path relinking|variable neighborhood|large neighborhood search|artificial immune|immune (algorithm|system|network)|immunolog|extremal optimization|membrane (computing|algorithm)|water cycle|water wave|crow search|atom search|slime mould|slime mold|harris hawk|gravitational search|sine cosine|moth.flame|aquila|chimp optimi|stochastic diffusion search|iterated local search|guided local search"),
    ("general_ec", r"evolutionary|evolution|evolv(e|es|ed|ing)|co.?evolution|genetic|crossover|mutation|fitness landscape|fitness function|selection pressure|population.based|recombination operator"),
    ("generic_heuristic", r"meta.?heuristic|matheuristic|heuristic|greedy|local search|neighborhood search|branch.and.bound"),
]

# v3（依据 v2 OTHER 抽样 25 例的定向增补，非全词表扩张）:
#  + emo: hypervolume / indicator-based（EMO 指标理论词汇，无歧义）
#  + other_swarm_bio: 裸 swarm（置于 PSO/ACO 后不冲突）与 nature/bio/physics-inspired 类措辞、pigeon/termite/imperialist/league championship 等已观测隐喻算法
#  + general_ec: \bEA\b/\bEAs\b（EC 语料内无歧义缩写）与 GA 理论词（deceptive/deception/royal road/schema theorem/building block）
FAMILIES_V3 = [
    ("neuroevolution", r"neuroevolution|neuro-evolution|evolutionary neural|evolving neural|evolved neural|genetic neural"),
    ("genetic_programming", r"genetic programming"),
    ("eda", r"estimation of distribution|probabilistic model.?building|PMBGA"),
    ("evolution_strategies", r"evolution strateg|evolutionary strateg"),
    ("differential_evolution", r"differential evolution"),
    ("particle_swarm", r"particle swarm|\bPSO\b"),
    ("ant_colony", r"ant colony|\bACO\b"),
    ("other_swarm_bio", r"swarm|artificial bee|bee colony|bees algorithm|cuckoo search|firefly algorithm|bat algorithm|grey wolf|gray wolf|whale optimi|harmony search|flower pollination|ant lion|grasshopper optimi|salp|krill|bacterial foraging|glowworm|social spider|cat swarm|shuffled frog|artificial fish|nature.inspired|nature inspired|bio.?inspired|physics?.inspired|pigeon|termite|imperialist|league championship|crow search|water cycle|water wave|slime mould|slime mold|harris hawk|moth.flame|ant colony"),
    ("lcs", r"learning classifier system|\bXCS\b|Michigan.style"),
    ("memetic_hybrid", r"memetic|hybrid genetic|hybrid evolutionary|lamarckian|hybrid meta.?heuristic"),
    ("hyper_heuristic", r"hyper.?heuristic"),
    ("genetic_fuzzy", r"(genetic|evolutionary|evolved|evolving) fuzzy|fuzzy (genetic|evolutionary)|fuzzy rule base.{0,40}(genetic|evolution)"),
    ("emo", r"multi.?objective|many.?objective|multiobjective|NSGA|MOEA|SPEA|Pareto|hypervolume|indicator.based"),
    ("ga", r"genetic algorithm|genetic.based|genetic (search|method|approach|technique|encoding|representation)|quantum genetic|quantum.ga\b"),
    ("other_metaheuristic", r"tabu|simulated annealing|greedy randomized adaptive|GRASP|path relinking|variable neighborhood|large neighborhood search|artificial immune|immune (algorithm|system|network)|immunolog|extremal optimization|membrane (computing|algorithm)|gravitational search|sine cosine|aquila|chimp optimi|stochastic diffusion search|iterated local search|guided local search|atom search"),
    ("general_ec", r"evolutionary|evolution|evolv(e|es|ed|ing)|co.?evolution|genetic|crossover|mutation|fitness landscape|fitness function|selection pressure|population.based|recombination operator|\bEAs?\b|deceptive|deception|royal road|schema theorem|building block"),
    ("generic_heuristic", r"meta.?heuristic|matheuristic|heuristic|greedy|local search|neighborhood search|branch.and.bound"),
]

WINDOWS = {"G1_2003_2007": (2003, 2007), "G2_2019_2022": (2019, 2022)}


def evaluate(rows, families, label):
    pats = [(name, re.compile(pat, re.I)) for name, pat in families]
    assigned = defaultdict(int)
    win_stat = {w: [0, 0] for w in WINDOWS}
    for r in rows:
        txt = r["txt"]
        hit = None
        for name, pat in pats:
            if pat.search(txt):
                hit = name
                break
        fam = hit if hit else "OTHER"
        assigned[fam] += 1
        y = r["y"]
        if y is not None:
            for w, (a, b) in WINDOWS.items():
                if a <= y <= b:
                    win_stat[w][1] += 1
                    if hit is None:
                        win_stat[w][0] += 1
    n = len(rows)
    return {
        "label": label,
        "n_ec_papers": n,
        "assigned_counts": dict(sorted(assigned.items(), key=lambda kv: -kv[1])),
        "other_rate_all": round(sum(v for k, v in assigned.items() if k == "OTHER") / n, 4),
        "other_rate_by_window": {w: [round(o / t, 4), o, t] for w, (o, t) in win_stat.items()},
    }


if __name__ == "__main__":
    print("loading EC papers ...", flush=True)
    raw = ecdb.raw_sql(
        "SELECT p.accession_no acc, p.pub_year y, p.title t, p.abstract ab "
        "FROM papers p JOIN paper_domain d ON d.accession_no=p.accession_no "
        "WHERE d.label='EC'",
        max_rows=60000,
    )["rows"]
    rows = [{"y": r["y"], "txt": ((r["t"] or "") + " \n " + (r["ab"] or "")).lower()} for r in raw]
    print(f"EC papers: {len(rows)}", flush=True)

    iterations = [evaluate(rows, FAMILIES_V1, "v1"), evaluate(rows, FAMILIES_V2, "v2"),
                  evaluate(rows, FAMILIES_V3, "v3")]
    result = {"generated": "R3-E' design-phase diagnostic", "frozen_note": "构成诊断，未触碰新人数据",
              "iterations": iterations}
    with open(os.path.join(OUT, "r3e_coverage.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    for last in iterations:
        print(f"\n=== {last['label']} ===")
        print(f"OTHER rate (all): {last['other_rate_all']:.1%}")
        for w, v in last["other_rate_by_window"].items():
            print(f"OTHER {w}: {v[0]:.1%} ({v[1]}/{v[2]})")
        for k, v in last["assigned_counts"].items():
            print(f"  {k:<22} {v:>6}  ({v/last['n_ec_papers']:.1%})")
