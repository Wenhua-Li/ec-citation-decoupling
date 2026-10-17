# -*- coding: utf-8 -*-
"""第二多源语料面板下载（2026-10-15 冻结清单 sources.json；复用 W1 oa_client 预算管理）。

用法：python panel_download.py（断点续传：.done 跳过）
输出：data/<field>__<sid>.jsonl + data/<field>__<sid>.done + out/download_summary.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from oa_client import iter_works  # noqa: E402

DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "out")
os.makedirs(DATA, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

spec = json.load(open(os.path.join(HERE, "sources.json"), encoding="utf-8"))
summary = []
for s in spec["sources"]:
    name = f"{s['field']}__{s['sid']}"
    done = os.path.join(DATA, name + ".done")
    if os.path.exists(done):
        print(f"[skip] {name}（已完成 {open(done).read().strip()} 条）", flush=True)
        continue
    filt = f"primary_location.source.id:{s['sid']},{spec['window']}"
    n = 0
    with open(os.path.join(DATA, name + ".jsonl"), "w", encoding="utf-8") as f:
        for w in iter_works(filt, spec["select"]):
            f.write(json.dumps(w, ensure_ascii=False) + "\n")
            n += 1
    with open(done, "w", encoding="utf-8") as f:
        f.write(str(n))
    print(f"[done] {name} ({s['journal']}): {n} 条", flush=True)
    summary.append({**s, "downloaded": n})

if summary:
    with open(os.path.join(OUT, "download_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
print("all sources processed.", flush=True)
