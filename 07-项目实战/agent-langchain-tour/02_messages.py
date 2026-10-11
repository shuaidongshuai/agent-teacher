"""
02_messages.py —— 消息（LangChain v1）

本节目标：理解 LangChain 用「消息对象」来组织对话，以及 v1 的标准内容块 content_blocks。

对应 README「消息」一节。涉及：
1. 四种常见消息：SystemMessage / HumanMessage / AIMessage / ToolMessage
2. 用消息列表做多轮对话（手动维护 history）
3. 字典写法：{"role": "...", "content": "..."}（和消息对象等价）
4. content_blocks：v1 新增的「标准内容块」，provider 无关地拿文本/推理/引用

运行：python 02_messages.py
"""

from __future__ import annotations

from common import get_model, require_key
from langchain.messages import AIMessage, HumanMessage, SystemMessage


def demo_message_objects() -> None:
    """用消息对象组织一轮带系统指令的对话。"""
    model = get_model()
    messages = [
        SystemMessage("你是一个只说中文、回答不超过 30 字的助手。"),
        HumanMessage("介绍一下你自己。"),
    ]
    resp = model.invoke(messages)
    print("[objects]", resp.text)
    print("          type:", type(resp).__name__)  # AIMessage


def demo_dict_style() -> None:
    """字典写法：和消息对象等价，很多场景更顺手。"""
    model = get_model()
    messages = [
        {"role": "system", "content": "你是数学老师，只给结果不解释。"},
        {"role": "user", "content": "123 * 456 = ?"},
    ]
    resp = model.invoke(messages)
    print("[dict]", resp.text)


def demo_multi_turn() -> None:
    """多轮：把上一轮的 AIMessage 拼回 history，模型才有「上下文」。

    注意：裸模型本身是无状态的——记忆要么你手动拼 history（这里），
    要么交给 Agent 的 checkpointer（见 05 节）。
    """
    model = get_model()
    history: list = [SystemMessage("你是旅行助手。")]

    history.append(HumanMessage("我想去一个有海的城市。"))
    r1 = model.invoke(history)
    history.append(r1)  # 关键：把模型回复也放回 history
    print("[turn1]", r1.text)

    history.append(HumanMessage("那边几月去最合适？"))  # 这里的「那边」依赖上一轮
    r2 = model.invoke(history)
    print("[turn2]", r2.text)


def demo_content_blocks() -> None:
    """content_blocks：v1 的标准内容块。

    不同厂商把「文本/推理过程/引用/内置工具调用」塞在不同字段里；
    content_blocks 用一套结构统一表达，便于跨厂商取用。
    """
    model = get_model()
    resp = model.invoke("简述三原色。")
    print("[blocks] .text        ->", resp.text)
    for block in resp.content_blocks:
        # 每个 block 形如 {"type": "text", "text": "..."}；
        # 推理模型还可能出现 {"type": "reasoning", ...} 等类型。
        print("         block type ->", block.get("type"))


if __name__ == "__main__":
    if not require_key():
        raise SystemExit(0)
    # demo_message_objects()
    # demo_dict_style()
    # demo_multi_turn()
    demo_content_blocks()
