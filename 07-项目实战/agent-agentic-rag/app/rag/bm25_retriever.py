from __future__ import annotations

import logging
import re
from typing import List, Tuple

from .vector_store import Chunk

logger = logging.getLogger(__name__)


class BM25Retriever:
    """BM25 关键词检索。详见智能金融投研助手-RAG 项目的完整注释版。"""

    def __init__(self, chunks: List[Chunk]) -> None:
        from rank_bm25 import BM25Okapi
        self.chunks = chunks
        self._tokenize_fn = self._get_tokenizer()
        self.tokenized_corpus = [self._tokenize_fn(c.content) for c in chunks]
        self.bm25 = BM25Okapi(self.tokenized_corpus)

    def _get_tokenizer(self):
        try:
            import jieba
            jieba.setLogLevel(logging.WARNING)
            def tokenize(text: str) -> List[str]:
                return [w.strip() for w in jieba.lcut(text) if w.strip()]
            return tokenize
        except ImportError:
            def tokenize_fallback(text: str) -> List[str]:
                return re.findall(r"[\u4e00-\u9fff]|[a-zA-Z0-9]+\.?[0-9]*%?", text)
            return tokenize_fallback

    def search(self, query: str, top_k: int = 10) -> List[Tuple[Chunk, float]]:
        tokenized_query = self._tokenize_fn(query)
        scores = self.bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [(self.chunks[idx], float(scores[idx])) for idx in top_indices if scores[idx] > 0]
