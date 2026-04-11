#!/usr/bin/env python3
"""
Agentic RAG 金融投研助手 - 主入口。

运行方式:
    # 配置 API key（必需）
    export OPENAI_API_KEY=your-key

    # 运行
    python scripts/run_agent.py

    # 指定查询
    python scripts/run_agent.py "请分析公司的盈利能力变化趋势"

    # 先构建索引（如果还没有）
    python scripts/build_index.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import AgenticRAGConfig
from app.graph import build_graph
from app.knowledge_base import KnowledgeBase


def main() -> int:
    print("=" * 70)
    print("Agentic RAG 金融投研助手")
    print("=" * 70)

    # ── 配置检查 ──
    config = AgenticRAGConfig(
        project_root=PROJECT_ROOT,
        data_dir=PROJECT_ROOT / "data",
    )

    if not config.openai_api_key:
        print("\n❌ 请先配置 OPENAI_API_KEY:")
        print("   export OPENAI_API_KEY=your-key")
        print("\n   Agentic RAG 的所有决策节点都依赖 LLM，必须配置 API key。")
        return 1

    # ── 加载知识库 ──
    print("\n正在加载知识库...")
    t0 = time.time()
    kb = KnowledgeBase.from_data(config.data_dir, config)
    print(f"知识库就绪: {len(kb.hybrid.vector_store.chunks)} 个 chunk ({time.time() - t0:.1f}s)")

    # ── 构建图 ──
    print("正在构建 Agent 图...")
    graph, llm = build_graph(config, kb)
    print(f"图构建完成，最多 {config.max_retrieval_rounds} 轮检索，最多 {config.max_llm_calls} 次 LLM 调用")

    # ── 获取查询 ──
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        example_queries = [
            "请分析公司的盈利能力变化趋势，并解释毛利率下降的主要原因",
            "公司的现金流状况如何？经营性现金流能否覆盖资本开支？",
            "从收入结构和成本变化两个维度，评估公司未来的经营风险",
            "研发投入的趋势如何？对公司未来竞争力有什么影响？",
        ]
        print("\n示例查询:")
        for i, q in enumerate(example_queries, 1):
            print(f"  [{i}] {q}")
        print(f"  [0] 自定义输入")

        choice = input("\n请选择 (默认 1): ").strip() or "1"
        if choice == "0":
            query = input("请输入你的问题: ").strip()
            if not query:
                return 0
        elif choice.isdigit() and 1 <= int(choice) <= len(example_queries):
            query = example_queries[int(choice) - 1]
        else:
            query = example_queries[0]

    # ── 运行 Agent ──
    print(f"\n{'=' * 70}")
    print(f"问题: {query}")
    print("=" * 70)
    print("\nAgent 开始工作...\n")

    t0 = time.time()
    initial_state = {
        "user_query": query,
        "execution_log": [],
        "llm_call_count": 0,
        "retrieval_count": 0,
        "query_history": [],
        "accumulated_contexts": [],
    }

    # 执行图
    result = graph.invoke(initial_state)
    elapsed = time.time() - t0

    # ── 打印推理轨迹 ──
    print("=" * 70)
    print("推理轨迹")
    print("=" * 70)
    for log_entry in result.get("execution_log", []):
        print(f"  {log_entry}")

    # ── 打印统计 ──
    print(f"\n{'=' * 70}")
    print("执行统计")
    print("=" * 70)
    print(f"  检索轮数: {result.get('retrieval_count', 0)}/{config.max_retrieval_rounds}")
    print(f"  LLM 调用: {result.get('llm_call_count', 0)}/{config.max_llm_calls}")
    print(f"  累积上下文: {len(result.get('accumulated_contexts', []))} 条")
    print(f"  使用过的 query: {result.get('query_history', [])}")
    print(f"  总耗时: {elapsed:.1f}s")

    # ── 打印答案 ──
    print(f"\n{'=' * 70}")
    print("最终回答")
    print("=" * 70)
    print(result.get("final_answer", "（未生成答案）"))

    # ── 保存结果 ──
    output_dir = PROJECT_ROOT / "output"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "last_run.json"
    output_data = {
        "query": query,
        "answer": result.get("final_answer", ""),
        "retrieval_count": result.get("retrieval_count", 0),
        "llm_call_count": result.get("llm_call_count", 0),
        "query_history": result.get("query_history", []),
        "execution_log": result.get("execution_log", []),
        "elapsed_seconds": round(elapsed, 1),
    }
    output_file.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n详细结果已保存到: {output_file}")

    return 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    raise SystemExit(main())
