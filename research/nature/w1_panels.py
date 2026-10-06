# -*- coding: utf-8 -*-
"""W1 主体启动（骨架阶段）：对照领域面板——年度发文曲线与参考文献可用性。

设计（PLAN v3 W1"两种测量"：本库=高分辨率主结果；外库=低分辨率轮廓佐证）：
  - 6 个对照领域 × 1-2 本锚定期刊（OpenAlex source），1985-2025；
  - 每本期刊两条曲线：总 works 年度量、has_references:true 年度量（group_by，每刊 2 次调用）；
  - 附 DOI 一致性抽查留待下一阶段（按 DOI 对齐本库/逐篇拉取）。
锚定期刊（领域代表，正式论文中须按三口径一致性再校准）：
  运筹优化 EJOR / 管理科学 Management Science；控制 Automatica；机器人 IJRR；
  NLP Computational Linguistics；计算机视觉 IJCV；演化生物学 Journal of Theoretical Biology；
  机器学习（牛市对照）Machine Learning（Springer）。
输出：research/nature/out/w1_panels.json
"""
import json
import os
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

MAILTO = "ecmap.project@outlook.com"
BASE = "https://api.openalex.org"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": f"ecmap-w1panels ({MAILTO})"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


FIELDS = {
    "operations_research": ["European Journal of Operational Research", "Management Science"],
    "control_theory": ["Automatica", "IEEE Transactions on Automatic Control"],
    "robotics": ["The International Journal of Robotics Research", "Robotics and Autonomous Systems"],
    "nlp": ["Computational Linguistics"],
    "computer_vision": ["International Journal of Computer Vision"],
    "evolutionary_biology": ["Journal of Theoretical Biology"],
    "machine_learning_bull": ["Machine Learning"],
}

Y0, Y1 = 1985, 2025

out = {}
for field, journals in FIELDS.items():
    out[field] = {}
    for j in journals:
        src = get(f"{BASE}/sources?search={urllib.parse.quote(j)}&per-page=1&mailto={MAILTO}")["results"][0]
        sid = src["id"].rsplit("/", 1)[-1]
        time.sleep(0.12)
        curves = {}
        for label, extra in (("total", ""), ("with_refs", ",has_references:true")):
            url = (f"{BASE}/works?filter=primary_location.source.id:{sid},"
                   f"from_publication_date:{Y0}-01-01,to_publication_date:{Y1}-12-31{extra}"
                   f"&group_by=publication_year&per-page=200&mailto={MAILTO}")
            curves[label] = {int(b["key"]): b["count"] for b in get(url)["group_by"] if Y0 <= int(b["key"]) <= Y1}
            time.sleep(0.12)
        yrs = sorted(curves["total"])
        ref_rate = round(sum(curves["with_refs"].values()) / max(1, sum(curves["total"].values())), 3)
        out[field][j] = {"source_id": sid, "display_name": src["display_name"],
                         "total": curves["total"], "with_refs": curves["with_refs"],
                         "n_total": sum(curves["total"].values()), "ref_rate": ref_rate}
        sample = {y: curves["total"][y] for y in yrs if y % 5 == 0}
        print(f"[{field}] {src['display_name']} (S={sid})  n={out[field][j]['n_total']}  refs可用率={ref_rate:.1%}")
        print("   ", sample)
print()
with open(os.path.join(OUT, "w1_panels.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("saved w1_panels.json")
