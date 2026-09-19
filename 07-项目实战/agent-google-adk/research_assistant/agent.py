"""Capstone：AI 深度研究助手（组合 ADK 的核心能力）

这一个 root_agent 把前面 11 个关卡的能力串成一条完整流水线：

  [规划] planner ────────────── 结构化输出 output_schema（关卡09）
     │                          + 输入护栏回调（关卡10）
  [并行研究] ParallelAgent ───── 并行工作流（关卡07）
     ├ researcher_1            + 函数工具 web_search（关卡02）
     ├ researcher_2            + 工具日志回调（关卡10）
     └ researcher_3
  [撰写] writer ─────────────── 顺序工作流 + state 传递（关卡06）
     │
  [评审循环] LoopAgent ───────── 循环 + escalate 退出（关卡08）
     ├ critic (可调用 exit_loop)
     └ reviser
     │
  [定稿] finalizer ──────────── 函数工具 save_report 落盘

整条链由外层 SequentialAgent 编排（关卡06）。

运行：
  adk web            # 然后在浏览器选择 research_assistant
  adk run research_assistant
  或编程式运行： python run_demo.py  （见项目根目录）
"""

import os

from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent

from .callbacks import input_guardrail, tool_logger
from .schemas import ResearchPlan
from .tools import exit_loop, save_report, web_search

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")

# 1) 规划：把主题拆成 3 个子问题，结构化输出到 state["plan"]
planner = LlmAgent(
    name="planner",
    model=MODEL,
    description="把研究主题拆解成结构化研究计划。",
    instruction=(
        "你是研究规划师。根据用户给的主题，拆出正好 3 个互不重叠、值得分别研究的子问题，"
        "并判断目标读者。严格按结构输出。"
    ),
    output_schema=ResearchPlan,
    output_key="plan",
    before_model_callback=input_guardrail,  # 输入护栏
)


def _researcher(idx: int) -> LlmAgent:
    """构造第 idx 个并行研究员，各写各的 state key，互不覆盖。"""
    return LlmAgent(
        name=f"researcher_{idx}",
        model=MODEL,
        description=f"研究计划中的第 {idx} 个子问题。",
        instruction=(
            f"这是研究计划：\n{{plan}}\n\n"
            f"请只针对其中【第 {idx} 个子问题】展开研究。"
            "调用 web_search 检索资料，然后用 4~6 句话总结你的发现。"
        ),
        tools=[web_search],
        output_key=f"finding_{idx}",
        before_tool_callback=tool_logger,  # 工具审计日志
    )


# 2) 并行研究：3 个研究员同时干活
parallel_research = ParallelAgent(
    name="parallel_research",
    description="并行研究计划中的 3 个子问题。",
    sub_agents=[_researcher(1), _researcher(2), _researcher(3)],
)

# 3) 撰写：把计划 + 三份研究发现汇编成初稿
writer = LlmAgent(
    name="writer",
    model=MODEL,
    description="根据研究发现撰写报告初稿。",
    instruction=(
        "根据研究计划和三份发现，写一篇结构清晰的中文研究报告初稿"
        "（含引言、分小节论述、结论）。面向计划里指定的读者。\n\n"
        "计划：\n{plan}\n\n发现1：\n{finding_1}\n\n发现2：\n{finding_2}\n\n发现3：\n{finding_3}"
    ),
    output_key="draft",
)

# 4) 评审循环：critic 挑刺（够好就 exit_loop），reviser 改稿，最多 2 轮
critic = LlmAgent(
    name="critic",
    model=MODEL,
    description="评审报告并给出改进意见。",
    instruction=(
        "评审这份报告草稿：\n----\n{draft}\n----\n"
        "若已足够清晰、完整、准确，调用 exit_loop 结束；"
        "否则不要调用工具，只列出 1~3 条具体修改建议。"
    ),
    tools=[exit_loop],
    output_key="critique",
)

reviser = LlmAgent(
    name="reviser",
    model=MODEL,
    description="按评审意见改进报告。",
    instruction=(
        "原稿：\n----\n{draft}\n----\n意见：\n----\n{critique}\n----\n"
        "据此改进，只输出改好后的完整报告。"
    ),
    output_key="draft",
)

refine_loop = LoopAgent(
    name="refine_loop",
    description="评审-修改循环，打磨报告质量。",
    max_iterations=2,
    sub_agents=[critic, reviser],
)

# 5) 定稿：保存到本地文件
finalizer = LlmAgent(
    name="finalizer",
    model=MODEL,
    description="定稿并保存报告。",
    instruction=(
        "这是最终报告：\n----\n{draft}\n----\n"
        "给它拟一个简短标题，然后调用 save_report 保存（title=标题, content=报告全文）。"
        "最后用一句话告诉用户报告已生成及保存位置。"
    ),
    tools=[save_report],
    output_key="final_report",
)

# 顶层编排：规划 → 并行研究 → 撰写 → 评审循环 → 定稿
root_agent = SequentialAgent(
    name="research_assistant",
    description="输入一个主题，自动完成规划、并行研究、撰写、评审打磨与定稿的研究助手。",
    sub_agents=[planner, parallel_research, writer, refine_loop, finalizer],
)
