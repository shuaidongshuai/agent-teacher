from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProjectConfig:
    """
    保存项目里常用的路径和默认阈值。

    之所以先做成 dataclass，是为了后面扩展到多环境配置时更清晰。
    配置分为几组：切片参数、Embedding 参数、检索参数、重排序参数、LLM 参数。
    """

    # ── 路径 ──
    project_root: Path
    data_dir: Path

    # ── 切片参数 ──
    max_chars: int = 1200
    min_chars: int = 200
    similarity_threshold: float = 0.78

    # ── Embedding 参数 ──
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5"

    # ── 检索参数 ──
    vector_top_k: int = 15
    bm25_top_k: int = 15
    hybrid_top_k: int = 10
    vector_weight: float = 0.5  # RRF 融合时向量检索的权重

    # ── 重排序参数 ──
    reranker_model_name: str = "BAAI/bge-reranker-v2-m3"
    rerank_top_k: int = 5

    # ── LLM 参数（从环境变量读取） ──
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"

    def __post_init__(self) -> None:
        """从环境变量补充 LLM 配置。"""
        if not self.openai_api_key:
            self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not self.openai_base_url:
            self.openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        if not self.openai_model:
            self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
