from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.rag.bge_embedding import BGEEmbeddingModel
from app.rag.bm25_retriever import BM25Retriever
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.reranker import CrossEncoderReranker
from app.rag.vector_store import Chunk, FAISSVectorStore

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """
    知识库：封装 RAG 检索全流程。

    Agent 通过 KnowledgeBase 与底层检索系统交互，
    不需要关心向量存储、BM25、重排序的实现细节。
    """

    def __init__(
        self,
        embedding_model: BGEEmbeddingModel,
        vector_store: FAISSVectorStore,
        bm25_retriever: BM25Retriever,
        reranker: CrossEncoderReranker,
        hybrid_top_k: int = 10,
        rerank_top_k: int = 5,
        vector_weight: float = 0.5,
    ) -> None:
        self.embedding_model = embedding_model
        self.hybrid = HybridRetriever(
            vector_store, bm25_retriever, embedding_model, vector_weight=vector_weight
        )
        self.reranker = reranker
        self.hybrid_top_k = hybrid_top_k
        self.rerank_top_k = rerank_top_k

    def search(self, query: str, top_k: int | None = None) -> List[Dict[str, Any]]:
        """
        执行混合检索 + 重排序，返回结构化结果。

        返回格式:
            [{"chunk_id": ..., "content": ..., "page_span": ..., "section_path": ..., "score": ...}]
        """
        rerank_k = top_k or self.rerank_top_k

        # 混合检索
        hybrid_results = self.hybrid.search(query, top_k=self.hybrid_top_k)

        # 重排序
        reranked = self.reranker.rerank(query, hybrid_results, top_k=rerank_k)

        # 转为字典格式
        results = []
        for chunk, score in reranked:
            results.append({
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "page_span": chunk.page_span,
                "section_path": chunk.section_path,
                "score": round(score, 4),
            })

        logger.info("知识库检索: query='%s', 返回 %d 条结果", query[:30], len(results))
        return results

    @classmethod
    def from_data(cls, data_dir: Path, config) -> "KnowledgeBase":
        """从数据目录构建知识库（加载已有索引或从头构建）。"""
        index_path = data_dir / "index"

        embedding_model = BGEEmbeddingModel(model_name=config.embedding_model_name)
        reranker = CrossEncoderReranker(model_name=config.reranker_model_name)

        if index_path.with_suffix(".faiss").exists():
            logger.info("加载已有索引: %s", index_path)
            vector_store = FAISSVectorStore.load(index_path)
            bm25 = BM25Retriever(vector_store.chunks)
        else:
            logger.info("索引不存在，从 sample_blocks.json 构建...")
            vector_store, bm25 = cls._build_index(data_dir, embedding_model, index_path)

        return cls(
            embedding_model=embedding_model,
            vector_store=vector_store,
            bm25_retriever=bm25,
            reranker=reranker,
            hybrid_top_k=config.hybrid_top_k,
            rerank_top_k=config.rerank_top_k,
            vector_weight=config.vector_weight,
        )

    @classmethod
    def _build_index(cls, data_dir: Path, embedding_model: BGEEmbeddingModel,
                     index_path: Path) -> Tuple[FAISSVectorStore, BM25Retriever]:
        """从 sample_blocks.json 构建索引。"""
        blocks_path = data_dir / "sample_blocks.json"
        raw = json.loads(blocks_path.read_text(encoding="utf-8"))

        # 简单清洗：过滤 header/footer
        cleaned = [b for b in raw if b["block_type"] not in ("header", "footer")]

        # 按章节分组构建 chunk
        chunks: List[Chunk] = []
        current_blocks: List[Dict] = []
        current_section: List[str] = []

        def flush():
            nonlocal current_blocks, current_section
            if not current_blocks:
                return
            content = "\n".join(b["text"] for b in current_blocks)
            pages = sorted({b["page_no"] for b in current_blocks})
            block_types = [b["block_type"] for b in current_blocks]
            chunks.append(Chunk(
                chunk_id=f"chunk_{len(chunks):04d}",
                content=content,
                page_span=pages,
                section_path=list(current_section),
                metadata={"block_types": block_types, "char_count": len(content)},
            ))
            current_blocks = []

        for block in cleaned:
            if block["block_type"] == "title":
                flush()
                current_section = block.get("section_path", [])
                current_blocks = [block]
            elif block["block_type"] == "table":
                flush()
                chunks.append(Chunk(
                    chunk_id=f"chunk_{len(chunks):04d}",
                    content=block["text"],
                    page_span=[block["page_no"]],
                    section_path=block.get("section_path", []),
                    metadata={"block_types": ["table"], "char_count": len(block["text"])},
                ))
            else:
                current_blocks.append(block)
        flush()

        # 向量化
        texts = [c.content for c in chunks]
        embeddings = embedding_model.encode(texts)

        # 构建索引
        vector_store = FAISSVectorStore(dimension=embedding_model.dimension)
        vector_store.add(chunks, embeddings)
        vector_store.save(index_path)

        bm25 = BM25Retriever(chunks)
        logger.info("索引构建完成: %d 个 chunk", len(chunks))
        return vector_store, bm25
