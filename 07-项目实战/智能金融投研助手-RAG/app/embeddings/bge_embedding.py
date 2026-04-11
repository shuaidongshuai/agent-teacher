from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class BGEEmbeddingModel:
    """
    基于 sentence-transformers 的真实 Embedding 模型。

    默认使用 BAAI/bge-small-zh-v1.5：
    - 专为中文优化，512 维向量
    - 模型约 90MB，首次运行时自动下载到 ~/.cache/huggingface/
    - 支持 passage 和 query 的不同前缀（BGE 模型推荐）

    使用方式:
        model = BGEEmbeddingModel()
        vectors = model.encode(["公司2024年营收增长12.5%"])
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        batch_size: int = 32,
        device: Optional[str] = None,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self._device = device
        self._model = None  # 懒加载，避免 import 时就下载模型

    def _load_model(self) -> None:
        """懒加载模型：第一次调用 encode 时才真正加载。"""
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "请安装 sentence-transformers: pip install sentence-transformers>=3.0.0"
            )

        logger.info("正在加载 embedding 模型: %s ...", self.model_name)
        self._model = SentenceTransformer(self.model_name, device=self._device)
        logger.info(
            "模型加载完成，维度: %d", self._model.get_sentence_embedding_dimension()
        )

    @property
    def dimension(self) -> int:
        """向量维度。"""
        self._load_model()
        assert self._model is not None
        return self._model.get_sentence_embedding_dimension()

    def encode(self, texts: List[str]) -> List[List[float]]:
        """
        将文本列表编码为归一化向量。

        BGE 模型推荐对 query 文本加 "为这个句子生成表示以用于检索中文文档：" 前缀，
        但这里统一处理（不加前缀），在检索阶段的 query 编码中单独处理。
        """
        self._load_model()
        assert self._model is not None

        # normalize_embeddings=True 使得内积 = 余弦相似度
        embeddings = self._model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 100,
        )

        return [vec.tolist() for vec in embeddings]

    def encode_query(self, query: str) -> List[float]:
        """
        编码单个查询文本。

        BGE 模型推荐对 query 加特定前缀以提升检索效果。
        """
        self._load_model()
        assert self._model is not None

        # BGE 中文模型推荐的 query 前缀
        prefixed = f"为这个句子生成表示以用于检索中文文档：{query}"
        embedding = self._model.encode(
            [prefixed], normalize_embeddings=True
        )
        return embedding[0].tolist()
