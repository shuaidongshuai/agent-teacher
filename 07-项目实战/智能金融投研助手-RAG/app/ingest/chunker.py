from __future__ import annotations

import math
from typing import List

from app.embeddings.simple_embedding import SimpleEmbeddingModel

from .models import Block, Chunk


class SemanticChunker:
    """
    一个教学型的“结构优先 + 语义辅助”切片器。

    设计原则：
    1. 标题是强边界
    2. 表格尽量单独成块
    3. 正文段落通过相邻语义相似度判断是否拼接
    4. 保留页码、section_path、block_type 等 metadata
    """

    def __init__(
        self,
        embedding_model: SimpleEmbeddingModel,
        similarity_threshold: float = 0.78,
        max_chars: int = 1200,
        min_chars: int = 200,
    ) -> None:
        self.embedding_model = embedding_model
        self.similarity_threshold = similarity_threshold
        self.max_chars = max_chars
        self.min_chars = min_chars

    def chunk(self, blocks: List[Block]) -> List[Chunk]:
        chunks: List[Chunk] = []
        current_blocks: List[Block] = []

        target_blocks = [b for b in blocks if b.block_type in {"title", "paragraph", "table"}]
        if not target_blocks:
            return chunks

        for block in target_blocks:
            if block.block_type == "title":
                self._flush_chunk(current_blocks, chunks)
                current_blocks = [block]
                continue

            if block.block_type == "table":
                self._flush_chunk(current_blocks, chunks)
                chunks.append(self._build_chunk([block], len(chunks)))
                current_blocks = []
                continue

            if not current_blocks:
                current_blocks.append(block)
                continue

            last_block = current_blocks[-1]
            current_text = "\n".join(item.text for item in current_blocks)

            if last_block.block_type == "title":
                current_blocks.append(block)
                continue

            similarity = self._similarity(last_block.text, block.text)
            if similarity >= self.similarity_threshold and len(current_text) < self.max_chars:
                current_blocks.append(block)
            else:
                self._flush_chunk(current_blocks, chunks)
                current_blocks = [block]

        self._flush_chunk(current_blocks, chunks)
        return self._merge_short_chunks(chunks)

    def _similarity(self, text_a: str, text_b: str) -> float:
        """
        计算两段文本的余弦相似度。

        这里故意拆开写，方便学习者后续替换成真实 embedding 模型。
        """

        embeddings = self.embedding_model.encode([text_a, text_b])
        vector_a, vector_b = embeddings[0], embeddings[1]

        dot = sum(a * b for a, b in zip(vector_a, vector_b))
        norm_a = math.sqrt(sum(value * value for value in vector_a))
        norm_b = math.sqrt(sum(value * value for value in vector_b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)

    def _flush_chunk(self, current_blocks: List[Block], chunks: List[Chunk]) -> None:
        if not current_blocks:
            return
        chunks.append(self._build_chunk(current_blocks, len(chunks)))
        current_blocks.clear()

    def _build_chunk(self, blocks: List[Block], idx: int) -> Chunk:
        content = "\n".join(block.text for block in blocks)
        page_span = sorted({block.page_no for block in blocks})
        section_path = blocks[0].section_path if blocks else []

        return Chunk(
            chunk_id=f"chunk_{idx:04d}",
            content=content,
            page_span=page_span,
            section_path=section_path,
            source_blocks=list(blocks),
            metadata={
                "block_types": [block.block_type for block in blocks],
                "char_count": len(content),
            },
        )

    def _merge_short_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        二次修正：
        如果某个 chunk 太短，就尝试和前一个合并。
        """

        if not chunks:
            return []

        merged: List[Chunk] = [chunks[0]]

        for chunk in chunks[1:]:
            prev = merged[-1]

            # 表格 chunk 往往本身就短，但它的独立性很重要，所以不轻易合并。
            if "table" in chunk.metadata["block_types"]:
                merged.append(chunk)
                continue

            # 如果 section_path 已经变化，说明语义边界很可能发生了变化，也不合并。
            if prev.section_path != chunk.section_path:
                merged.append(chunk)
                continue

            if len(chunk.content) < self.min_chars and merged:
                merged[-1] = Chunk(
                    chunk_id=prev.chunk_id,
                    content=prev.content + "\n" + chunk.content,
                    page_span=sorted(set(prev.page_span + chunk.page_span)),
                    section_path=prev.section_path,
                    source_blocks=prev.source_blocks + chunk.source_blocks,
                    metadata={
                        "block_types": prev.metadata["block_types"] + chunk.metadata["block_types"],
                        "char_count": len(prev.content) + len(chunk.content),
                    },
                )
            else:
                merged.append(chunk)

        return merged
