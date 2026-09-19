"""关卡 03：内置工具 google_search —— 让 Agent 会"上网查"

学习目标：
  - 使用 ADK 自带的 google_search 内置工具
  - 记住一个重要约束：内置工具（google_search / 代码执行等）在同一个 Agent 里
    通常要"独占"，不能和自定义函数工具混用（会报错）。
    需要混用时，用关卡 05 的 AgentTool 把它包成子 Agent。

注意：google_search 需要 Gemini 模型 + 真实联网，离线跑不出结果。

运行：adk run s03_builtin_search   或   adk web 后选择本关卡
"""

import os

from google.adk.agents import Agent
from google.adk.tools import google_search  # 内置的 Google 搜索工具

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")

root_agent = Agent(
    name="search_agent",
    model=MODEL,
    description="能用 Google 搜索回答时事、最新信息类问题的助手。",
    instruction=(
        "你是一个可以联网搜索的助手。"
        "当用户的问题涉及实时/最新信息（新闻、价格、版本号等），先用 google_search 搜索，"
        "再基于搜索结果回答，并简要说明信息来源。"
    ),
    # 内置工具单独使用，不要再往 tools 里加别的函数工具
    tools=[google_search],
)
