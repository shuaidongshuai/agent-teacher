"""进阶 05：可生产级的本地 Skill 加载 + 检索（google.adk.skills）

学习目标：
  - 用 list_skills_in_dir 只加载 L1(name+desc)，正文(L2)命中时才懒加载，做**可扩展检索**（skill 上千也不崩）
  - 掌握"检索-再-呈现"与"两段式渐进披露"这两个生产要点

生产级设计（见 skill_index.py）：
  1. 不把全量目录塞进 prompt —— 只在需要时通过工具检索 **top-k**；
  2. **两段式工具**：
       search_skills(query) → 只返回 top-k 的 name+desc（L1 发现层）
       load_skill(name)     → 命中后才取该技能的完整 instructions（L2 执行层）
  3. 索引启动时构建一次；向量检索(Gemini embeddings)可选，离线自动降级关键词。

可选开关（环境变量）：
  ADK_SKILL_EMBEDDING=1   启用向量检索（需模型凭证），否则关键词兜底
  ADK_SKILL_TOPK=5        每次检索返回的候选数

运行：
  - 离线看加载+检索（无需 Key）：  python adv_05_skills/demo.py "帮我写 git commit"
  - 作为 Agent：  adk run adv_05_skills   或   adk web 后选择本关卡
"""

import os
from pathlib import Path

from google.adk.agents import LlmAgent

from .skill_index import SkillIndex

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")
USE_EMBEDDING = os.environ.get("ADK_SKILL_EMBEDDING") == "1"
TOP_K = int(os.environ.get("ADK_SKILL_TOPK", "5"))

# 启动时构建一次索引（L1 常驻；向量命中缓存则不重算）
INDEX = SkillIndex(Path(__file__).parent / "skills", use_embeddings=USE_EMBEDDING)


def search_skills(query: str) -> dict:
    """检索与用户任务最相关的本地技能，只返回候选的名称与描述（不含正文）。

    Args:
        query: 用户想做的事，如 "写 git 提交信息"、"解释 SQL"。
    """
    hits = INDEX.search(query, top_k=TOP_K)
    return {
        "status": "ok" if hits else "none",
        "mode": INDEX.mode,  # embedding / keyword
        "candidates": [{"name": s.name, "description": s.description} for s in hits],
    }


def load_skill(name: str) -> dict:
    """按名称取出某个技能的完整执行说明（instructions）——命中时才从磁盘读(L2)。

    Args:
        name: search_skills 返回的候选之一的 name。
    """
    s = INDEX.load_body(name)
    if not s:
        return {"status": "not_found", "message": f"没有名为 {name} 的技能"}
    return {"status": "ok", "name": s.name, "instructions": s.instructions}


root_agent = LlmAgent(
    name="skill_aware_agent",
    model=MODEL,
    description="会先检索本地技能库、命中就照技能说明执行的助手。",
    instruction=(
        "你是研发助手。处理用户任务时按两步走：\n"
        "1. 先调用 search_skills 检索候选技能（只会返回名称+描述）；\n"
        "2. 若有合适的，调用 load_skill 取它的完整步骤，然后严格照做，并说明用了哪个技能；\n"
        "   若没有合适的（status=none 或候选都不相关），按你自己的常规能力回答。\n"
        "重要：技能库可能非常大，**不要假设你知道全部技能**，一律通过 search_skills 去发现。"
    ),
    tools=[search_skills, load_skill],
)
