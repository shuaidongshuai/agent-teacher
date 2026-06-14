from __future__ import annotations

"""
Prompt 模板加载与渲染。

所有 Prompt 模板统一放在项目根目录下的 prompts/ 中，
便于集中管理、调优和后续做多版本切换。
"""

from pathlib import Path


class PromptManager:
    """从 prompts/ 目录加载文本模板。"""

    def __init__(self, prompts_dir: Path) -> None:
        self.prompts_dir = prompts_dir

    @classmethod
    def from_project_root(cls, project_root: Path) -> "PromptManager":
        return cls(project_root / "prompts")

    def get(self, name: str) -> str:
        path = self.prompts_dir / f"{name}.txt"
        if not path.exists():
            raise FileNotFoundError(f"Prompt 模板不存在: {path}")
        return path.read_text(encoding="utf-8").strip()

    def render(self, name: str, **kwargs) -> str:
        return self.get(name).format(**kwargs)
