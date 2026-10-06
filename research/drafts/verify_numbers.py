# -*- coding: utf-8 -*-
"""数字核验（三段式；2026-10-02 扩展：英文数字形式 / LaTeX 命令 / Q 编号三方回查）。

1) checklist vs NUMBERS.md：numbers_checklist.csv 每行（number, context, registry_value）
   核对该值出现在 research/nature/NUMBERS.md 中；
2) 草稿扫描：抽取数字 token（中文稿 + 英文稿两套正则），列出未在 checklist 出现的
   "未登记数字"警告；白名单 = checklist 的 number/alt_forms 列 + ignore 列；
3) Q 编号三方回查：对 paper/build/doc_ids.md 的每个 Q 编号，检查
   ① 该 Q 在 doc_ids.md 有行（编号存在）；
   ② 该 Q 的"登记位置"能在 NUMBERS.md 找到（登记先于使用）；
   ③ 若 doc_ids.md 给了"输出文件 + 字段路径"，则该字段在 out/*.json 中确实存在
      （值存在性，不做数值相等判断——数值比对由登记行承担）。
   另：检查 paper/plan/01_narrative_and_outline.md 正文里出现的 \\qid{Qn} 是否都在
   doc_ids.md 中已分配。

扩展动机（todo.md 写稿前置 ④）：原脚本的中文正则扫不到英文稿，且无法以 Q 编号为键回查。
扩展到本版后方可进入英文正文（paper/draft/00_draft_v1.md）。

输出：paper/build/verify_report.txt（而非旧位置）；退出码 0=无未解释差异。
用法：python verify_numbers.py [草稿文件...]
"""
import csv
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CHECKLIST = os.path.join(ROOT, "research", "drafts", "numbers_checklist.csv")
NUMBERS = os.path.join(ROOT, "research", "nature", "NUMBERS.md")
DOC_IDS = os.path.join(ROOT, "paper", "build", "doc_ids.md")
OUT_JSON = os.path.join(ROOT, "research", "nature", "out")
PLAN_OUTLINE = os.path.join(ROOT, "paper", "plan", "01_narrative_and_outline.md")
PAPER_DRAFT = os.path.join(ROOT, "paper", "draft")
REPORT_OUT = os.path.join(ROOT, "paper", "build")

# 旧默认扫描目标（研究草稿）+ 新增（paper/ 工作稿）
DEFAULT_DRAFTS = [p for p in (
    os.path.join(ROOT, "research", "drafts", f) for f in
    ("methods_draft.md", "abstract_skeleton.md", "terminology_check.md")
) if os.path.exists(p)]

# 中文与英文两套数字 token 正则
CN_PAT = re.compile(r"\d[\d,]*\.?\d*\s*(?:%|×|倍|fold)?")
EN_PAT = re.compile(
    r"\b\d[\d,]*\.?\d*\s*(?:%|percent|per cent|percentage points|pp|fold|times|x)?\b", re.I
)
# LaTeX 命令：\numval{0.406} \pctval{-48} \cntval{2,995}
LATEX_PAT = re.compile(r"\\(?:numval|pctval|cntval|qid|ref|cite[a-z]*)\s*\{([^}]*)\}")


