from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol, runtime_checkable


@dataclass
class EvalResult:
    """单条评测结果。"""

    score: float  # 0.0 ~ 1.0
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalSummary:
    """评测集汇总结果。"""

    evaluator_name: str
    total: int
    passed: int
    avg_score: float
    results: List[EvalResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0


@runtime_checkable
class BaseEvaluator(Protocol):
    """评估器协议。所有评估器必须实现此接口。"""

    name: str

    def evaluate(self, prediction: str, reference: str, **kwargs: Any) -> EvalResult:
        """
        评估单条预测结果。

        Args:
            prediction: 模型输出
            reference: 参考答案
            **kwargs: 额外参数（如 retrieved_contexts, ground_truth_contexts 等）

        Returns:
            EvalResult: 评测结果
        """
        ...
