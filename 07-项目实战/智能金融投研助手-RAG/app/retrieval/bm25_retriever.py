from __future__ import annotations

import logging
import re
from typing import List, Tuple

from app.ingest.models import Chunk

logger = logging.getLogger(__name__)


class BM25Retriever:
    """
    基于 BM25 的关键词检索器。

    为什么需要 BM25？
    在金融文档中，很多查询涉及精确匹配：
    - 公司名称、财务指标名（"毛利率"、"营业收入"）
    - 具体数值（"35.2%"、"12.5%"）
    - 年份（"2024年"）
    向量检索擅长语义匹配，但精确关键词匹配不如 BM25。
    两者结合（混合检索）才是最佳实践。

    分词策略：
    - 优先使用 jieba 分词（中文效果好）
    - 如果 jieba 未安装，退化为字符级 n-gram（效果差但能运行）
    """

    def __init__(self, chunks: List[Chunk]) -> None:
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            raise ImportError("请安装 rank-bm25: pip install rank-bm25>=0.2.2")

        self.chunks = chunks
        self._tokenize_fn = self._get_tokenizer()
        self.tokenized_corpus = [self._tokenize_fn(c.content) for c in chunks]

        from rank_bm25 import BM25Okapi
        self.bm25 = BM25Okapi(self.tokenized_corpus)
        logger.info("BM25 索引构建完成，文档数: %d", len(chunks))

    def _get_tokenizer(self):
        """获取分词函数：优先 jieba，退化为正则分词。"""
        try:
            import jieba
            jieba.setLogLevel(logging.WARNING)

            def tokenize(text: str) -> List[str]:
                # jieba 分词 + 过滤掉纯空白和单字符标点
                words = jieba.lcut(text)
                return [w.strip() for w in words if w.strip() and len(w.strip()) > 0]

            logger.info("使用 jieba 分词")
            return tokenize

        except ImportError:
            logger.warning("jieba 未安装，退化为正则分词（效果较差），建议: pip install jieba")

            def tokenize_fallback(text: str) -> List[str]:
                # 按中文字符和英文单词切分
                tokens = re.findall(r"[\u4e00-\u9fff]|[a-zA-Z0-9]+\.?[0-9]*%?", text)
                return tokens

            return tokenize_fallback

    def search(self, query: str, top_k: int = 10) -> List[Tuple[Chunk, float]]:
        """
        检索与 query 关键词最匹配的 top_k 个 chunk。

        返回:
            [(chunk, score), ...] 列表，按 BM25 分数降序排列
        """
        tokenized_query = self._tokenize_fn(query)
        scores = self.bm25.get_scores(tokenized_query)

        # 获取 top_k 的索引（按分数降序）
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results: List[Tuple[Chunk, float]] = []
        for idx in top_indices:
            if scores[idx] > 0:  # 过滤掉零分结果
                results.append((self.chunks[idx], float(scores[idx])))

        return results
