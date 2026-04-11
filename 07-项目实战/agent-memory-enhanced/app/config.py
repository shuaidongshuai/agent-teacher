from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MemoryAgentConfig:
    """记忆增强 Agent 配置。"""

    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent)

    # LLM
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"

    # Embedding（用于长期记忆）
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5"

    # 短期记忆
    short_term_max_messages: int = 20  # 超过此数量触发压缩
    short_term_keep_recent: int = 6    # 压缩时保留最近 N 条

    # 长期记忆
    long_term_top_k: int = 5  # 语义检索返回 top-k

    # Agent 控制
    max_turns: int = 20  # 最大对话轮数
    max_llm_calls: int = 50  # 最大 LLM 调用次数

    def __post_init__(self) -> None:
        if not self.openai_api_key:
            self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not self.openai_base_url:
            self.openai_base_url = os.getenv(
                "OPENAI_BASE_URL", "https://api.openai.com/v1"
            )
        if self.openai_model == "gpt-4o-mini":
            self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    @property
    def data_dir(self) -> Path:
        return self.project_root / "data"

    @property
    def memory_dir(self) -> Path:
        p = self.project_root / "data" / "memory_store"
        p.mkdir(parents=True, exist_ok=True)
        return p
