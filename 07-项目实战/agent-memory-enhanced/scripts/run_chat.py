"""
交互式对话入口。

运行方式:
    python scripts/run_chat.py

说明:
    - 需要 OPENAI_API_KEY
    - 需要安装 langgraph, sentence-transformers, faiss-cpu
    - 输入 /quit 退出
    - 输入 /memory 查看当前记忆状态
    - 输入 /clear 清空记忆
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import MemoryAgentConfig
from app.graph import build_graph, run_turn
from app.llm_client import LLMClient
from app.memory import LongTermMemory, ShortTermMemory, WorkingMemory


def print_working_memory(working: WorkingMemory) -> None:
    print("工作记忆:")
    print(f"  当前目标: {working.current_goal}")

    if working.key_facts:
        print("  关键事实:")
        for fact in working.key_facts:
            print(f"    - {fact}")
    else:
        print("  关键事实: （无）")

    if working.pending_questions:
        print("  待解决问题:")
        for question in working.pending_questions:
            print(f"    - {question}")
    else:
        print("  待解决问题: （无）")

    if working.reasoning_steps:
        print("  推理步骤:")
        for idx, step in enumerate(working.reasoning_steps, start=1):
            print(f"    {idx}. {step}")
    else:
        print("  推理步骤: （无）")


def main():
    print("=" * 60)
    print("       记忆增强 Agent - 交互式对话")
    print("=" * 60)

    config = MemoryAgentConfig(project_root=project_root)

    if not config.openai_api_key:
        print("\n错误: 请先设置 OPENAI_API_KEY")
        print("  例如: set OPENAI_API_KEY=your-key")
        return

    llm = LLMClient(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        model=config.openai_model,
        ca_bundle=config.openai_ca_bundle,
        ssl_verify=config.openai_ssl_verify,
    )

    short_term = ShortTermMemory(
        llm_client=llm,
        max_messages=config.short_term_max_messages,
        keep_recent=config.short_term_keep_recent,
    )

    long_term = LongTermMemory(
        storage_dir=config.memory_dir,
        embedding_model_name=config.embedding_model_name,
    )

    working = WorkingMemory()
    graph = build_graph(llm, short_term, long_term, working)

    print(f"\n已加载 {len(long_term.entries)} 条长期记忆")
    print("输入 /quit 退出 | /memory 查看记忆 | /clear 清空记忆\n")

    state = None
    turn = 0

    while turn < config.max_turns:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            print("再见。")
            break

        if user_input == "/memory":
            print("\n--- 记忆状态 ---")
            print(f"短期记忆: {len(short_term.messages)} 条消息")
            print(f"摘要: {short_term.summary[:200] or '（无）'}")
            print(f"长期记忆: {len(long_term.entries)} 条")
            for entry in long_term.entries[-5:]:
                print(f"  [{entry.category}] {entry.content}")
            print_working_memory(working)
            print("---\n")
            continue

        if user_input == "/clear":
            short_term.messages.clear()
            short_term.summary = ""
            long_term.clear()
            working.reset()
            state = None
            print("记忆已清空。\n")
            continue

        state = run_turn(graph, user_input, state)
        turn += 1

        response = state.get("assistant_response", "")
        print(f"\n助手: {response}\n")

        log = state.get("execution_log", [])
        if log:
            print(
                f"  [调试] LLM调用: {state.get('llm_call_count', 0)} | 长期记忆: {len(long_term.entries)} 条"
            )
            print(f"  [调试] 工作目标: {working.current_goal}")
            print(f"  [调试] 关键事实: {len(working.key_facts)} 条")
            print(f"  [调试] 待解决问题: {len(working.pending_questions)} 条")

    print(f"\n对话结束，共 {turn} 轮。")


if __name__ == "__main__":
    main()
