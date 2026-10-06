# -*- coding: utf-8 -*-
"""W4a 尾巴（W0.8 遗留，评审 F18）：P4 关键模式的抽样校验材料生成。

对 LLM/GPT、prompt、transformer（限定版）三个模式：
  - 正样本：2023-2025 年 EC 论文中命中的随机 50 篇/模式，dump 标题 + 命中上下文（±70 字符）
  - 负样本：2024-2025 年 EC 论文中未命中三模式的随机 50 篇，dump 标题 + 摘要前 160 字符
    （用于人工扫描假阴性：明明在讲 LLM/提示词/Transformer 却没被模式抓住的）
人工复核结论记入 research/notes/p4_validation.md（精确率/召回率估计）。
输出：research/nature/out/p4_validation_samples.txt
"""
import json
import os
import random
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ecdb

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

PATTERNS = {
    "LLM/GPT": r"large language model|\bllms?\b|\bgpt\b|chatgpt",
    "prompt": r"\bprompt",
    "transformer": r"transformer\s+(models?|architectures?|networks?|encoders?|decoders?)",
}
ALL = re.compile("|".join(PATTERNS.values()), re.I)

ec_rows = ecdb.raw_sql(
    "SELECT p.accession_no acc, p.pub_year y, p.title, p.abstract FROM papers p "
    "JOIN paper_domain d USING(accession_no) WHERE d.label='EC' AND p.pub_year >= 2023",
    max_rows=200000,
)["rows"]
print(f"EC papers 2023+: {len(ec_rows)}")

random.seed(20260929)
lines = []
for name, pat in PATTERNS.items():
    pc = re.compile(pat, re.I)
    matched = []
    for r in ec_rows:
        txt = ((r["title"] or "") + " \n " + (r["abstract"] or ""))
        m = pc.search(txt)
        if m:
            s, e = max(0, m.start() - 70), min(len(txt), m.end() + 70)
            matched.append((r, txt[s:e].replace("\n", " ")))
    sample = random.sample(matched, min(50, len(matched)))
    lines.append(f"\n{'='*90}\n### 模式 [{name}] 命中 {len(matched)} 篇，抽样 {len(sample)} 篇\n{'='*90}")
    for r, ctx in sample:
        lines.append(f"[{r['y']}] {r['title']}\n    ctx: ...{ctx}...\n")

neg = [r for r in ec_rows if not ALL.search((r["title"] or "") + " \n " + (r["abstract"] or "")) and (r["abstract"] or "")]
neg_sample = random.sample(neg, min(50, len(neg)))
lines.append(f"\n{'='*90}\n### 负样本（三模式均未命中，2023+，抽样 {len(neg_sample)} 篇，查假阴性）\n{'='*90}")
for r in neg_sample:
    ab = (r["abstract"] or "").replace("\n", " ")[:160]
    lines.append(f"[{r['y']}] {r['title']}\n    abs: {ab}...\n")

path = os.path.join(OUT, "p4_validation_samples.txt")
with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"written: {path} ({len(lines)} lines)")
print("命中率概览：", {name: len([1 for r in ec_rows if re.compile(p, re.I).search((r['title'] or '') + ' ' + (r['abstract'] or ''))]) for name, p in PATTERNS.items()}, "/", len(ec_rows))
