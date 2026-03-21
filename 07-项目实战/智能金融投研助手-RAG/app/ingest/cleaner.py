from __future__ import annotations

import re
from typing import List

from .models import Block


class FinancialDocCleaner:
    """
    针对金融 PDF 文本做第一阶段清洗。

    目标不是“把所有东西都删掉”，而是：
    1. 尽量保留真正有信息量的 block
    2. 去掉明显噪声
    3. 为后续切片阶段准备更稳定的输入
    """

    def __init__(self) -> None:
        self.footer_patterns = [
            r"第\s*\d+\s*页",
            r"Page\s+\d+",
            r"\d+\s*/\s*\d+",
            r"仅供参考",
        ]
        self.header_patterns = [
            r".*年度报告.*",
            r".*证券研究报告.*",
            r".*公司研究.*",
        ]

    def clean_text(self, text: str) -> str:
        """
        做轻量级清洗。

        这里只做保守清洗，避免过早破坏原始信息。
        """

        text = text.strip()
        text = text.replace("\u3000", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{2,}", "\n", text)
        return text

    def is_noise_block(self, block: Block) -> bool:
        """
        判断一个 block 是否应当在第一阶段被过滤。
        """

        text = block.text.strip()
        if not text:
            return True

        if block.block_type in {"header", "footer"}:
            return True

        for pattern in self.footer_patterns + self.header_patterns:
            if re.fullmatch(pattern, text):
                return True

        return False

    def clean_blocks(self, blocks: List[Block]) -> List[Block]:
        cleaned: List[Block] = []

        for block in blocks:
            if self.is_noise_block(block):
                continue

            text = self.clean_text(block.text)
            if not text:
                continue

            cleaned.append(
                Block(
                    page_no=block.page_no,
                    block_type=block.block_type,
                    text=text,
                    section_path=block.section_path,
                )
            )

        return cleaned
