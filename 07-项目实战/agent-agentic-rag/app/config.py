from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AgenticRAGConfig:
    """Agentic RAG 项目配置。"""

    project_root: Path
    data_dir: Path

    # Embedding
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5"

    # 检索
    vector_top_k: int = 15
    bm25_top_k: int = 15
    hybrid_top_k: int = 10
    vector_weight: float = 0.5

    # 重排序
    reranker_model_name: str = "BAAI/bge-reranker-v2-m3"
    rerank_top_k: int = 5

    # Agent 控制参数
    max_retrieval_rounds: int = 3   # 最多检索轮数
    max_llm_calls: int = 8          # 最多 LLM 调用次数

    # LLM
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"

    def __post_init__(self) -> None:
        if not self.openai_api_key:
            self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not self.openai_base_url:
            self.openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        if self.openai_model == "gpt-4o-mini":
            self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
