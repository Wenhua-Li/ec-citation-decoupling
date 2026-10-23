# -*- coding: utf-8 -*-
"""B 广度层锚源字典与窗口常量（单一来源，2026-10-18）。

纪律：刊名→sid 经 display_name+ISSN+近年计数三重核验（control_theory 盲选教训）；
2026-10-17 健康扫查（out/source_health.json）后三处死档换新：
  PRB 旧档 S4210174675（近年 0 篇）-> S4210237713（ISSN 2469-9950 系，2021-23 计 14,892）
  BMJ 停更印刷档 S4393911389 -> 电子版 S4393917726（ISSN 1756-1833，9,474）
  NEJM 历史同名刊 S4210202533（1812 年刊，27 works）-> S62468778（ISSN 0028-4793，3,266）
econ/psych/math 沿用 W1 已采集刊源；business 含 W1 已核 Management Science S33323087。
"""
S = {
    "economics": ["S23254222", "S203860005", "S95323914", "S95464858", "S88935262"],
    "psychology": ["S58854535", "S62013203", "S88198767", "S35223124"],
    "mathematics": ["S45918994", "S98347115", "S130224168", "S171170845"],
    "physics": ["S24807848", "S4210237713", "S105243760", "S164566984"],
    "materials": ["S99352657", "S64016596", "S143846845", "S135204980"],
    "chemistry": ["S111155417", "S67393510", "S184645833", "S191963794"],
    "chemical_engineering": ["S147177414", "S33892871", "S202680183"],
    "biology": ["S110447773", "S154343897", "S127916151", "S134668137"],
    "medicine": ["S49861241", "S172573765", "S4393917726", "S62468778"],
    "computer_science": ["S118992489", "S199944782", "S103482838"],
    "electrical_engineering": ["S68686220", "S4502562", "S168680287"],
    "neuroscience": ["S45757444", "S2298632", "S5555990"],
    "business": ["S117778295", "S143668711", "S206124708", "S33323087"],
    "sociology": ["S157620343", "S122471516", "S130611943"],
    "political_science": ["S176007004", "S90314269", "S95650557"],
    "ecology": ["S80967739", "S35917800", "S74970393"],
    "earth_science": ["S119230507", "S56162041", "S32973720"],
    "statistics": ["S119757635", "S4394736638", "S172180718"],
    "biomedical_engineering": ["S163807576", "S5240358", "S173145877"],
    "mechanical_engineering": ["S128368299", "S72716621", "S154368109"],
}

# 端点窗对（冻结，NUMBERS 2026-10-18）：早窗 2011–2013 对现代窗 2021–2023
WINDOWS = {"early": ("2011-01-01", "2013-12-31"), "modern": ("2021-01-01", "2023-12-31")}

# 采集池（v3 §5）：16 双 PASS 方向 + 4 存活单向
DOUBLE_PAIRS = [("physics", "materials"), ("chemistry", "chemical_engineering"),
                ("biology", "medicine"), ("computer_science", "electrical_engineering"),
                ("neuroscience", "psychology"), ("economics", "business"),
                ("sociology", "political_science"), ("statistics", "computer_science")]
SINGLE_DIRS = [("ecology", "earth_science"), ("biomedical_engineering", "medicine"),
               ("mathematics", "physics"), ("mechanical_engineering", "materials")]
