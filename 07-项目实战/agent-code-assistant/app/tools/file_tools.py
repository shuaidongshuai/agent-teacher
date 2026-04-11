from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

from ..sandbox import Sandbox

logger = logging.getLogger(__name__)


def read_file(sandbox: Sandbox, path: str) -> Dict[str, str]:
    """读取文件内容。"""
    try:
        resolved = sandbox.validate_path(path)
        if not resolved.exists():
            return {"success": "false", "error": f"文件不存在: {path}"}
        if not resolved.is_file():
            return {"success": "false", "error": f"不是文件: {path}"}
        content = resolved.read_text(encoding="utf-8")
        return {"success": "true", "content": content, "path": str(resolved)}
    except PermissionError as e:
        return {"success": "false", "error": str(e)}


def write_file(sandbox: Sandbox, path: str, content: str) -> Dict[str, str]:
    """写入文件（完整覆盖）。"""
    try:
        resolved = sandbox.validate_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return {"success": "true", "path": str(resolved), "chars_written": str(len(content))}
    except PermissionError as e:
        return {"success": "false", "error": str(e)}


def list_dir(sandbox: Sandbox, path: str = ".") -> Dict[str, str]:
    """列出目录内容。"""
    try:
        resolved = sandbox.validate_path(path)
        if not resolved.exists():
            return {"success": "false", "error": f"目录不存在: {path}"}
        if not resolved.is_dir():
            return {"success": "false", "error": f"不是目录: {path}"}

        entries = []
        for item in sorted(resolved.iterdir()):
            prefix = "[DIR] " if item.is_dir() else "[FILE]"
            rel_path = item.relative_to(sandbox.root_dir)
            entries.append(f"{prefix} {rel_path}")

        return {"success": "true", "entries": "\n".join(entries)}
    except PermissionError as e:
        return {"success": "false", "error": str(e)}
