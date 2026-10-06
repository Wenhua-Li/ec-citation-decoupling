"""ecdomain：EC / 非EC 领域打标子系统（python -m ecdomain）。

四层判定，标签落在主库新表 paper_domain（一篇一行，不删不改 papers）：
  tier='venue'  纯EC刊源直接判 EC（venue_tier 表驱动，用户核定）
  tier='rule'   规则层（标题/摘要/受控词正则，双向：auto-EC 与 auto-非EC）
  tier='llm'    MiniMax LLM 判定（规则层未决论文，JSONL 缓存可续跑）
  tier='llm2'   二次复核模型（低置信 / 与规则矛盾样本）
  tier='human'  人工复核（金标准校准 + 分歧队列）
"""
__version__ = "0.1.0"

LABEL_EC = "EC"
LABEL_NON = "NON_EC"

# venue 分层取值
TIER_A = "A_pure_ec"
TIER_B = "B_ci_broad"
TIER_C = "C_mixed_appl"
TIER_NAMES = {TIER_A: "A_纯EC", TIER_B: "B_CI大类", TIER_C: "C_混合应用"}
