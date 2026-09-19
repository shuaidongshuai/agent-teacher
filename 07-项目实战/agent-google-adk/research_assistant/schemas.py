"""capstone 的结构化数据模型（Pydantic）。"""

from pydantic import BaseModel, Field


class ResearchPlan(BaseModel):
    """一次研究任务的计划：把用户主题拆成几个可并行研究的子问题。"""

    topic: str = Field(description="用户想研究的总主题")
    subtopics: list[str] = Field(
        description="拆解出的子问题列表，正好 3 个，彼此尽量不重叠",
        min_length=3,
        max_length=3,
    )
    audience: str = Field(description="报告的目标读者，如 '初学者' / '技术决策者'")
