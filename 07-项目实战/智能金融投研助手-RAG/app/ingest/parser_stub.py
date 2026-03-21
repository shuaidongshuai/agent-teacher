from __future__ import annotations

from typing import List

from .models import Block


class PDFParserStub:
    """
    这是一个占位解析器。

    当前项目第一阶段重点不是 PDF 解析本身，而是：
    - 清洗
    - 结构化
    - 语义切片

    所以后面你可以把这里替换成：
    - PyMuPDF
    - pdfplumber
    - OCR 解析器
    """

    def parse(self, pdf_path: str) -> List[Block]:
        raise NotImplementedError("请在下一阶段用真实 PDF 解析逻辑替换这个 Stub。")
