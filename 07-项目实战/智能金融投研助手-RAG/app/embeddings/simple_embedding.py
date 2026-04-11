from __future__ import annotations

import random
from typing import List


class SimpleEmbeddingModel:
    “””
    教学型 embedding 占位实现，满足 EmbeddingModel 协议。

    为什么先做一个假的？
    因为第一阶段的重点是理解”切片逻辑”，而不是先被模型依赖卡住。

    后续你可以把这个类替换成 BGEEmbeddingModel（见 bge_embedding.py）。
    “””

    def __init__(self, dim: int = 16) -> None:
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    def encode(self, texts: List[str]) -> List[List[float]]:
        vectors: List[List[float]] = []

        for text in texts:
            # 这里用 hash 保证同一段文本多次运行时得到稳定向量，
            # 这样演示相似度逻辑时更容易观察现象。
            seed = abs(hash(text)) % (10**6)
            rng = random.Random(seed)
            vector = [rng.uniform(-1.0, 1.0) for _ in range(self._dim)]
            vectors.append(vector)

        return vectors
