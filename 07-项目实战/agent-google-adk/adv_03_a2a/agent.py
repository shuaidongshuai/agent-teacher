"""进阶 03 · 消费端：通过 A2A 调用远程 Agent（RemoteA2aAgent）

学习目标：
  - 用 RemoteA2aAgent 把一个【远程】Agent 当成本地 sub_agent 使用
  - 对比关卡 04（sub_agents）：那是同进程内委派；这里是【跨进程/跨网络】委派
  - 理解 Agent Card：远程 Agent 的"名片"（能力描述），消费端靠它知道对方会什么

前置：先按 remote_server.py 的说明启动服务端（localhost:8001）。

运行消费端（另一个终端）：
  cd agent-google-adk
  adk run adv_03_a2a          # 问它 "帮我算 (23*17)+89"，会转交给远程 math_expert
  或 adk web 后选择 adv_03_a2a
"""

import os

from google.adk.agents import LlmAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")

# 指向远程服务端的 Agent Card（若 404，可换成 /.well-known/agent.json）
REMOTE_CARD_URL = "http://localhost:8001/.well-known/agent-card.json"

# 远程数学专家：构造时不联网，真正调用时才通过 A2A 请求远端
remote_math = RemoteA2aAgent(
    name="math_expert",
    description="远程数学专家（通过 A2A 协议调用，运行在另一个进程）。",
    agent_card=REMOTE_CARD_URL,
)

# 本地协调者：数学问题转交远程专家，其余自己回答
root_agent = LlmAgent(
    name="a2a_coordinator",
    model=MODEL,
    description="本地协调者，会把数学问题委派给远程 A2A 专家。",
    instruction=(
        "你是协调者。遇到需要计算的数学问题，就把它转交给 math_expert（远程专家）处理；"
        "其他闲聊或常识问题你自己回答。"
    ),
    sub_agents=[remote_math],
)
