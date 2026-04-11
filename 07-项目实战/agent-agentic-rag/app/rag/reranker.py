from __future__ import annotations

import logging
from typing import List, Tuple

from .vector_store import Chunk

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """交叉编码器重排序。详见智能金融投研助手-RAG 项目的完整注释版。"""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3") -> None:
        self.model_name = model_name
        self._model = None

    def _load_model(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import CrossEncoder
        logger.info("加载 reranker: %s ...", self.model_name)
        self._model = CrossEncoder(self.model_name)

    def rerank(self, query: str, chunks_with_scores: List[Tuple[Chunk, float]],
               top_k: int = 5) -> List[Tuple[Chunk, float]]:
        if not chunks_with_scores:
            return []
        self._load_model()
        pairs = [(query, chunk.content) for chunk, _ in chunks_with_scores]
        scores = self._model.predict(pairs)
        reranked = [(chunk, float(score)) for (chunk, _), score in zip(chunks_with_scores, scores)]
        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked[:top_k]
