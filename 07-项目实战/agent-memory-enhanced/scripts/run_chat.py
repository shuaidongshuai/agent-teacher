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


def main():
    print("=" * 60)
    print("       记忆增强 Agent — 交互式对话")
    print("=" * 60)

    config = MemoryAgentConfig(project_root=project_root)

    if not config.openai_api_key:
        print("\n错误: 请先设置 OPENAI_API_KEY")
        print("  export OPENAI_API_KEY=your-key")
        return

    # 初始化组件
    llm = LLMClient(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        model=config.openai_model,
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

    # 构建图
    graph = build_graph(llm, short_term, long_term, working)

    print(f"\n已加载 {len(long_term.entries)} 条长期记忆")
    print("输入 /quit 退出 | /memory 查看记忆 | /clear 清空记忆\n")

    state = None
    turn = 0

    while turn < config.max_turns:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            print("再见！")
            break

        if user_input == "/memory":
            print("\n--- 记忆状态 ---")
            print(f"短期记忆: {len(short_term.messages)} 条消息")
            print(f"摘要: {short_term.summary[:200] or '（无）'}")
            print(f"长期记忆: {len(long_term.entries)} 条")
            for i, entry in enumerate(long_term.entries[-5:]):
                print(f"  [{entry.category}] {entry.content}")
            print(f"工作记忆: {working.current_goal}")
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

        # 执行一轮对话
        state = run_turn(graph, user_input, state)
        turn += 1

        response = state.get("assistant_response", "")
        print(f"\n助手: {response}\n")

        # 打印调试信息
        log = state.get("execution_log", [])
        if log:
            print(f"  [调试] LLM调用: {state.get('llm_call_count', 0)} | 记忆: {len(long_term.entries)} 条")

    print(f"\n对话结束，共 {turn} 轮。")


if __name__ == "__main__":
    main()
