"""关卡 01：最小 LlmAgent —— 一个"会说话的 Agent"

学习目标：
  - 理解 ADK 里最基本的单元 LlmAgent（别名 Agent）
  - 知道 name / model / description / instruction 各自的作用

运行：
  1. 在本文件夹或上级目录放好 .env（含 GOOGLE_API_KEY）
  2. 回到 agent-google-adk 目录执行：  adk web
     然后在浏览器里选中 s01_llm_agent 对话
  或：  adk run s01_llm_agent
"""

import os

from google.adk.agents import Agent  # Agent 就是 LlmAgent 的别名

# 各关卡统一从环境变量读模型名，缺省用 gemini-2.5-flash
MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")

# root_agent 是 ADK 约定的入口变量名，adk web / adk run 会自动找它
root_agent = Agent(
    # name：Agent 的唯一标识，多智能体里用于互相委派，必须是合法标识符
    name="hello_agent",
    # model：驱动这个 Agent 的大模型
    model=MODEL,
    # description：一句话描述"我能干什么"。在多智能体里，父 Agent 靠它决定要不要把任务交给我
    description="一个友好的通用助手，能闲聊、答疑、做简单解释。",
    # instruction：系统提示词，决定 Agent 的人设与行为准则
    instruction=(
        "你是一个友好、简洁的中文助手。"
        "回答要口语化、抓重点，必要时用要点列出。"
        "如果用户问的问题需要实时数据或工具，你没有工具，就如实说明。"
    ),
)
