from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CodeAgentConfig:
    """Code Agent 配置。"""

    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent)

    # LLM
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"

    # 沙箱
    sandbox_root: str = "data/sample_project"  # 允许操作的目录
    command_timeout: int = 30  # 命令执行超时（秒）
    max_output_chars: int = 2000  # 命令输出截断长度
    allowed_commands: tuple = ("python", "pytest", "pip", "cat", "ls", "echo")

    # Agent 控制
    max_fix_rounds: int = 3     # 最多修复轮数
    max_tool_calls: int = 10    # 最多工具调用次数
    max_llm_calls: int = 8      # 最多 LLM 调用次数

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
    def sandbox_path(self) -> Path:
        return self.project_root / self.sandbox_root
