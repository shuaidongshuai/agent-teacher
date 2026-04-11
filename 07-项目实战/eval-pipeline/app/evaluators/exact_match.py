from __future__ import annotations

import re
from typing import Any, List, Optional

from .base import EvalResult


class ExactMatchEvaluator:
    """
    精确匹配评估器。

    支持三种模式：
    1. exact — 完全一致
    2. contains — prediction 包含 reference
    3. keywords — prediction 包含所有指定关键词
    """

    name: str = "exact_match"

    def __init__(self, mode: str = "contains", keywords: Optional[List[str]] = None):
        """
        Args:
            mode: "exact" | "contains" | "keywords"
            keywords: 当 mode="keywords" 时，需要匹配的关键词列表
        """
        self.mode = mode
        self.keywords = keywords or []

    def evaluate(self, prediction: str, reference: str, **kwargs: Any) -> EvalResult:
        pred_clean = self._normalize(prediction)
        ref_clean = self._normalize(reference)

        if self.mode == "exact":
            matched = pred_clean == ref_clean
            score = 1.0 if matched else 0.0
            details = {"mode": "exact", "matched": matched}

        elif self.mode == "contains":
            matched = ref_clean in pred_clean
            score = 1.0 if matched else 0.0
            details = {"mode": "contains", "matched": matched}

        elif self.mode == "keywords":
            kw_list = self.keywords or kwargs.get("keywords", [])
            if not kw_list:
                # 没有关键词列表，回退到 contains 模式
                matched = ref_clean in pred_clean
                score = 1.0 if matched else 0.0
                details = {"mode": "keywords_fallback_contains", "matched": matched}
            else:
                hits = []
                for kw in kw_list:
                    kw_clean = self._normalize(kw)
                    hits.append(kw_clean in pred_clean)
                hit_count = sum(hits)
                score = hit_count / len(kw_list)
                matched = all(hits)
                details = {
                    "mode": "keywords",
                    "keywords": kw_list,
                    "hits": dict(zip(kw_list, hits)),
                    "hit_rate": score,
                }
        else:
            raise ValueError(f"未知匹配模式: {self.mode}")

        return EvalResult(
            score=score,
            passed=matched,
            details=details,
        )

    @staticmethod
    def _normalize(text: str) -> str:
        """标准化文本：去除多余空白、统一小写。"""
        text = re.sub(r"\s+", " ", text.strip().lower())
        return text
