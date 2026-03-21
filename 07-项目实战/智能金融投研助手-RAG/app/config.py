from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProjectConfig:
    """
    保存项目里常用的路径和默认阈值。

    之所以先做成 dataclass，是为了后面扩展到多环境配置时更清晰。
    """

    project_root: Path
    data_dir: Path
    max_chars: int = 1200
    min_chars: int = 200
    similarity_threshold: float = 0.78
