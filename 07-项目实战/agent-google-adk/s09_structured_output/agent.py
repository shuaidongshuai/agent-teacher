"""关卡 09：结构化输出（output_schema + Pydantic）

学习目标：
  - 用 Pydantic 模型约束 Agent 的输出格式，得到稳定可解析的 JSON
  - 结果会以该结构写入 state[output_key]，方便后续程序直接使用
  - 重要约束：一旦设了 output_schema，这个 Agent 就【不能再用工具、也不能委派】，
    它只负责"把输入整理成指定结构"。

场景：从一段用户评价里抽取结构化信息（情感、评分、关键词、要不要跟进）。

运行：adk run s09_structured_output   或   adk web 后选择本关卡
（粘贴一段商品/服务评价即可）
"""

import os

from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")


class ReviewAnalysis(BaseModel):
    """一条用户评价的结构化分析结果。"""

    sentiment: str = Field(description="情感倾向，取值：正面 / 中性 / 负面")
    score: int = Field(description="综合评分，1~5 的整数", ge=1, le=5)
    keywords: list[str] = Field(description="评价中的关键词，2~5 个")
    need_followup: bool = Field(description="是否需要人工跟进（如强烈不满/投诉）")
    summary: str = Field(description="一句话中文总结")


root_agent = LlmAgent(
    name="review_analyzer",
    model=MODEL,
    description="把用户评价抽取成结构化 JSON。",
    instruction=(
        "你是评价分析器。阅读用户提供的一段评价，"
        "严格按给定的结构输出分析结果，不要输出多余文字。"
    ),
    # 设定输出结构；ADK 会要求模型产出符合该 schema 的 JSON
    output_schema=ReviewAnalysis,
    output_key="analysis",
)
