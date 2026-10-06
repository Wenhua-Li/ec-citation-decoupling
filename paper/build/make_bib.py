"""references.csv -> refs.bib

把 research/drafts/references.csv（手工维护的参考文献库）转换成论文用的 BibTeX。
脚本只读 CSV，只写输出文件；不修改 references.csv。

用法（在项目根目录运行）：
    python paper/build/make_bib.py

输出：paper/manuscript/refs.bib
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

# paper/build/make_bib.py -> 项目根 = 向上三级
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "research" / "drafts" / "references.csv"
DST = ROOT / "paper" / "manuscript" / "refs.bib"

# 需要按字符转义的 LaTeX 特殊字符
ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def latex_escape(text: str) -> str:
    """转义 LaTeX 特殊字符，但保留已经写好的 LaTeX 命令（以 \\ 开头的片段不动）。

    本库的作者字段含 \"o 这类重音写法（如 Érdi 已勘误为 Liu，但其他条目可能有），
    因此对反斜杠采取保守策略：若原文已含 LaTeX 命令样式（\\ 后跟字母），则不转义反斜杠本身。
    """
    has_command = "\\" in text
    out = []
    for ch in text:
        if ch in ESCAPES:
            if ch == "\\" and has_command:
                out.append(ch)  # 保留用户已写好的 LaTeX 命令
            else:
                out.append(ESCAPES[ch])
        else:
            out.append(ch)
    return "".join(out)


def entry_type(row: dict) -> str:
    """按 venue 猜 BibTeX 条目类型。"""
    venue = (row.get("venue") or "").lower()
    doi = (row.get("doi") or "").strip()
    url = (row.get("url") or "").lower()
    if "arxiv" in venue or "arxiv" in url:
        return "misc"
    if not doi:
        # 专著 / 技术报告 / 在线文档
        if any(k in venue for k in ("report", "press", "university", "book")):
            return "techreport"
        return "misc"
    if any(k in venue for k in ("conference", "proceedings", "icml", "neurips", "gecco",
                                "congress", "symposium", "workshop")):
        return "inproceedings"
    return "article"


def bib_key(row: dict) -> str:
    """生成引用键：首作者姓氏 + 年份（小写）；同名同年的加后缀。"""
    authors = row.get("authors") or ""
    first = authors.split(";")[0].split(",")[0].strip()
    first = "".join(c for c in first if c.isalnum()) or "anon"
    year = (row.get("year") or "n.d.").strip()
    return f"{first.lower()}{year}"


def build() -> int:
    if not SRC.exists():
        print(f"[make_bib] 源文件不存在：{SRC}", file=sys.stderr)
        return 1

    with SRC.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    used: dict[str, int] = {}
    blocks: list[str] = [
        "% refs.bib — 由 paper/build/make_bib.py 从 research/drafts/references.csv 生成",
        "% 请勿手工编辑本文件：改条目请改 references.csv，然后重跑脚本。",
        f"% 条目数：{len(rows)}",
        "",
    ]

    for row in rows:
        key = bib_key(row)
        used[key] = used.get(key, 0) + 1
        if used[key] > 1:
            key = f"{key}{chr(ord('a') + used[key] - 2)}"

        kind = entry_type(row)
        fields: list[tuple[str, str]] = []

        authors = (row.get("authors") or "").strip()
        if authors:
            # "Surname, Given; Surname2, Given2" -> "Surname, Given and Surname2, Given2"
            fields.append(("author", " and ".join(a.strip() for a in authors.split(";"))))
        if (row.get("title") or "").strip():
            fields.append(("title", row["title"].strip()))
        if (row.get("year") or "").strip():
            fields.append(("year", row["year"].strip()))

        venue = (row.get("venue") or "").strip()
        if venue:
            if kind == "inproceedings":
                fields.append(("booktitle", venue))
            elif kind == "article":
                fields.append(("journal", venue))
            else:
                fields.append(("howpublished", venue))

        if (row.get("doi") or "").strip():
            fields.append(("doi", row["doi"].strip()))
        if (row.get("url") or "").strip():
            fields.append(("url", row["url"].strip()))

        # note 列在 references.csv 里是内部工作注记（中文、含工作项编号与勘误痕迹），
        # 只供内部查阅，**不进 .bib**——投稿件不得含内部代号与中文注记（AGENTS.md 硬规则 5），
        # 且中文会让 pdflatex 编译失败。需要保留的理由写进各自条目的内部注释。
        note = (row.get("note") or "").strip()
        if note and "--include-notes" in sys.argv:
            fields.append(("note", note))

        blocks.append(f"@{kind}{{{key},")
        width = max(len(k) for k, _ in fields) if fields else 0
        for name, value in fields:
            blocks.append(f"  {name.ljust(width)} = {{{latex_escape(value)}}},")
        blocks.append("}")
        blocks.append("")

    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text("\n".join(blocks), encoding="utf-8")

    print(f"[make_bib] {len(rows)} 条 -> {DST.relative_to(ROOT)}")
    keys = list(used)
    print(f"[make_bib] 引用键：{', '.join(keys[:8])}{' …' if len(keys) > 8 else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
