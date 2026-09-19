"""关卡 05：把 Agent 当工具用（AgentTool）

学习目标：
  - 用 AgentTool 把一个子 Agent 包装成"工具"，供主 Agent 调用
  - 和关卡 04 的区别：
      sub_agents  → 委派：控制权整个交给子 Agent
      AgentTool   → 调用：主 Agent 叫子 Agent 干一件事，拿回结果后自己继续说
  - 典型用途：翻译器、摘要器、格式化器这类"被随时调用的能力"

运行：adk run s05_agent_as_tool   或   adk web 后选择本关卡
"""

import os

from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")

# 一个专职"英译中"的子 Agent
translator_agent = Agent(
    name="translator",
    model=MODEL,
    description="把任意英文文本翻译成地道中文。",
    instruction="你是专业翻译。把收到的英文翻译成通顺、自然的中文，只输出译文。",
)

# 一个专职"缩写成一句话"的子 Agent
summarizer_agent = Agent(
    name="summarizer",
    model=MODEL,
    description="把一段较长文本压缩成一句话摘要。",
    instruction="你是摘要专家。把输入内容浓缩成不超过 40 字的一句话中文摘要。",
)

# 主 Agent：把上面两个 Agent 当成工具来调度
root_agent = Agent(
    name="writing_helper",
    model=MODEL,
    description="写作助手：可翻译、可摘要，并把结果整合润色后交给用户。",
    instruction=(
        "你是写作助手。"
        "遇到英文内容需要翻译时，调用 translator 工具；"
        "需要一句话概括时，调用 summarizer 工具。"
        "可以先翻译再摘要，最后用中文把结果整理好回复用户。"
    ),
    # 用 AgentTool 包装后放进 tools —— 调用完会把控制权还给主 Agent
    tools=[
        AgentTool(agent=translator_agent),
        AgentTool(agent=summarizer_agent),
    ],
)
