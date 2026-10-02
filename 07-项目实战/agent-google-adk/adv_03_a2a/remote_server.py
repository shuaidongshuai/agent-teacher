"""进阶 03 · 服务端：把一个 Agent 暴露成 A2A 服务

A2A（Agent-to-Agent）是一个开放协议，让不同进程/机器/框架的 Agent 互相调用。
这里用 to_a2a() 把一个"数学专家"Agent 包装成标准的 A2A 服务（一个 Starlette 应用）。

先起服务端（单独一个终端）：
  cd agent-google-adk
  uvicorn adv_03_a2a.remote_server:a2a_app --host localhost --port 8001

起来后，它的 Agent Card 在：
  http://localhost:8001/.well-known/agent-card.json
消费端（adv_03_a2a/agent.py）就靠这个地址来远程调用它。
"""

import os
from pathlib import Path

# 关键：uvicorn 直接 import 本模块跑服务，不经过 adk CLI，
# 不会自动加载 .env。所以这里主动读一次项目根目录的 .env，
# 否则 GOOGLE_GENAI_USE_VERTEXAI / API Key 等配置进不来，会报"找不到 api_key"。
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from google.adk.agents import LlmAgent
from google.adk.a2a.utils.agent_to_a2a import to_a2a

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")

# 被远程暴露的专家 Agent
math_expert = LlmAgent(
    name="math_expert",
    model=MODEL,
    description="擅长四则运算、单位换算和简单应用题的数学专家。",
    instruction="你是数学专家。一步步算清楚，给出最终答案，必要时展示关键步骤。",
)

# to_a2a：把 Agent 变成 A2A 服务（Starlette app）。host/port 用于生成 Agent Card 里的地址。
a2a_app = to_a2a(math_expert, host="localhost", port=8001)
