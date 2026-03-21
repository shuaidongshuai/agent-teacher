from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Block:
    """
    表示 PDF 解析后的最小结构单元。

    block 不一定等于自然段，它也可能是：
    - 标题
    - 正文段落
    - 表格
    - 页眉页脚
    """

    page_no: int
    block_type: str
    text: str
    section_path: List[str] = field(default_factory=list)


@dataclass
class Chunk:
    """
    表示最终用于索引和检索的 chunk。

    一个 chunk 往往由多个 block 合并而来。
    """

    chunk_id: str
    content: str
    page_span: List[int]
    section_path: List[str]
    source_blocks: List[Block]
    metadata: Dict[str, Any]
