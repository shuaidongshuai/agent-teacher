#!/usr/bin/env python3
"""
检索 + 重排序 Demo：加载索引 → 混合检索 → 重排序 → 展示结果。

运行方式:
    python scripts/run_retrieval_demo.py

前置条件:
    先运行 run_indexing_demo.py 构建索引。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.embeddings.bge_embedding import BGEEmbeddingModel
from app.ingest.models import Chunk
from app.rerank.cross_encoder_reranker import CrossEncoderReranker
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.vector_store import FAISSVectorStore


def main() -> int:
    print("=" * 70)
    print("智能金融投研助手：检索与重排序 Demo")
    print("=" * 70)

    # ── 加载索引 ──
    index_path = PROJECT_ROOT / "data" / "index"
    if not index_path.with_suffix(".faiss").exists():
        print("❌ 索引文件不存在，请先运行 run_indexing_demo.py")
        return 1

    embedding_model = BGEEmbeddingModel()
    vector_store = FAISSVectorStore.load(index_path)
    bm25 = BM25Retriever(vector_store.chunks)
    hybrid = HybridRetriever(vector_store, bm25, embedding_model, vector_weight=0.5)
    reranker = CrossEncoderReranker()

    print(f"索引加载完成: {vector_store.index.ntotal} 个向量")

    # ── 测试查询 ──
    test_queries = [
        "公司去年毛利率变化了多少？原因是什么？",
        "营业收入增长的主要驱动因素",
        "研发投入占比和趋势",
        "公司有哪些经营风险？",
    ]

    for query in test_queries:
        print(f"\n{'=' * 70}")
        print(f"查询: 「{query}」")
        print("=" * 70)

        # ── 1. 单路检索对比 ──
        print("\n--- 向量检索 Top-3 ---")
        query_vec = embedding_model.encode_query(query)
        vec_results = vector_store.search(query_vec, top_k=3)
        for i, (chunk, score) in enumerate(vec_results, 1):
            print(f"  [{i}] {chunk.chunk_id} (score={score:.4f}) 章节={' > '.join(chunk.section_path)}")
            print(f"      {chunk.content[:80]}...")

        print("\n--- BM25 检索 Top-3 ---")
        bm25_results = bm25.search(query, top_k=3)
        for i, (chunk, score) in enumerate(bm25_results, 1):
            print(f"  [{i}] {chunk.chunk_id} (score={score:.4f}) 章节={' > '.join(chunk.section_path)}")
            print(f"      {chunk.content[:80]}...")

        # ── 2. 混合检索 ──
        print("\n--- 混合检索 (RRF) Top-5 ---")
        hybrid_results = hybrid.search(query, top_k=5)
        for i, (chunk, score) in enumerate(hybrid_results, 1):
            print(f"  [{i}] {chunk.chunk_id} (rrf={score:.6f}) 章节={' > '.join(chunk.section_path)}")
            print(f"      {chunk.content[:80]}...")

        # ── 3. 重排序 ──
        print("\n--- 重排序后 Top-3 ---")
        t0 = time.time()
        reranked = reranker.rerank(query, hybrid_results, top_k=3)
        elapsed = time.time() - t0
        for i, (chunk, score) in enumerate(reranked, 1):
            print(f"  [{i}] {chunk.chunk_id} (rerank={score:.4f}) 章节={' > '.join(chunk.section_path)}")
            print(f"      {chunk.content[:80]}...")
        print(f"  重排序耗时: {elapsed:.2f}s")

    print("\n检索 Demo 完成！接下来运行 run_pipeline_demo.py 体验完整的端到端问答。")
    return 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    raise SystemExit(main())
