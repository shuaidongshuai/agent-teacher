from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from ..sandbox import Sandbox


def search_code(sandbox: Sandbox, pattern: str, path: str = ".") -> Dict[str, str]:
    """
    在代码中搜索模式（类似 grep）。

    Args:
        sandbox: 沙箱实例
        pattern: 正则表达式模式
        path: 搜索目录（相对于沙箱根目录）
    """
    try:
        resolved = sandbox.validate_path(path)
    except PermissionError as e:
        return {"success": "false", "error": str(e)}

    if not resolved.exists():
        return {"success": "false", "error": f"路径不存在: {path}"}

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return {"success": "false", "error": f"无效的正则表达式: {e}"}

    matches: List[str] = []
    search_dir = resolved if resolved.is_dir() else resolved.parent
    files = [resolved] if resolved.is_file() else list(search_dir.rglob("*.py"))

    for file_path in files:
        if not file_path.is_file():
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
            for line_no, line in enumerate(content.split("\n"), 1):
                if regex.search(line):
                    rel = file_path.relative_to(sandbox.root_dir)
                    matches.append(f"{rel}:{line_no}: {line.strip()}")
        except (UnicodeDecodeError, PermissionError):
            continue

    if not matches:
        return {"success": "true", "matches": "（无匹配结果）", "count": "0"}

    # 限制结果数
    if len(matches) > 50:
        matches = matches[:50]
        matches.append(f"... [结果过多，仅显示前50条]")

    return {
        "success": "true",
        "matches": "\n".join(matches),
        "count": str(len(matches)),
    }
