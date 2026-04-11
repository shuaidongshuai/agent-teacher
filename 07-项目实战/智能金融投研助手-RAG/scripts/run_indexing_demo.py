#!/usr/bin/env python3
"""
构建索引 Demo：数据清洗 → 语义切片 → 向量化 → 建索引。

运行方式:
    python scripts/run_indexing_demo.py

这个脚本演示 RAG 离线阶段的完整流程：
1. 加载 sample_blocks.json
2. 清洗噪声 block
3. 结构优先 + 语义辅助切片
4. 用真实 BGE 模型生成向量
5. 构建 FAISS 索引 + BM25 索引
6. 保存 FAISS 索引到磁盘
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
from app.ingest.chunker import SemanticChunker
from app.ingest.cleaner import FinancialDocCleaner
from app.ingest.models import Block
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.vector_store import FAISSVectorStore


def load_sample_blocks() -> list[Block]:
    sample_path = PROJECT_ROOT / "data" / "sample_blocks.json"
    raw = json.loads(sample_path.read_text(encoding="utf-8"))
    return [Block(**item) for item in raw]


def main() -> int:
    print("=" * 70)
    print("智能金融投研助手：离线索引构建 Demo")
    print("=" * 70)

    # ── 步骤 1：加载数据 ──
    t0 = time.time()
    raw_blocks = load_sample_blocks()
    print(f"\n[1/5] 加载原始 block: {len(raw_blocks)} 个 ({time.time() - t0:.2f}s)")

    # ── 步骤 2：数据清洗 ──
    t0 = time.time()
    cleaner = FinancialDocCleaner()
    cleaned_blocks = cleaner.clean_blocks(raw_blocks)
    print(f"[2/5] 清洗后 block: {len(cleaned_blocks)} 个 ({time.time() - t0:.2f}s)")

    # ── 步骤 3：语义切片（使用真实 BGE 模型） ──
    t0 = time.time()
    embedding_model = BGEEmbeddingModel()
    chunker = SemanticChunker(
        embedding_model=embedding_model,
        similarity_threshold=0.75,
        max_chars=500,
        min_chars=60,
    )
    chunks = chunker.chunk(cleaned_blocks)
    print(f"[3/5] 切片完成: {len(chunks)} 个 chunk ({time.time() - t0:.2f}s)")

    # ── 步骤 4：向量化 + FAISS 索引 ──
    t0 = time.time()
    chunk_texts = [c.content for c in chunks]
    embeddings = embedding_model.encode(chunk_texts)
    print(f"       向量维度: {len(embeddings[0])}")

    vector_store = FAISSVectorStore(dimension=embedding_model.dimension)
    vector_store.add(chunks, embeddings)
    print(f"[4/5] FAISS 索引构建完成: {vector_store.index.ntotal} 个向量 ({time.time() - t0:.2f}s)")

    # 保存索引
    index_path = PROJECT_ROOT / "data" / "index"
    vector_store.save(index_path)
    print(f"       索引已保存到: {index_path}.faiss / {index_path}.chunks.pkl")

    # ── 步骤 5：BM25 索引 ──
    t0 = time.time()
    bm25 = BM25Retriever(chunks)
    print(f"[5/5] BM25 索引构建完成 ({time.time() - t0:.2f}s)")

    # ── 展示切片结果 ──
    print("\n" + "=" * 70)
    print("切片结果一览")
    print("=" * 70)
    for chunk in chunks:
        print(f"\n--- {chunk.chunk_id} ---")
        print(f"  页码: {chunk.page_span}")
        print(f"  章节: {' > '.join(chunk.section_path) if chunk.section_path else '(无)'}")
        print(f"  类型: {chunk.metadata.get('block_types', [])}")
        print(f"  字数: {len(chunk.content)}")
        print(f"  内容: {chunk.content[:100]}{'...' if len(chunk.content) > 100 else ''}")

    # ── 快速检索验证 ──
    print("\n" + "=" * 70)
    print("快速检索验证")
    print("=" * 70)

    test_queries = ["毛利率下降原因", "营业收入增长", "研发投入"]
    for query in test_queries:
        print(f"\n查询: 「{query}」")

        # 向量检索
        query_vec = embedding_model.encode_query(query)
        vec_results = vector_store.search(query_vec, top_k=3)
        print(f"  向量 Top-1: {vec_results[0][0].chunk_id} (score={vec_results[0][1]:.4f})" if vec_results else "  向量: 无结果")

        # BM25 检索
        bm25_results = bm25.search(query, top_k=3)
        print(f"  BM25 Top-1: {bm25_results[0][0].chunk_id} (score={bm25_results[0][1]:.4f})" if bm25_results else "  BM25: 无结果")

    print("\n索引构建完成！接下来可以运行 run_retrieval_demo.py 进行更详细的检索测试。")
    return 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    raise SystemExit(main())
