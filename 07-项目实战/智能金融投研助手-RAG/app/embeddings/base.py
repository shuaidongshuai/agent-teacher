from __future__ import annotations

from typing import List, Protocol, runtime_checkable


@runtime_checkable
class EmbeddingModel(Protocol):
    """
    Embedding 模型的统一协议。

    所有 embedding 实现（占位模型、BGE、Jina 等）都应满足这个接口，
    这样切片器、检索器可以无缝切换不同的 embedding 后端。
    """

    @property
    def dimension(self) -> int:
        """向量维度。"""
        ...

    def encode(self, texts: List[str]) -> List[List[float]]:
        """
        将文本列表编码为向量列表。

        参数:
            texts: 待编码的文本列表
        返回:
            与 texts 等长的向量列表，每个向量维度为 self.dimension
        """
        ...
