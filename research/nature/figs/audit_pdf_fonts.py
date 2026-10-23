# -*- coding: utf-8 -*-
"""PDF 文本字号审计：figs/reconstruction/ 下全部 PDF 的最小字号（设计字号）须 >= 7.0 pt。

依据（2026-10-20 图组重构 G2 裁定）：sn-jnl 单栏 \textwidth = 372.0pt = 130.74mm，
183mm 图件被缩放 0.7148×；NC 终尺寸最小字号下限 5pt → 设计字号须 >= 5/0.7148 = 7.0pt。
（此前门限 6.0pt → 落地 4.29pt，低于 NC 下限；三席评审 D10 裁定升级。）

用法：python research/nature/figs/audit_pdf_fonts.py
退出码 0 = 全部通过。由 pypdf 的 visitor_text 逐页收集字体大小。
（2026-10-17 重建：原 audit_pdf_text.py 未随图组迁移，按工序要求补写最小版。）
"""
import os
import sys

from pypdf import PdfReader

HERE = os.path.dirname(os.path.abspath(__file__))
FIG_DIR = os.path.join(HERE, "reconstruction")
SCALE = 0.7148
FLOOR = 7.0


def min_font(path):
    sizes = []

    def visitor(text, cm, tm, font_dict, font_size):
        if text.strip() and font_size:
            sizes.append(round(float(font_size), 2))

    reader = PdfReader(path)
    for page in reader.pages:
        page.extract_text(visitor_text=visitor)
    return min(sizes) if sizes else None


def main():
    targets = [a for a in sys.argv[1:] if a]
    bad = 0
    for name in sorted(os.listdir(FIG_DIR)):
        if not name.endswith(".pdf"):
            continue
        if targets and name not in targets:
            continue
        m = min_font(os.path.join(FIG_DIR, name))
        status = "OK" if (m is not None and m >= FLOOR) else "FAIL"
        if status == "FAIL":
            bad += 1
        print(f"{name:44s} min font = {m} pt (rendered ~{m * SCALE:.1f})  [{status}]")
    scope = "all" if not targets else f"{len(targets)} file(s)"
    print(f"floor {FLOOR} pt design (~{FLOOR * SCALE:.1f} pt rendered), scope={scope}; {'ALL PASS' if bad == 0 else f'{bad} file(s) FAIL'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
