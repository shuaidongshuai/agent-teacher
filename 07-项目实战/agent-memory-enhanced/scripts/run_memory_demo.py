"""
记忆能力演示（自动多轮对话）。

运行方式:
    python scripts/run_memory_demo.py

说明:
    - 自动运行 sample_conversations.json 中的测试对话
    - 观察 Agent 如何记住和召回信息
    - 需要 OPENAI_API_KEY
"""

import json
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
    print("       记忆增强 Agent — 自动演示")
    print("=" * 60)

    config = MemoryAgentConfig(project_root=project_root)

    if not config.openai_api_key:
        print("\n错误: 请先设置 OPENAI_API_KEY")
        print("  export OPENAI_API_KEY=your-key")
        return

    # 加载测试对话
    conv_path = config.data_dir / "sample_conversations.json"
    with open(conv_path, "r", encoding="utf-8") as f:
        conversations = json.load(f)

    print(f"已加载 {len(conversations)} 组测试对话\n")

    for conv in conversations:
        conv_id = conv["id"]
        description = conv["description"]
        turns = conv["turns"]

        print(f"\n{'='*60}")
        print(f"测试: {conv_id} — {description}")
        print(f"{'='*60}")

        # 每组对话使用独立的记忆
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

        # 使用临时目录避免干扰
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            long_term = LongTermMemory(
                storage_dir=Path(tmpdir),
                embedding_model_name=config.embedding_model_name,
            )
            working = WorkingMemory()

            graph = build_graph(llm, short_term, long_term, working)
            state = None

            for i, turn in enumerate(turns):
                user_input = turn["content"]
                print(f"\n[轮 {i+1}] 用户: {user_input}")

                state = run_turn(graph, user_input, state)
                response = state.get("assistant_response", "")
                print(f"[轮 {i+1}] 助手: {response}")

                # 简要状态
                print(
                    f"        [记忆: {len(long_term.entries)} 条 | "
                    f"LLM调用: {state.get('llm_call_count', 0)}]"
                )

        print(f"\n--- {conv_id} 完成 ---")

    print(f"\n{'='*60}")
    print("所有测试对话已完成！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
