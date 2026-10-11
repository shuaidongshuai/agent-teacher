"""
05_short_term_memory.py —— 短期记忆 / 单会话记忆（LangChain v1）

本节目标：让 Agent 在「同一个会话里」记住上文，而不用你手动拼 history。

核心机制：checkpointer（检查点）+ thread_id。
- create_agent 底层是一张 LangGraph 图；给它一个 checkpointer，
  每一步的状态（含完整消息历史）就会被持久化。
- 调用时用 config 传 thread_id，同一个 thread_id = 同一个会话。
- 不同 thread_id 之间天然隔离，互不串台。

对应 README「短期记忆」一节。

运行：python 05_short_term_memory.py
"""

from __future__ import annotations

from common import get_model, require_key
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver


def build_agent():
    # InMemorySaver：进程内内存版 checkpointer，适合开发/演示。
    # 生产换成 langgraph.checkpoint.postgres.PostgresSaver 即可持久到数据库。
    return create_agent(
        model=get_model(),
        tools=[],
        system_prompt="你是一个会记住对话的助手，回答简短。",
        checkpointer=InMemorySaver(),
    )


def say(agent, text: str, thread_id: str) -> str:
    # 这里不是真实的线程id，只是一个tag标识
    config = {"configurable": {"thread_id": thread_id}}
    out = agent.invoke({"messages": [{"role": "user", "content": text}]}, config)
    return out["messages"][-1].text


def demo_same_thread_remembers() -> None:
    """同一 thread：第二轮能用到第一轮说过的信息。"""
    agent = build_agent()
    print("[t1-1]", say(agent, "我叫小明，我最喜欢的颜色是蓝色。", thread_id="user-A"))
    # 没有再提名字/颜色，靠 checkpointer 自动带出历史。
    print("[t1-2]", say(agent, "我叫什么？喜欢什么颜色？", thread_id="user-A"))


def demo_different_thread_isolated() -> None:
    """不同 thread：换一个 thread_id，之前的信息不会串过来。"""
    agent = build_agent()
    say(agent, "记住：今天的暗号是 7788。", thread_id="user-A")
    print("[t-A]", say(agent, "暗号是多少？", thread_id="user-A"))
    print("[t-B]", say(agent, "暗号是多少？", thread_id="user-B"))  # B 不知道


if __name__ == "__main__":
    if not require_key():
        raise SystemExit(0)
    demo_same_thread_remembers()
    # demo_different_thread_isolated()
