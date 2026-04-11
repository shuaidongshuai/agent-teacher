from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)


class Chunk:
    """检索用的文档片段。"""

    def __init__(self, chunk_id: str, content: str, page_span: List[int],
                 section_path: List[str], metadata: dict) -> None:
        self.chunk_id = chunk_id
        self.content = content
        self.page_span = page_span
        self.section_path = section_path
        self.metadata = metadata


class FAISSVectorStore:
    """FAISS 向量存储。详见智能金融投研助手-RAG 项目的完整注释版。"""

    def __init__(self, dimension: int) -> None:
        import faiss
        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)
        self.chunks: List[Chunk] = []

    def add(self, chunks: List[Chunk], embeddings: List[List[float]]) -> None:
        import numpy as np
        vectors = np.array(embeddings, dtype=np.float32)
        self.index.add(vectors)
        self.chunks.extend(chunks)

    def search(self, query_embedding: List[float], top_k: int = 10) -> List[Tuple[Chunk, float]]:
        import numpy as np
        if self.index.ntotal == 0:
            return []
        query_vec = np.array([query_embedding], dtype=np.float32)
        actual_k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(query_vec, actual_k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0:
                results.append((self.chunks[idx], float(score)))
        return results

    def save(self, path: Path) -> None:
        import faiss
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(path.with_suffix(".faiss")))
        with open(path.with_suffix(".chunks.pkl"), "wb") as f:
            pickle.dump(self.chunks, f)

    @classmethod
    def load(cls, path: Path) -> "FAISSVectorStore":
        import faiss
        path = Path(path)
        index = faiss.read_index(str(path.with_suffix(".faiss")))
        with open(path.with_suffix(".chunks.pkl"), "rb") as f:
            chunks = pickle.load(f)
        store = cls.__new__(cls)
        store.dimension = index.d
        store.index = index
        store.chunks = chunks
        return store
