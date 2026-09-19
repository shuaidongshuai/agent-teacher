"""编程式运行 capstone 研究助手（不依赖 adk web）。

演示如何用 ADK 的 Runner + SessionService 在自己的 Python 代码里驱动 Agent，
并把执行过程中每一步（哪个子 Agent 说了什么、调用了什么工具）打印出来——
这就是"可观测"的最小实现。

用法：
  1. 确保已配置好 Key（把 环境变量配置示例.txt 的内容写进 .env）
  2. python run_demo.py               # 用默认主题
     python run_demo.py "你的主题"     # 自定义主题
"""

import asyncio
import os
import sys

# 尽量加载 .env（若装了 python-dotenv）
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from research_assistant.agent import root_agent

APP_NAME = "research_assistant"
USER_ID = "demo_user"


def _has_credentials() -> bool:
    """粗略检查是否配置了可用的模型凭证。"""
    if os.environ.get("GOOGLE_API_KEY"):
        return True
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE":
        return bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    return False


async def run(topic: str) -> None:
    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
    session = await session_service.create_session(app_name=APP_NAME, user_id=USER_ID)

    print(f"\n=== 研究主题：{topic} ===\n")
    message = types.Content(role="user", parts=[types.Part(text=topic)])

    async for event in runner.run_async(
        user_id=USER_ID, session_id=session.id, new_message=message
    ):
        author = event.author or "?"
        # 打印每个子 Agent 产出的文本，直观看到流水线推进
        if event.content and event.content.parts:
            for part in event.content.parts:
                if getattr(part, "text", None):
                    snippet = part.text.strip()
                    if snippet:
                        print(f"[{author}] {snippet}\n")
                if getattr(part, "function_call", None):
                    fc = part.function_call
                    print(f"[{author}] → 调用工具 {fc.name}({dict(fc.args or {})})")

    # 从最终会话状态里取关键产物
    final = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session.id
    )
    path = final.state.get("report_path")
    if path:
        print(f"\n✅ 报告已保存到：{path}")


def main() -> None:
    topic = sys.argv[1] if len(sys.argv) > 1 else "检索增强生成（RAG）技术"
    if not _has_credentials():
        print(
            "⚠️ 未检测到模型凭证。请先把「环境变量配置示例.txt」的内容复制成 .env 并填入 "
            "GOOGLE_API_KEY（AI Studio 免费获取：https://aistudio.google.com/apikey）。\n"
            "配置好后重新运行： python run_demo.py"
        )
        return
    asyncio.run(run(topic))


if __name__ == "__main__":
    main()
