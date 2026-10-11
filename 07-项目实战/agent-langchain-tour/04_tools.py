"""
04_tools.py —— 工具定义与调用（LangChain v1）

本节目标：定义工具，并用 create_agent 跑完整的 ReAct 循环（模型自己决定调哪个工具）。

对应 README「工具定义与调用」一节。涉及：
1. @tool：把普通函数声明成工具（类型标注 + docstring = 给模型看的说明书）
2. create_agent：一行搭好「模型 + 工具 + 系统提示」的 Agent
3. 观察工具被自动调用、结果回填、模型据此作答
4. 直接执行工具 / 查看工具的 name & args schema

运行：python 04_tools.py
"""

from __future__ import annotations

from common import get_model, require_key
from langchain.agents import create_agent
from langchain.tools import tool


@tool
def add(a: int, b: int) -> int:
    """计算两个整数之和。"""
    return a + b


@tool
def get_weather(city: str) -> str:
    """查询某个城市今天的天气（演示用，返回假数据）。"""
    fake = {"北京": "晴 12℃", "上海": "多云 18℃", "广州": "阵雨 26℃"}
    return fake.get(city, f"{city}：暂无数据")


def demo_tool_object() -> None:
    """工具本质：带 name / description / args schema 的可调用对象。"""
    print("[tool] name       ->", get_weather.name)
    print("[tool] description->", get_weather.description)
    print("[tool] args       ->", get_weather.args)
    # 也可以手动执行工具（不经过模型）。
    print("[tool] invoke     ->", get_weather.invoke({"city": "北京"}))


def demo_agent_with_tools() -> None:
    """create_agent：模型自己决定何时、调用哪个工具，并把结果融进回答。"""
    agent = create_agent(
        model=get_model(),
        tools=[add, get_weather],
        system_prompt="你是生活助手，需要算术或天气时调用工具，不要瞎编。",
    )
    # 这句话会触发两次工具调用（天气 + 加法），模型自动编排。
    out = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "北京今天天气怎么样？另外帮我算一下 24 + 18。",
                }
            ]
        }
    )
    # 打印整条消息轨迹，能看到 AIMessage(tool_calls) -> ToolMessage -> AIMessage。
    for m in out["messages"]:
        kind = type(m).__name__
        if getattr(m, "tool_calls", None):
            print(f"[{kind}] 请求工具 ->", [tc["name"] for tc in m.tool_calls])
        else:
            print(f"[{kind}]", m.text)


if __name__ == "__main__":
    demo_tool_object()  # 这个不需要 Key
    if not require_key():
        raise SystemExit(0)
    demo_agent_with_tools()
