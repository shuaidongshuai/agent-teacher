from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def load_eval_set(path: str | Path) -> List[Dict[str, Any]]:
    """加载评测集 JSON 文件。"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"评测集文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"评测集格式错误，期望 list，实际为 {type(data).__name__}")

    logger.info("已加载评测集: %s (%d 条)", path.name, len(data))
    return data


def validate_eval_set(
    data: List[Dict[str, Any]], required_fields: List[str]
) -> List[str]:
    """
    校验评测集格式。

    Returns:
        错误信息列表，空列表表示校验通过
    """
    errors = []
    for i, item in enumerate(data):
        for field in required_fields:
            if field not in item:
                errors.append(f"第 {i+1} 条缺少字段: {field}")
    return errors
