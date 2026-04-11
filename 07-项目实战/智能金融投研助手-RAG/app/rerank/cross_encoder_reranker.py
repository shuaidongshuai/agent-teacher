from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from app.ingest.models import Chunk

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """
    基于交叉编码器的重排序器。

    为什么需要重排序？（详见 03-RAG/4.为什么RAG需要重排序.md）
    - 初筛（BM25/向量）追求召回率，难免混入噪声
    - 交叉编码器对 (query, document) 对做精细打分，准确率远高于双塔模型
    - 但交叉编码器速度慢，所以只对初筛 top-k 结果做重排序

    默认模型 BAAI/bge-reranker-v2-m3：
    - 支持中英文
    - 约 560MB，首次运行自动下载
    - 可替换为更小的 BAAI/bge-reranker-base（约 220MB）
    """

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3") -> None:
        self.model_name = model_name
        self._model = None  # 懒加载

    def _load_model(self) -> None:
        if self._model is not None:
            return

        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            raise ImportError(
                "请安装 sentence-transformers: pip install sentence-transformers>=3.0.0"
            )

        logger.info("正在加载 reranker 模型: %s ...", self.model_name)
        self._model = CrossEncoder(self.model_name)
        logger.info("Reranker 模型加载完成")

    def rerank(
        self,
        query: str,
        chunks_with_scores: List[Tuple[Chunk, float]],
        top_k: int = 5,
    ) -> List[Tuple[Chunk, float]]:
        """
        对候选 chunk 进行重排序。

        参数:
            query: 用户查询
            chunks_with_scores: 初筛结果 [(chunk, initial_score), ...]
            top_k: 重排序后保留的结果数量
        返回:
            [(chunk, rerank_score), ...] 按重排序分数降序排列
        """
        if not chunks_with_scores:
            return []

        self._load_model()
        assert self._model is not None

        # 构造 (query, passage) 对
        pairs = [(query, chunk.content) for chunk, _ in chunks_with_scores]

        # 交叉编码器打分
        scores = self._model.predict(pairs)

        # 组合结果并排序
        reranked = [
            (chunk, float(score))
            for (chunk, _), score in zip(chunks_with_scores, scores)
        ]
        reranked.sort(key=lambda x: x[1], reverse=True)

        logger.info(
            "重排序完成: %d 候选 -> top %d",
            len(chunks_with_scores), min(top_k, len(reranked)),
        )

        return reranked[:top_k]
