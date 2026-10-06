"""清洗规则：噪声分类、标题规范化、去重打分、质量标签。

规则目录（首条命中即分类，标题均先小写+空白折叠）：

  retraction_notice  R1  撤稿/更正通知（标题前缀 retract/errat/withdraw/corrigend/correction 等）
  editorial          E1  标题以 editorial / guest editorial 开头
                     E2  标题含 editorial board / editor's remarks / editor-in-chief / masthead 等
                     E3  标题含 "special issue" 且有佐证（无摘要/无关键词/参考文献≤1/以 introduction to 开头）
  front_matter       F1  规范化标题等于通用短题（preface, foreword, welcome, contents 等）
                         或以 acknowledg / in memoriam / obituary 开头
                     F2  标题含 "proceedings of" 或以 program / abstracts of 开头（论文集前言）
                     F3  标题含 front/back matter / call for papers / announcement 等
  discussion         D1  标题以 comment on / reply to / response to / discussion 等开头（评论与回复）

质量标签（保留记录）：no_abstract / no_doi / no_keywords / no_authors / short_paper。
"""
import re

# ---------------------------------------------------------------------------
# 噪声分类
# ---------------------------------------------------------------------------

_STARTSWITH_ANY = [
    ("retraction_notice", "R1", ("retraction", "retracted", "withdrawn", "withdrawal",
                                 "erratum", "errata", "corrigendum", "correction")),
    ("editorial", "E1", ("editorial", "guest editorial")),
    ("discussion", "D1", ("comment on", "comments on", "reply to", "response to",
                          "reply", "discussion", "rejoinder")),
]
_CONTAINS_ANY = [
    ("retraction_notice", "R1", ("withdrawal notice",)),
    ("editorial", "E2", ("editorial board", "editor's remarks", "editor-in-chief",
                         "editor in chief", "masthead", "message from the editor",
                         "letter from the editor")),
    ("front_matter", "F2", ("proceedings of",)),
    ("front_matter", "F3", ("front matter", "back matter", "title page",
                            "call for papers", "announcement", "publisher's note",
                            "guide for authors", "instructions for authors",
                            "author guidelines", "calendar of", "table of contents",
                            "list of reviewers")),
]
# F1：规范化标题（小写、仅字母数字）等于这些词即视为通用短题
_GENERIC_TITLES = {
    "preface", "foreword", "welcome", "contents", "authorindex", "subjectindex",
    "reviewers", "acknowledgments", "acknowledgements", "acknowledgment",
    "acknowledgement", "organizingcommittee", "programcommittee", "committee",
    "editorialboard", "cover", "newsandviews", "news", "frontmatter", "backmatter",
    "titlepage", "introduction", "openingremarks", "closingremarks", "keynote",
    "prefacetothefirstedition", "messagefromtheeditor",
}
_GENERIC_STARTS = ("acknowledg", "inmemoriam", "obituary", "foreword", "preface", "welcome")
# F2 前缀（标题以这些词开头）
_F2_STARTS = ("proceedings", "program", "abstracts of", "abstracts")
_F3_STARTS = ("announcement", "news", "calendar", "cover", "comment from the editor")


def _norm(title):
    return " ".join(str(title or "").lower().split())


def _alnum(title):
    return re.sub(r"[^a-z0-9]", "", str(title or "").lower())


def classify_noise(rec, terms):
    """返回 (类别, 规则号) 或 None（core）。terms 为该记录解析出的关键词列表。"""
    title = _norm(rec.get("title"))
    if not title:
        return None
    for cls, rid, prefixes in _STARTSWITH_ANY:
        if title.startswith(prefixes):
            return cls, rid
    for cls, rid, needles in _CONTAINS_ANY:
        if any(n in title for n in needles):
            return cls, rid
    alnum = _alnum(title)
    if alnum in _GENERIC_TITLES or alnum.startswith(_GENERIC_STARTS):
        return "front_matter", "F1"
    if title.startswith(_F2_STARTS):
        return "front_matter", "F2"
    if title.startswith(_F3_STARTS):
        return "front_matter", "F3"
    # E3：含 special issue 且有佐证，避免误伤题名含 Special issue 的正经文章
    if "special issue" in title and (
            not rec.get("abstract")
            or not terms
            or (rec.get("num_references") or 0) <= 1
            or title.startswith("introduction to")):
        return "editorial", "E3"
    return None


# ---------------------------------------------------------------------------
# 去重
# ---------------------------------------------------------------------------

def normalize_title(title):
    """去重分组用标题键：小写、仅字母数字。"""
    return _alnum(title)


TITLE_MIN_LEN = 25  # 短于此的规范化标题不参与同题去重（各会议各有 Preface 等通用短题）


def completeness_key(rec, n_terms=0):
    """记录完整度排序键（越大越好）。平手时调用方以 accession_no 升序决出。"""
    return (
        1 if rec.get("abstract") else 0,
        len(rec.get("abstract") or ""),
        1 if rec.get("authors_raw") else 0,
        1 if n_terms else 0,
        1 if rec.get("doi") else 0,
        rec.get("num_references") or 0,
    )


# ---------------------------------------------------------------------------
# 质量标签（保留记录的缺失字段提示）
# ---------------------------------------------------------------------------

def quality_flags(rec, terms):
    flags = []
    if not rec.get("abstract"):
        flags.append("no_abstract")
    if not rec.get("doi"):
        flags.append("no_doi")
    if not terms:
        flags.append("no_keywords")
    if not rec.get("authors_raw"):
        flags.append("no_authors")
    if not rec.get("article_number") and _page_span(rec.get("pages")) is not None \
            and _page_span(rec.get("pages")) <= 2:
        flags.append("short_paper")
    return flags


def _page_span(pages):
    """'1458-1462' -> 5；'e12345'/单页/无法解析 -> None。"""
    if not pages:
        return None
    m = re.match(r"^([0-9]+)\s*[-–]\s*([0-9]+)$", str(pages).strip())
    if m:
        return int(m.group(2)) - int(m.group(1)) + 1
    return None
