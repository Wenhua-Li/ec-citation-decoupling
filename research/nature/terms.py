# -*- coding: utf-8 -*-
"""主题时尚周期 + 词汇更替分析。

指标（按年份、按 EC / A_pure_ec / 全库三个口径）：
  1) 标题+摘要包含指定模式串的论文份额（LIKE 扫描，大小写不敏感）
  2) survey/review 标题份额（综述膨胀）
  3) 受控关键词 top-N 的年度份额曲线（EC 自有词汇的潮汐）
输出：research/nature/out/terms.json
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

tier_of = {}
for r in ecdb.raw_sql("SELECT venue_tag, tier FROM venue_tier", max_rows=200)["rows"]:
    tier_of[r["venue_tag"]] = r["tier"]

PATTERNS = {
    "genetic algorithm": r"genetic algorithm",
    "particle swarm": r"particle swarm|\bpsos?\b",
    "differential evolution": r"differential evolution",
    "multi-objective": r"multi-?objective",
    "estimation of distribution": r"estimation of distribution",
    "surrogate": r"surrogate",
    "neuroevolution": r"neuroevolution|neuro-evolution|evolving neural",
    "novelty/quality-diversity": r"novelty search|quality-?diversity|illumination",
    "deep learning": r"deep learning|deep neural",
    "reinforcement learning": r"reinforcement learning",
    # W0.8（评审 F18）：transformer 单词多义（含电力变压器等），限定上下文
    "transformer": r"transformer\s+(models?|architectures?|networks?|encoders?|decoders?)",
    "LLM/GPT": r"large language model|\bllms?\b|\bgpt\b|chatgpt",
    # W4a 抽样校验后收紧（原 \bprompt 精确率仅 ~72%，混入英语动词/副词 prompt(ed)/promptly）
    "prompt": r"prompt[- ](?:engineering|optimi[sz]ation|design|space|chaining|embedding|tuning|strateg|evolution|template)|prompt[- ]based|few[- ]shot prompt|zero[- ]shot prompt|(?:llm|language model) prompts?",
    "metaheuristic(s)": r"metaheuristic|meta-heuristic",
    "no free lunch": r"no free lunch",
    "hyperheuristic": r"hyper-?heuristic",
    "explainable AI": r"explainab|interpretab",
    # W0.8（评审 F12）：撤回的受控词跨年结论改用标题+摘要模式匹配口径重算
    "computational complexity": r"computational complexity",
    "constraint handling": r"constraint (handling|theory|processing)",
    "simulated annealing": r"simulated annealing",
    "artificial intelligence": r"\bartificial intelligence\b",
    "convergence analysis": r"convergence (analysis|proof|theor)",
}

surveys_pat = re.compile(r"\b(survey|review|systematic review|state of the art|state-of-the-art)\b", re.I)

def load_year_texts(where="", params=()):
    """-> list of (year, text, is_a_tier)"""
    rows = ecdb.raw_sql(
        f"SELECT accession_no acc, pub_year y, title, abstract, venue_tag vt FROM papers {where}",
        params=params,
        max_rows=200000,
    )["rows"]
    out = []
    for r in rows:
        txt = ((r["title"] or "") + " \n " + (r["abstract"] or "")).lower()
        out.append((r["y"], txt, tier_of.get(r["vt"]) == "A_pure_ec"))
    return out

print("loading all papers text ...", flush=True)
texts = load_year_texts()
print(f"papers: {len(texts)}", flush=True)

pat_c = {k: re.compile(v, re.I) for k, v in PATTERNS.items()}
agg = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))  # year -> pattern -> [all_n, ec?, a_n]
# ec 标签单独取
ec_set = set()
for r in ecdb.raw_sql("SELECT accession_no acc FROM paper_domain WHERE label='EC'", max_rows=100000)["rows"]:
    ec_set.add(r["acc"])
ec_flag = {}
for r in ecdb.raw_sql("SELECT accession_no acc, venue_tag vt FROM papers", max_rows=200000)["rows"]:
    ec_flag[r["acc"]] = None

# 需要 acc 对应：重新带 acc 载入
print("matching patterns ...", flush=True)
rows = ecdb.raw_sql(
    "SELECT accession_no acc, pub_year y, title, abstract, venue_tag vt FROM papers",
    max_rows=200000,
)["rows"]
counts = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))  # year -> name -> [n_all, n_ec, n_a]
denom = defaultdict(lambda: [0, 0, 0])
survey_counts = defaultdict(lambda: [0, 0, 0])
for r in rows:
    y = r["y"]
    is_ec = r["acc"] in ec_set
    is_a = tier_of.get(r["vt"]) == "A_pure_ec"
    txt = ((r["title"] or "") + " \n " + (r["abstract"] or "")).lower()
    di = 0 if not is_a else 2
    denom[y][0] += 1
    if is_ec:
        denom[y][1] += 1
    if is_a:
        denom[y][2] += 1
    if surveys_pat.search(r["title"] or ""):
        survey_counts[y][0] += 1
        if is_ec:
            survey_counts[y][1] += 1
        if is_a:
            survey_counts[y][2] += 1
    for name, pc in pat_c.items():
        if pc.search(txt):
            counts[y][name][0] += 1
            if is_ec:
                counts[y][name][1] += 1
            if is_a:
                counts[y][name][2] += 1

result = {"share": defaultdict(dict), "denom": {str(y): v for y, v in denom.items()},
          "survey_share": {},
          "meta": {
              "denom_defs": {
                  "all": "全库论文数", "ec": "EC 打标子集论文数", "a": "A_pure_ec 期刊论文数",
              },
              "caveat": "受控词（term_tides_*）受 EI 标引政策漂移影响，只做同年内跨组比较；"
                        "跨年强结论一律用本表 share 的模式匹配口径（评审 F12，data_caveats 第 6 条）",
              "revised": "2026-09-29 W0.8：transformer 限定上下文；新增理论术语模式（替代受控词跨年结论）",
          }}
for y in sorted(denom):
    for name in PATTERNS:
        c = counts[y][name]
        result["share"][name][str(y)] = {
            "all": round(c[0] / denom[y][0], 4) if denom[y][0] else None,
            "ec": round(c[1] / denom[y][1], 4) if denom[y][1] else None,
            "a": round(c[2] / denom[y][2], 4) if denom[y][2] else None,
        }
    result["survey_share"][str(y)] = {
        "all": round(survey_counts[y][0] / denom[y][0], 4),
        "ec": round(survey_counts[y][1] / denom[y][1], 4),
        "a": round(survey_counts[y][2] / denom[y][2], 4),
    }
result["share"] = dict(result["share"])

# 受控词表 top 潮汐：EC 论文里份额变化最大的受控词
print("controlled-term tides ...", flush=True)
rows = ecdb.raw_sql(
    """
    SELECT t.term, p.pub_year y, COUNT(*) n
    FROM paper_terms t
    JOIN papers p USING(accession_no)
    JOIN paper_domain d USING(accession_no)
    WHERE d.label='EC' AND t.kind='controlled'
    GROUP BY t.term, p.pub_year
    """,
    max_rows=500000,
)["rows"]
term_year = defaultdict(dict)
for r in rows:
    term_year[r["term"]][r["y"]] = r["n"]
ec_denom = {y: v[1] for y, v in denom.items()}
tides = []
for term, ys in term_year.items():
    tot = sum(ys.values())
    if tot < 400:
        continue
    shares = {y: n / ec_denom[y] for y, n in ys.items() if ec_denom.get(y)}
    if not shares:
        continue
    peak_y = max(shares, key=shares.get)
    early = statistics_mean = None
    def avg(rng):
        vs = [shares[y] for y in rng if y in shares]
        return sum(vs) / len(vs) if vs else None
    e = avg(range(2003, 2009))
    l = avg(range(2019, 2026))
    if e is None or l is None:
        continue
    tides.append({"term": term, "n": tot, "peak_year": peak_y, "peak_share": round(shares[peak_y], 4),
                  "early_03_08": round(e, 4), "late_19_25": round(l, 4), "ratio_late_over_early": round(l / e, 2) if e > 0 else None})
tides.sort(key=lambda t: -(t["ratio_late_over_early"] or 0))
result["term_tides_top"] = tides[:40]
tides.sort(key=lambda t: (t["ratio_late_over_early"] or 99))
result["term_tides_bottom"] = tides[:40]

with open(os.path.join(OUT, "terms.json"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)

print("\n=== EC 论文中模式份额（%） ===")
hdr = "pattern                 " + "".join(f"{y:>7}" for y in (2005, 2010, 2015, 2018, 2021, 2023, 2025))
print(hdr)
for name in PATTERNS:
    vals = []
    for y in (2005, 2010, 2015, 2018, 2021, 2023, 2025):
        s = result["share"][name].get(str(y), {}).get("ec")
        vals.append(f"{s*100:.2f}" if s is not None else "  -  ")
    print(f"{name:<24}" + "".join(f"{v:>7}" for v in vals))
print("\n=== A_pure_ec 期刊中 LLM/GPT 与 prompt 份额（%） ===")
for name in ("LLM/GPT", "prompt", "deep learning", "transformer"):
    vals = []
    for y in range(2012, 2026):
        s = result["share"][name].get(str(y), {}).get("a")
        vals.append(f"{y}:{s*100:.2f}" if s is not None else f"{y}:  -  ")
    print(f"{name:<22}", "  ".join(vals))
print("\n=== survey/review 标题份额（%）all | ec ===")
for y in range(2003, 2026, 2):
    s = result["survey_share"].get(str(y))
    if s:
        print(y, f"all={s['all']*100:.1f}%  ec={s['ec']*100:.1f}%")
print("\n=== 受控词潮汐： Late(19-25)/Early(03-08) 比值 Top15 ===")
for t in result["term_tides_top"][:15]:
    print(f"{t['term']:<50} peak={t['peak_year']} {t['early_03_08']:.3f}->{t['late_19_25']:.3f} x{t['ratio_late_over_early']}")
print("\n=== 受控词潮汐：衰减 Bottom15 ===")
for t in result["term_tides_bottom"][:15]:
    print(f"{t['term']:<50} peak={t['peak_year']} {t['early_03_08']:.3f}->{t['late_19_25']:.3f} x{t['ratio_late_over_early']}")
