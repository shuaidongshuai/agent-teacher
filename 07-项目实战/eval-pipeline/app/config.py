from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EvalConfig:
    """评测 Pipeline 配置。"""

    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent)

    # LLM（用于 LLM-as-Judge）
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"

    # LLM Judge 评分
    llm_judge_temperature: float = 0
    llm_judge_max_score: int = 5

    # RAG 指标
    recall_k: int = 5
    mrr_k: int = 10

    # 输出
    output_dir: str = "output"

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
    def output_path(self) -> Path:
        p = self.project_root / self.output_dir
        p.mkdir(parents=True, exist_ok=True)
        return p
