from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class BGEEmbeddingModel:
    """BGE 中文 Embedding 模型。详见智能金融投研助手-RAG 项目的完整注释版。"""

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5") -> None:
        self.model_name = model_name
        self._model = None

    def _load_model(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer
        logger.info("加载 embedding 模型: %s ...", self.model_name)
        self._model = SentenceTransformer(self.model_name)
        logger.info("维度: %d", self._model.get_sentence_embedding_dimension())

    @property
    def dimension(self) -> int:
        self._load_model()
        return self._model.get_sentence_embedding_dimension()

    def encode(self, texts: List[str]) -> List[List[float]]:
        self._load_model()
        embeddings = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [vec.tolist() for vec in embeddings]

    def encode_query(self, query: str) -> List[float]:
        self._load_model()
        prefixed = f"为这个句子生成表示以用于检索中文文档：{query}"
        embedding = self._model.encode([prefixed], normalize_embeddings=True)
        return embedding[0].tolist()
