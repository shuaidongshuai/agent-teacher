from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from .vector_store import Chunk, FAISSVectorStore
from .bm25_retriever import BM25Retriever

logger = logging.getLogger(__name__)


class HybridRetriever:
    """RRF 混合检索。详见智能金融投研助手-RAG 项目的完整注释版。"""

    def __init__(self, vector_store: FAISSVectorStore, bm25: BM25Retriever,
                 embedding_model, vector_weight: float = 0.5, rrf_k: int = 60) -> None:
        self.vector_store = vector_store
        self.bm25 = bm25
        self.embedding_model = embedding_model
        self.vector_weight = vector_weight
        self.rrf_k = rrf_k

    def search(self, query: str, top_k: int = 10) -> List[Tuple[Chunk, float]]:
        candidate_k = top_k * 2
        query_vec = self.embedding_model.encode_query(query)
        vec_results = self.vector_store.search(query_vec, top_k=candidate_k)
        bm25_results = self.bm25.search(query, top_k=candidate_k)
        return self._rrf_merge(vec_results, bm25_results)[:top_k]

    def _rrf_merge(self, vec_results, bm25_results):
        scores: Dict[str, float] = {}
        chunk_map: Dict[str, Chunk] = {}
        for rank, (chunk, _) in enumerate(vec_results):
            chunk_map[chunk.chunk_id] = chunk
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0) + self.vector_weight / (self.rrf_k + rank + 1)
        bm25_weight = 1.0 - self.vector_weight
        for rank, (chunk, _) in enumerate(bm25_results):
            chunk_map[chunk.chunk_id] = chunk
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0) + bm25_weight / (self.rrf_k + rank + 1)
        sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)
        return [(chunk_map[cid], scores[cid]) for cid in sorted_ids]
