"""
08_advanced.py —— 高级功能与适用场景（LangChain v1）

本节目标：了解几个「从 Demo 走向生产」时真正用得上的高级能力，以及它们各自的场景。

涵盖：
  1. 结构化输出 structured output —— 让 Agent 直接吐出校验过的对象（抽取/分类/表单）
  2. 流式 streaming           —— 边执行边产出事件（前端实时、排障）
  3. 自定义中间件 middleware    —— 在 Agent 循环各环节插钩子（日志/护栏/路由）
  4. 人工介入 HITL            —— 关键动作前暂停等人确认（高风险操作，交互式真实演示）

（「多模型切换」原在本文件，已拆成独立的 09_multi_provider.py——它属于「模型层」，
和这里「Agent 执行层」的几项不是一类。）

对应 README「高级功能与适用场景」一节。

运行：python 08_advanced.py
"""

from __future__ import annotations

from typing import Any

from common import get_model, require_key
from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, before_model
from langchain.agents.structured_output import ToolStrategy
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import BaseModel, Field


# ---- 1. 结构化输出 ----
class ContactInfo(BaseModel):
    """从文本中抽取的联系人信息。"""

    name: str = Field(description="姓名")
    email: str = Field(description="邮箱")
    phone: str = Field(description="电话")


def demo_structured_output() -> None:
    """response_format：Agent 直接返回校验过的对象，省去自己解析 JSON。

    场景：信息抽取、意图分类、生成表单/工单。v1 里结构化输出在主循环内生成，
    通常不额外多花一次 LLM 调用。

    关于策略：response_format 直接传 Pydantic 模型时，会按 provider 能力自动选策略
    （AutoStrategy）——支持原生结构化输出的厂商走 ProviderStrategy。但各家对「原生 JSON
    模式」的实现参差，个别模型（如部分 Gemini 版本）可能返回无法解析的内容而报错。
    这里显式用 ToolStrategy：让模型以「调用一个工具」的方式交出结构化对象，provider 无关、
    最稳。想体验原生策略可改成 response_format=ContactInfo。
    """
    agent = create_agent(
        model=get_model(), tools=[], response_format=ToolStrategy(ContactInfo)
    )
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "从这段话抽取联系人：张三，邮箱 zhangsan@example.com，电话 13800138000",
                }
            ]
        }
    )
    info = result["structured_response"]  # 这里是一个 ContactInfo 实例
    print("[structured]", info)
    print("            name=", info.name, "email=", info.email)


# ---- 3. 自定义中间件 ----
@before_model
def log_turns(state: AgentState, runtime) -> dict[str, Any] | None:
    """每次调用模型前打一条日志（最朴素的可观测中间件）。

    真实用途：注入护栏、改写输入、按条件短路、埋点统计。
    返回 None 表示「不修改状态，继续」。
    """
    print(f"    (middleware) 当前历史 {len(state['messages'])} 条消息，准备调用模型")
    return None


def demo_streaming_and_middleware() -> None:
    """流式 + 自定义中间件：边跑边看事件流，同时每步打日志。

    场景：前端实时展示执行轨迹、线上排障、长任务进度反馈。
    """
    agent = create_agent(
        model=get_model(),
        tools=[],
        middleware=[log_turns],
    )
    print("[stream] 事件流：")
    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": "用一句话介绍杭州。"}]},
        stream_mode="updates",  # 每个节点产生的增量更新
    ):
        print("        ", chunk)


# ---- 4. 人工介入 HITL（交互式真实演示）----
@tool
def send_email(to: str, body: str) -> str:
    """给指定收件人发送一封邮件（高风险操作，演示用，不会真的发信）。"""
    return f"[已发送] 收件人={to}，正文={body}"


def demo_hitl() -> None:
    """人工介入 HITL：敏感工具（这里是 send_email）执行前暂停，等你在命令行 approve/reject。

    场景：下单、转账、删库、发邮件等高风险动作，执行前强制人工确认。
    机制（两阶段）：HumanInTheLoopMiddleware 在该工具真正执行前调 interrupt() 把状态存进
    checkpointer 并让 invoke() 带着 __interrupt__ 提前返回；你做完决定后，再用
    Command(resume=...) + 同一个 thread_id 恢复。所以 **必须配 checkpointer**。
    """
    agent = create_agent(
        model=get_model(),
        tools=[send_email],
        system_prompt="用户想发邮件时调用 send_email 工具，不要自己编造已发送。",
        # interrupt_on：把 send_email 标记为「执行前要人审」；没列的工具默认自动放行。
        middleware=[HumanInTheLoopMiddleware(interrupt_on={"send_email": True})],
        checkpointer=InMemorySaver(),            # ← 暂停/恢复的前提，缺了会报错
    )
    cfg = {"configurable": {"thread_id": "hitl-demo"}}

    print("[hitl] 发起任务：给 bob@example.com 发封邮件通知周会改期…")
    res = agent.invoke(
        {"messages": [{"role": "user",
                       "content": "给 bob@example.com 发封邮件，告诉他周会从周三改到周四下午3点"}]},
        cfg,
    )

    # 模型没调敏感工具 → 没有中断，直接作答
    if "__interrupt__" not in res:
        print("[hitl] 模型未调用敏感工具，直接作答：", res["messages"][-1].text)
        return

    # 暂停了：把待批准的动作摊开给人看（value 里是 HITLRequest）
    reqs = res["__interrupt__"][0].value["action_requests"]
    print("\n⚠️  以下敏感操作需要你确认：")
    for r in reqs:
        print(f"    工具 {r['name']}  参数={r['args']}")

    try:
        raw = input("   批准执行吗？[y=批准 / 直接回车或其它=拒绝，可写拒绝理由] ").strip()
    except EOFError:                             # 非交互式（管道/CI）→ 按安全默认：拒绝
        raw = ""
        print("   (检测到非交互式输入，按安全默认：拒绝)")

    if raw.lower() in ("y", "yes"):
        decisions = [{"type": "approve"} for _ in reqs]
        print("   ✅ 已批准，恢复执行…")
    else:
        reason = raw if raw and raw.lower() not in ("n", "no") else "用户拒绝了该操作"
        decisions = [{"type": "reject", "message": reason} for _ in reqs]
        print("   ⛔ 已拒绝，把理由回传给模型…")

    # 用 Command(resume=...) + 同一 thread_id 恢复，拿到最终答复
    final = agent.invoke(Command(resume={"decisions": decisions}), cfg)
    print("[hitl] 最终答复：", final["messages"][-1].text)


def explain_multi_provider() -> None:
    """多模型切换已拆到 09_multi_provider.py（可真实运行）。这里只留一个指路牌。"""
    print("[multi] 多模型切换见 09_multi_provider.py：换厂商只改一个 'provider:model' 字符串，"
          "还演示 .with_fallbacks() 容灾。")


if __name__ == "__main__":
    explain_multi_provider()  # 不需要 Key
    if not require_key():
        raise SystemExit(0)
    demo_structured_output()
    demo_streaming_and_middleware()
    demo_hitl()  # 交互式：会用 input() 等你 approve/reject，放最后
