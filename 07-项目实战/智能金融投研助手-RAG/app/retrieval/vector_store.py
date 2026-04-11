from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import List, Tuple

from app.ingest.models import Chunk

logger = logging.getLogger(__name__)


class FAISSVectorStore:
    """
    基于 FAISS 的向量存储与检索。

    设计要点：
    1. 使用 IndexFlatIP（内积）配合归一化向量 = 余弦相似度
       - IndexFlatIP 是精确搜索，适合教学和中小规模数据
       - 生产环境数据量大时可替换为 IndexIVFFlat 或 IndexHNSW
    2. 向量索引和 Chunk 元数据分开存储
       - FAISS 只存向量，Chunk 对象单独 pickle
       - 这样 FAISS 索引可以独立更新
    """

    def __init__(self, dimension: int) -> None:
        try:
            import faiss
        except ImportError:
            raise ImportError("请安装 faiss-cpu: pip install faiss-cpu>=1.8.0")

        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)
        self.chunks: List[Chunk] = []

    def add(self, chunks: List[Chunk], embeddings: List[List[float]]) -> None:
        """
        将 chunk 和对应的向量添加到索引中。

        参数:
            chunks: Chunk 对象列表
            embeddings: 对应的向量列表，必须与 chunks 等长
        """
        import numpy as np

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"chunks 数量 ({len(chunks)}) 与 embeddings 数量 ({len(embeddings)}) 不匹配"
            )

        vectors = np.array(embeddings, dtype=np.float32)
        self.index.add(vectors)
        self.chunks.extend(chunks)
        logger.info("已添加 %d 个向量到索引，当前总量: %d", len(chunks), self.index.ntotal)

    def search(self, query_embedding: List[float], top_k: int = 10) -> List[Tuple[Chunk, float]]:
        """
        检索与 query 最相似的 top_k 个 chunk。

        返回:
            [(chunk, score), ...] 列表，按相似度降序排列
        """
        import numpy as np

        if self.index.ntotal == 0:
            return []

        query_vec = np.array([query_embedding], dtype=np.float32)
        actual_k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(query_vec, actual_k)

        results: List[Tuple[Chunk, float]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:  # FAISS 用 -1 表示无效结果
                continue
            results.append((self.chunks[idx], float(score)))

        return results

    def save(self, path: Path) -> None:
        """
        持久化索引到磁盘。

        保存两个文件：
        - {path}.faiss: FAISS 索引
        - {path}.chunks.pkl: Chunk 元数据
        """
        import faiss

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self.index, str(path.with_suffix(".faiss")))
        with open(path.with_suffix(".chunks.pkl"), "wb") as f:
            pickle.dump(self.chunks, f)

        logger.info("索引已保存: %s（%d 个向量）", path, self.index.ntotal)

    @classmethod
    def load(cls, path: Path) -> "FAISSVectorStore":
        """从磁盘加载索引。"""
        import faiss

        path = Path(path)
        index = faiss.read_index(str(path.with_suffix(".faiss")))
        with open(path.with_suffix(".chunks.pkl"), "rb") as f:
            chunks = pickle.load(f)

        store = cls.__new__(cls)
        store.dimension = index.d
        store.index = index
        store.chunks = chunks

        logger.info("索引已加载: %s（%d 个向量）", path, index.ntotal)
        return store
