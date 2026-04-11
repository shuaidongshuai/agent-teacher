from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from app.embeddings.base import EmbeddingModel
from app.ingest.models import Chunk
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.vector_store import FAISSVectorStore

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    混合检索器：BM25 + 向量检索 + Reciprocal Rank Fusion（RRF）融合。

    为什么需要混合检索？
    - BM25 擅长精确关键词匹配（公司名、指标名、数值）
    - 向量检索擅长语义匹配（"盈利能力" ≈ "毛利率"、"净利率"）
    - 两者互补，RRF 融合后的效果通常显著优于单一检索

    RRF（Reciprocal Rank Fusion）原理：
    对于每个文档 d，其融合分数 = Σ 1/(k + rank_i(d))
    其中 k 是常数（默认 60），rank_i(d) 是文档在第 i 个检索结果中的排名。
    RRF 的好处是不需要归一化不同检索器的分数，直接用排名融合。
    """

    def __init__(
        self,
        vector_store: FAISSVectorStore,
        bm25_retriever: BM25Retriever,
        embedding_model: EmbeddingModel,
        vector_weight: float = 0.5,
        rrf_k: int = 60,
    ) -> None:
        self.vector_store = vector_store
        self.bm25_retriever = bm25_retriever
        self.embedding_model = embedding_model
        self.vector_weight = vector_weight
        self.rrf_k = rrf_k

    def search(self, query: str, top_k: int = 10) -> List[Tuple[Chunk, float]]:
        """
        混合检索：同时运行 BM25 和向量检索，用 RRF 融合结果。

        参数:
            query: 用户查询
            top_k: 最终返回的结果数量
        返回:
            [(chunk, rrf_score), ...] 列表，按融合分数降序排列
        """
        # 两路检索各取 top_k * 2，给 RRF 足够的候选
        candidate_k = top_k * 2

        # ── 向量检索 ──
        if hasattr(self.embedding_model, "encode_query"):
            query_vec = self.embedding_model.encode_query(query)
        else:
            query_vec = self.embedding_model.encode([query])[0]
        vec_results = self.vector_store.search(query_vec, top_k=candidate_k)

        # ── BM25 检索 ──
        bm25_results = self.bm25_retriever.search(query, top_k=candidate_k)

        # ── RRF 融合 ──
        merged = self._rrf_merge(vec_results, bm25_results)

        logger.info(
            "混合检索完成: 向量 %d 条, BM25 %d 条, 融合后 %d 条",
            len(vec_results), len(bm25_results), len(merged),
        )

        return merged[:top_k]

    def _rrf_merge(
        self,
        vec_results: List[Tuple[Chunk, float]],
        bm25_results: List[Tuple[Chunk, float]],
    ) -> List[Tuple[Chunk, float]]:
        """RRF 融合两路检索结果。"""
        scores: Dict[str, float] = {}
        chunk_map: Dict[str, Chunk] = {}

        # 向量检索结果的 RRF 分数
        for rank, (chunk, _) in enumerate(vec_results):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            scores[cid] = scores.get(cid, 0.0) + self.vector_weight / (self.rrf_k + rank + 1)

        # BM25 检索结果的 RRF 分数
        bm25_weight = 1.0 - self.vector_weight
        for rank, (chunk, _) in enumerate(bm25_results):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            scores[cid] = scores.get(cid, 0.0) + bm25_weight / (self.rrf_k + rank + 1)

        # 按融合分数降序排列
        sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)
        return [(chunk_map[cid], scores[cid]) for cid in sorted_ids]
