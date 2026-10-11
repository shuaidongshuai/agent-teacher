"""
01_models.py —— 调用模型（LangChain v1）

本节目标：掌握「用统一接口调用任意厂商的 chat model」。

对应 README「调用模型」一节。涉及：
1. init_chat_model：统一入口，provider:model 字符串选模型
2. invoke：一次问答
3. stream：流式逐 token 输出
4. batch：一次并发跑多条输入
5. 运行参数：temperature 等

运行：python 01_models.py
"""

from __future__ import annotations

from common import get_model, require_key


def demo_invoke() -> None:
    """最基础：invoke 一次拿到完整回答。"""
    model = get_model()
    # 输入既可以是一个字符串，也可以是消息列表（见 02_messages.py）。
    resp = model.invoke("用一句话解释什么是大语言模型。")
    print("[invoke] ", resp.text)  # .text 取纯文本；.content_blocks 见 02 节


def demo_stream() -> None:
    """流式：逐块产出，适合前端打字机效果、长回答场景。"""
    model = get_model()
    print("[stream] ", end="", flush=True)
    for chunk in model.stream("用三点说明 Agent 和普通聊天机器人的区别。"):
        print(chunk.text, end="", flush=True)
    print()


def demo_batch() -> None:
    """批量：一次并发跑多条输入，比 for 循环逐条调用快得多。"""
    model = get_model()
    questions = [
        "RAG 是什么？一句话。",
        "function calling 是什么？一句话。",
        "向量数据库是什么？一句话。",
    ]
    results = model.batch(questions)
    for q, r in zip(questions, results):
        print(f"[batch] Q: {q}\n        A: {r.text}")


def demo_runtime_params() -> None:
    """运行参数：如 temperature；也体现「换模型只改字符串」。"""
    # 把 temperature 直接传进 init_chat_model（经由 common.get_model 透传）。
    model = get_model(temperature=0)
    resp = model.invoke("随机报一个 1-10 的数字，只输出数字。")
    print("[params] temperature=0 ->", resp.text)


if __name__ == "__main__":
    if not require_key():
        raise SystemExit(0)
    # demo_invoke()
    # demo_stream()
    # demo_batch()
    demo_runtime_params()
