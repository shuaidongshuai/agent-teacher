"""关卡 08：LoopAgent 循环工作流 + 用 escalate 主动退出

学习目标：
  - 用 LoopAgent 让"评审 → 修改"反复迭代，直到满意
  - 用 max_iterations 兜底，防止死循环
  - 用工具里 tool_context.actions.escalate = True 主动跳出循环
    （这是"达到目标就停"的标准写法）

流程：先写初稿(在循环外) → 进入循环[评审员挑刺 → 修改员改稿]，
     评审员觉得够好了就调用 exit_loop 结束。

运行：adk run s08_loop   或   adk web 后选择本关卡
"""

import os

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.tools.tool_context import ToolContext

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")


def exit_loop(tool_context: ToolContext) -> dict:
    """当稿件质量已达标、无需再修改时调用本工具，用于结束修订循环。"""
    # 把 escalate 置为 True，LoopAgent 检测到后会停止循环
    tool_context.actions.escalate = True
    return {"status": "approved", "message": "稿件已达标，结束修订。"}


# 循环外：先产出初稿，写入 state["draft"]
initial_writer = LlmAgent(
    name="initial_writer",
    model=MODEL,
    description="根据主题写第一版初稿。",
    instruction="根据用户主题，写一段 120 字左右的中文介绍作为初稿。",
    output_key="draft",
)

# 循环内步骤 1：评审员。够好就调用 exit_loop，否则只输出改进意见
critic = LlmAgent(
    name="critic",
    model=MODEL,
    description="评审当前稿件并给出改进意见。",
    instruction=(
        "这是当前稿件：\n----\n{draft}\n----\n"
        "如果它已经清晰、准确、无明显问题，就调用 exit_loop 工具结束。"
        "否则不要调用工具，只输出 1~3 条具体、可执行的修改建议。"
    ),
    tools=[exit_loop],
    output_key="critique",
)

# 循环内步骤 2：修改员，按意见改稿，覆盖 state["draft"]
reviser = LlmAgent(
    name="reviser",
    model=MODEL,
    description="根据评审意见修改稿件。",
    instruction=(
        "原稿：\n----\n{draft}\n----\n"
        "评审意见：\n----\n{critique}\n----\n"
        "请据此改进，只输出改好后的完整新稿。"
    ),
    output_key="draft",  # 覆盖旧稿，供下一轮评审
)

# 循环体：最多 3 轮「评审 → 修改」
refine_loop = LoopAgent(
    name="refine_loop",
    description="反复评审并修改稿件，直到达标或达到最大轮数。",
    max_iterations=3,
    sub_agents=[critic, reviser],
)

# 整体：初稿 → 进入修订循环
root_agent = SequentialAgent(
    name="iterative_writer",
    description="先写初稿，再进入评审-修改循环打磨。",
    sub_agents=[initial_writer, refine_loop],
)
