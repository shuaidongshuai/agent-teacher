from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class Sandbox:
    """
    沙箱管理器。

    限制文件操作和命令执行的范围，防止 Agent 越权操作。
    """

    def __init__(
        self,
        root_dir: Path,
        allowed_commands: tuple = ("python", "pytest", "pip", "cat", "ls", "echo"),
        timeout: int = 30,
        max_output_chars: int = 2000,
    ) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.allowed_commands = allowed_commands
        self.timeout = timeout
        self.max_output_chars = max_output_chars

        # 确保沙箱目录存在
        if not self.root_dir.exists():
            raise FileNotFoundError(f"沙箱目录不存在: {self.root_dir}")

    def validate_path(self, path: str) -> Path:
        """
        验证路径是否在沙箱内。

        Returns:
            解析后的绝对路径

        Raises:
            PermissionError: 路径不在沙箱内
        """
        # 处理相对路径
        if not os.path.isabs(path):
            resolved = (self.root_dir / path).resolve()
        else:
            resolved = Path(path).resolve()

        # 检查是否在沙箱目录内
        try:
            resolved.relative_to(self.root_dir)
        except ValueError:
            raise PermissionError(
                f"路径不在沙箱范围内: {path}\n"
                f"允许的根目录: {self.root_dir}"
            )

        return resolved

    def validate_command(self, cmd: str) -> None:
        """
        验证命令是否在白名单内。

        Raises:
            PermissionError: 命令不在白名单内
        """
        # 提取命令名（第一个词）
        cmd_name = cmd.strip().split()[0] if cmd.strip() else ""

        # 检查是否在白名单
        if not any(cmd_name.startswith(allowed) for allowed in self.allowed_commands):
            raise PermissionError(
                f"命令不在白名单内: {cmd_name}\n"
                f"允许的命令: {', '.join(self.allowed_commands)}"
            )

    def truncate_output(self, output: str) -> str:
        """截断过长的输出。"""
        if len(output) > self.max_output_chars:
            truncated = output[: self.max_output_chars]
            truncated += f"\n\n... [输出已截断，共 {len(output)} 字符，显示前 {self.max_output_chars} 字符]"
            return truncated
        return output