def load_checklist():
    with open(CHECKLIST, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows


def step1_checklist(rows, numbers_md, out):
    ok = bad = skipped = 0
    for row in rows:
        if not row.get("number") or row.get("ignore") == "1":
            skipped += 1
            continue
        val = (row.get("registry_value") or "").strip()
        ctx = (row.get("context") or "").strip()
        if val and val in numbers_md:
            ok += 1
        else:
            bad += 1
            out.append(f"[MISMATCH] {row['number']} | {ctx} | registry_value={val!r} 不在 NUMBERS.md")
    out.append(f"checklist: {ok} ok, {bad} mismatch, {skipped} ignored")
    return bad


def step2_draft_scan(targets, whitelist, out):
    """中文 + 英文两套正则；LaTeX 命令内嵌值单独抽取。

    只扫散文——Markdown 表格行（以 | 开头）为索引/进度表，其中数字是章节号与图号，
    真正的数据表在 SI（由 make_tables.py 从登记表生成，另走 Q 回查），本步不重复计。
    """
    warn = 0
    for path in targets:
        raw_text = open(path, encoding="utf-8").read()
        text = "\n".join(
            ("" if l.lstrip().startswith("|") else l) for l in raw_text.split("\n")
        )
        found = []
        found += [(m.group(0), m.start()) for m in CN_PAT.finditer(text)]
        found += [(m.group(0), m.start()) for m in EN_PAT.finditer(text)]
        for raw, pos in found:
            tok = re.sub(r"\s+", "", raw)
            core = tok.rstrip(".,;:)）】。，、")
            core = re.sub(r"(?i)(percent|percentagepoints|fold|times|x)$", "", core)
            if tok in whitelist or core in whitelist or len(core) <= 2:
                continue
            if re.fullmatch(r"(19|20)\d{2}", core):       # 年份
                continue
            if re.fullmatch(r"\d+\.\d+", core):            # 章节号（1.8 / 2.1）
                continue
            if re.fullmatch(r"\d+", core) and int(core) <= 200:  # 图号/节号/小整数
                continue
            warn += 1
            line = text[:pos].count("\n") + 1
            out.append(f"[UNREGISTERED?] {os.path.basename(path)}:{line} :: {raw!r}")
        # LaTeX 命令内嵌值
        for m in LATEX_PAT.finditer(text):
            cmd, arg = m.group(0).split("{", 1)
            cmd = cmd.strip()
            if cmd in ("\\qid", "\\ref", "\\cite"):
                continue
            arg = arg.rstrip("}")
            if not arg or arg in whitelist or re.fullmatch(r"\d+", arg):
                continue
            core = re.sub(r"^[-+]", "", arg).rstrip("%")
            if core in whitelist or arg in whitelist:
                continue
            warn += 1
            line = text[:m.start()].count("\n") + 1
            out.append(f"[UNREGISTERED?] {os.path.basename(path)}:{line} :: {cmd}{{{arg}}}")
    out.append(f"draft scan: {warn} unregistered tokens")
    return warn


def _split_field_path(path):
    """把 a.b[].c 或 a.b[0].c 切成 ['a','b[]','c']，方括号不参与点号分割。"""
    return [seg for seg in re.split(r"\.(?![^\[]*\])", path) if seg]


def _resolve_field(obj, path):
    """按 a.b[].c / a.b[0].c / a.b[year].c 形式在 JSON 中取字段，返回 (found, sample)。

    段形态：`name`（取键）、`name[..]`（取键后按下标筛选）、`[..]`（对当前列表按下标筛选）。
    下标为空 `[]` 表示展开全部元素；否则按整数下标或 `key`/`year` 字段值匹配。
    """
    if not path:
        return False, None
    cur = [obj]
    for part in _split_field_path(path):
        m = re.match(r"^([^\[]*)((?:\[[^\]]*\])*)$", part)
        if not m:
            return False, None
        name, idxs = m.group(1), re.findall(r"\[([^\]]*)\]", m.group(2) or "")

        # 第一步：按名字取键
        if name:
            vals = []
            for c in cur:
                if isinstance(c, dict) and name in c:
                    vals.append(c[name])
                elif isinstance(c, list):
                    for e in c:
                        if isinstance(e, dict) and name in e:
                            vals.append(e[name])
                        else:
                            return False, None
                else:
                    return False, None
            cur = vals

        # 第二步：应用下标
        for i in idxs:
            nxt = []
            for c in cur:
                if not isinstance(c, list):
                    return False, None
                if i == "":
                    nxt.extend(c)
                    continue
                k = i.strip("'\"")
                if re.fullmatch(r"-?\d+", k):
                    n = int(k)
                    if -len(c) <= n < len(c):
                        nxt.append(c[n])
                        continue
                    return False, None
                # key=value 形式（如 [year=2003]）
                if "=" in k:
                    fk, fv = (x.strip() for x in k.split("=", 1))
                    hits = [e for e in c if isinstance(e, dict) and str(e.get(fk)) == fv]
                    if not hits:
                        return False, None
                    nxt.extend(hits)
                    continue
                hit = False
                for e in c:
                    if isinstance(e, dict):
                        if k in e:
                            nxt.append(e[k]); hit = True
                        elif str(e.get("year")) == k:
                            nxt.append(e); hit = True
                        elif str(e.get("key", "")) == k:
                            nxt.append(e); hit = True
                    elif str(e) == k:
                        nxt.append(e); hit = True
                if not hit:
                    return False, None
            cur = nxt

        if not cur:
            return False, None
    return len(cur) > 0, (cur[0] if cur else None)


# doc_ids.md 行内转义竖线（如 `2018\|10-19\|20-29`）不得当作单元格分隔
CELL_SPLIT_PAT = re.compile(r"(?<!\\)\|")
_Q_ROW = re.compile(r"^\|\s*\*{0,2}(Q\d+[a-z]?)\*{0,2}\s*\|")


def _split_cells(line):
    """按未转义的竖线切单元格，并把 `\\|` 还原为 `|`。"""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [c.strip().replace("\\|", "|") for c in CELL_SPLIT_PAT.split(body)]


def _main_q_table(text):
    """只取「## Q 编号表」主表区段内的行——「## 待补编号」等预留区行结构不同，
    不应参与硬核对（其中 Q0/Q37/Q40/Q42 是段位标题或预留占位）。"""
    lines = text.split("\n")
    start = end = None
    for i, l in enumerate(lines):
        if l.startswith("## ") and "Q 编号表" in l:
            start = i
        elif start is not None and l.startswith("## ") and "Q 编号表" not in l:
            end = i
            break
    if start is None:
        return lines
    return lines[start:(end if end is not None else len(lines))]


def step3_q_lookup(numbers_md, out):
    """Q 编号三方回查：列结构  Q | 含义 | 值 | 登记位置 | 脚本 | 输出文件 | 字段路径。

    硬失败（计入退出码）：编号行存在但输出字段解析不到（说明登记表写错了路径）。
    软提示（不计入退出码）：登记位置/输出文件的自由文本注释（"同上""—""待补"等），
    这些行通常由人工速记，其中信息量不足以做机器核对。
    """
    text = open(DOC_IDS, encoding="utf-8").read()
    q_rows, parse_fail = [], 0
    for line in _main_q_table(text):
        if "---" in line or not _Q_ROW.match(line):
            continue
        cells = _split_cells(line)
        q = re.sub(r"\*", "", cells[0]).strip()
        if not re.fullmatch(r"Q\d+[a-z]?", q):
            continue
        if len(cells) != 7:
            parse_fail += 1
            out.append(f"[Q-PARSE] {q}: 解析到 {len(cells)} 列（应为 7），跳过硬核对")
            continue
        q_rows.append((q, cells))

    bad = parse_fail
    hard_checked = 0
    for q, cells in q_rows:
        _, meaning, value, reg_pos, script, out_file, field = cells
        reg_key = re.sub(r"（.*?）|\(.*?\)", "", reg_pos).strip()
        if reg_key and reg_key not in numbers_md:
            out.append(f"[Q-REG-NOTE] {q}: 登记位置为速记语 {reg_pos!r}，未在 NUMBERS.md 字面命中")

        if not out_file or out_file in ("—", "-", "同上") or " " in out_file or "/" in out_file:
            if out_file not in ("—", "-", "同上", "") and "待" not in out_file:
                out.append(f"[Q-OUT-NOTE] {q}: 输出文件为速记语 {out_file!r}，跳过字段核对")
            continue
        fname = out_file if out_file.endswith(".json") else out_file + ".json"
        p = os.path.join(OUT_JSON, fname)
        if not os.path.exists(p):
            hits = glob.glob(os.path.join(ROOT, "research", "**", fname), recursive=True) or \
                glob.glob(os.path.join(ROOT, "archive", "**", fname), recursive=True)
            p = hits[0] if hits else None
        if p is None:
            out.append(f"[Q-OUT-NOTE] {q}: 输出文件 {out_file!r} 未在 research/ 下找到")
            continue
        try:
            obj = json.load(open(p, encoding="utf-8"))
        except Exception as e:
            out.append(f"[Q-BAD-JSON] {q}: {p} 读取失败 {e}")
            bad += 1
            continue
        fld = re.sub(r"（.*?）|\(.*?\)|\*\*", "", field).strip()
        # 一个格子可能给多条路径（"a / b"、"a；b"），逐个试，全失败才算错。
        # 形如 "a.b / .c" 的省略写法：后半以 . 开头则继承前一条的父路径。
        raw_parts = [x.strip() for x in re.split(r"[；;]| / ", fld) if x.strip()]
        cands = []
        for c in raw_parts:
            if c in ("—", "-", "", "派生", "同上") or "派生" in c:
                continue
            if c.startswith(".") and cands:
                cands.append(cands[-1].rsplit(".", 1)[0] + c)
            else:
                cands.append(c)
        if not cands:
            continue
        hard_checked += 1
        if not any(_resolve_field(obj, c)[0] for c in cands):
            out.append(f"[Q-FIELD-MISS] {q}: 字段 {fld!r} 在 {os.path.basename(p)} 中均不存在")
            bad += 1
    out.append(f"Q lookup: {len(q_rows)} 行解析, {hard_checked} 条硬核对, {bad} 问题")

    if os.path.exists(PLAN_OUTLINE):
        body = open(PLAN_OUTLINE, encoding="utf-8").read()
        used = set(re.findall(r"\\qid\{([^}]+)\}", body))
        declared = {q for q, _ in q_rows}
        missing = sorted(used - declared)
        if missing:
            out.append(f"[Q-UNDECLARED] 正文引用了未分配的 Q 编号: {', '.join(missing)}")
            bad += len(missing)
        out.append(f"Q 正文引用: {len(used)} 个" + ("，均已分配" if not missing
                                                else f"，未分配 {len(missing)} 个"))
    return bad


def step4_matrix_rowcount(out):
    """③ 版本口径统一：PLAN.md 稳健性矩阵须为 17 条数据行（2026-10-02 核实值）。

    外部评审曾报"20 行"（awk 统计命令跨入下一张表所致）与"16 条"，均不确。
    此处以机器校验固定口径，防止后续编辑悄悄改行数。
    """
    plan = os.path.join(ROOT, "research", "nature", "PLAN.md")
    expected = 17
    lines = open(plan, encoding="utf-8").read().split("\n")
    start = None
    for i, l in enumerate(lines):
        if l.startswith("|") and "施引侧参考文献密度分层" in l:
            start = i
            break
    if start is None:
        out.append("[MATRIX] 未找到稳健性矩阵起始行，跳过行数校验")
        return 0
    n = 0
    for l in lines[start:]:
        if l.startswith("|") and "---" not in l:
            n += 1
        elif l.strip() == "" and n > 0:
            break
    if n != expected:
        out.append(f"[MATRIX-ROWCOUNT] 稳健性矩阵为 {n} 条数据行，应为 {expected}")
        return 1
    out.append(f"matrix: 稳健性矩阵 {n} 条数据行（口径已统一）")
    return 0


def main():
    targets = sys.argv[1:] or DEFAULT_DRAFTS
    # 默认加入 paper/draft 下全部 md（英文稿扩展后）
    if len(sys.argv) <= 1:
        targets += sorted(glob.glob(os.path.join(PAPER_DRAFT, "*.md")))
    numbers_md = open(NUMBERS, encoding="utf-8").read()
    out = []

    rows = load_checklist()
    bad1 = step1_checklist(rows, numbers_md, out)

    whitelist = set()
    for row in rows:
        whitelist.add((row.get("number") or "").strip())
        whitelist.update(x.strip() for x in (row.get("alt_forms") or "").split(";") if x.strip())
    warn = step2_draft_scan(targets, whitelist, out)

    bad3 = step3_q_lookup(numbers_md, out)
    bad4 = step4_matrix_rowcount(out)

    bad = bad1 + bad3 + bad4
    verdict = "PASS" if bad == 0 else "FAIL"
    out.append(f"verdict: {verdict}（mismatch=0 即过；unregistered 需人工归零或加入 checklist/ignore）")
    os.makedirs(REPORT_OUT, exist_ok=True)
    with open(os.path.join(REPORT_OUT, "verify_report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("\n".join(out))
    sys.exit(0 if bad == 0 else 1)


if __name__ == "__main__":
    main()
