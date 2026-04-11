#!/usr/bin/env python3
"""
端到端 Pipeline Demo：查询改写 → 混合检索 → 重排序 → 答案生成。

运行方式:
    # 无 API key（检索可运行，生成会显示原始检索结果）
    python scripts/run_pipeline_demo.py

    # 配置 API key（完整体验）
    OPENAI_API_KEY=your-key python scripts/run_pipeline_demo.py

    # 指定查询
    python scripts/run_pipeline_demo.py "公司去年毛利率变化了多少？"

前置条件:
    先运行 run_indexing_demo.py 构建索引。
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import ProjectConfig
from app.embeddings.bge_embedding import BGEEmbeddingModel
from app.generation.answer_generator import AnswerGenerator
from app.query.query_rewriter import QueryRewriter
from app.rerank.cross_encoder_reranker import CrossEncoderReranker
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.vector_store import FAISSVectorStore


def main() -> int:
    print("=" * 70)
    print("智能金融投研助手：端到端 RAG Pipeline Demo")
    print("=" * 70)

    # ── 初始化配置 ──
    config = ProjectConfig(
        project_root=PROJECT_ROOT,
        data_dir=PROJECT_ROOT / "data",
    )

    # ── 加载索引 ──
    index_path = config.data_dir / "index"
    if not index_path.with_suffix(".faiss").exists():
        print("❌ 索引文件不存在，请先运行: python scripts/run_indexing_demo.py")
        return 1

    print("\n正在加载模型和索引...")
    t0 = time.time()
    embedding_model = BGEEmbeddingModel(model_name=config.embedding_model_name)
    vector_store = FAISSVectorStore.load(index_path)
    bm25 = BM25Retriever(vector_store.chunks)
    hybrid = HybridRetriever(vector_store, bm25, embedding_model, vector_weight=config.vector_weight)
    reranker = CrossEncoderReranker(model_name=config.reranker_model_name)
    query_rewriter = QueryRewriter(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        model=config.openai_model,
    )
    answer_generator = AnswerGenerator(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        model=config.openai_model,
    )
    print(f"初始化完成 ({time.time() - t0:.2f}s)")

    if not config.openai_api_key:
        print("\n⚠️  未配置 OPENAI_API_KEY，查询改写和答案生成将使用 fallback 模式。")
        print("   设置方式: export OPENAI_API_KEY=your-key")

    # ── 获取查询 ──
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        default_queries = [
            "公司去年毛利率变化了多少？原因是什么？",
            "营业收入增长的主要驱动因素是什么？",
            "研发投入占比和趋势如何？",
            "公司面临的主要经营风险有哪些？",
        ]
        print("\n可选的示例查询:")
        for i, q in enumerate(default_queries, 1):
            print(f"  [{i}] {q}")
        print(f"  [0] 自定义输入")

        choice = input("\n请选择 (默认 1): ").strip() or "1"
        if choice == "0":
            query = input("请输入你的问题: ").strip()
            if not query:
                print("未输入问题，退出。")
                return 0
        elif choice.isdigit() and 1 <= int(choice) <= len(default_queries):
            query = default_queries[int(choice) - 1]
        else:
            query = default_queries[0]

    print(f"\n{'=' * 70}")
    print(f"原始查询: {query}")
    print("=" * 70)

    # ── 步骤 1: 查询改写 ──
    print("\n📝 步骤 1: 查询改写")
    t0 = time.time()
    rewritten_queries = query_rewriter.rewrite(query)
    print(f"   改写结果 ({time.time() - t0:.2f}s):")
    for i, rq in enumerate(rewritten_queries, 1):
        print(f"   [{i}] {rq}")

    # ── 步骤 2: 混合检索（对每个改写 query 检索，合并去重） ──
    print("\n🔍 步骤 2: 混合检索")
    t0 = time.time()
    all_results = {}
    for rq in rewritten_queries:
        results = hybrid.search(rq, top_k=config.hybrid_top_k)
        for chunk, score in results:
            if chunk.chunk_id not in all_results or score > all_results[chunk.chunk_id][1]:
                all_results[chunk.chunk_id] = (chunk, score)

    # 按分数排序
    merged_results = sorted(all_results.values(), key=lambda x: x[1], reverse=True)
    print(f"   检索到 {len(merged_results)} 个候选片段 ({time.time() - t0:.2f}s)")

    # ── 步骤 3: 重排序 ──
    print("\n📊 步骤 3: 重排序")
    t0 = time.time()
    reranked = reranker.rerank(query, merged_results, top_k=config.rerank_top_k)
    print(f"   重排序后 Top-{len(reranked)} ({time.time() - t0:.2f}s):")
    for i, (chunk, score) in enumerate(reranked, 1):
        section = " > ".join(chunk.section_path) if chunk.section_path else "未知"
        print(f"   [{i}] {chunk.chunk_id} (score={score:.4f}) [{section}]")

    # ── 步骤 4: 答案生成 ──
    print("\n💡 步骤 4: 答案生成")
    t0 = time.time()
    answer = answer_generator.generate(query, [c for c, _ in reranked])
    elapsed = time.time() - t0

    print(f"\n{'=' * 70}")
    print("回答:")
    print("=" * 70)
    print(answer)
    print(f"\n(生成耗时: {elapsed:.2f}s)")

    return 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    raise SystemExit(main())
