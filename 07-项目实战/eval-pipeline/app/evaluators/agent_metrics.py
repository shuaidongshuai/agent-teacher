from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import EvalResult

logger = logging.getLogger(__name__)

TASK_COMPLETION_PROMPT = """你是一个任务完成度评估专家。请判断 Agent 的输出是否完成了给定任务。

## 任务描述
{task_description}

## 期望结果
{expected_outcome}

## Agent 实际输出
{agent_output}

## 输出要求

请严格按以下 JSON 格式输出：

```json
{{
    "completed": true或false,
    "completion_score": <0.0到1.0的浮点数>,
    "reasoning": "<简要判断理由，50字以内>"
}}
```"""


class AgentMetricsEvaluator:
    """
    Agent 行为质量评估器。

    评估三个维度：
    1. 任务完成率 — LLM 判断任务是否完成（需要 LLMClient）
    2. 工具调用匹配度 — 对比实际调用 vs 期望调用
    3. 步数效率 — 实际步数 vs 期望步数的比值
    """

    name: str = "agent_metrics"

    def __init__(self, llm_client: Optional[Any] = None):
        self.llm_client = llm_client

    def evaluate(self, prediction: str, reference: str, **kwargs: Any) -> EvalResult:
        """
        评估 Agent 输出质量。

        kwargs 中可提供：
        - task_description: str — 任务描述
        - expected_outcome: str — 期望结果描述
        - actual_tool_calls: List[str] — Agent 实际调用的工具列表
        - expected_tool_calls: List[str] — 期望的工具调用列表
        - actual_steps: int — Agent 实际执行步数
        - expected_steps: int — 期望步数
        """
        scores: Dict[str, float] = {}
        details: Dict[str, Any] = {}

        # 1. 任务完成率
        task_score = self._eval_task_completion(prediction, reference, **kwargs)
        scores["task_completion"] = task_score["score"]
        details["task_completion"] = task_score

        # 2. 工具调用匹配度
        tool_score = self._eval_tool_calls(**kwargs)
        scores["tool_accuracy"] = tool_score["score"]
        details["tool_accuracy"] = tool_score

        # 3. 步数效率
        step_score = self._eval_step_efficiency(**kwargs)
        scores["step_efficiency"] = step_score["score"]
        details["step_efficiency"] = step_score

        # 综合得分：加权平均
        weights = {"task_completion": 0.5, "tool_accuracy": 0.3, "step_efficiency": 0.2}
        total_score = sum(scores[k] * weights[k] for k in weights)

        return EvalResult(
            score=total_score,
            passed=scores["task_completion"] >= 0.6,
            details={
                "sub_scores": scores,
                "weights": weights,
                **details,
            },
        )

    def _eval_task_completion(
        self, prediction: str, reference: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """使用 LLM 判断任务完成度。"""
        if self.llm_client is None:
            # 无 LLM 时回退到包含匹配
            ref_lower = reference.lower().strip()
            pred_lower = prediction.lower().strip()
            matched = ref_lower in pred_lower if ref_lower else False
            return {
                "score": 1.0 if matched else 0.0,
                "method": "contains_fallback",
                "matched": matched,
            }

        task_desc = kwargs.get("task_description", reference)
        expected = kwargs.get("expected_outcome", reference)

        prompt = TASK_COMPLETION_PROMPT.format(
            task_description=task_desc,
            expected_outcome=expected,
            agent_output=prediction,
        )

        try:
            result = self.llm_client.generate_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            score = float(result.get("completion_score", 0.0))
            return {
                "score": min(1.0, max(0.0, score)),
                "method": "llm_judge",
                "completed": result.get("completed", False),
                "reasoning": result.get("reasoning", ""),
            }
        except Exception as e:
            logger.warning("Agent 任务完成度评估失败: %s", e)
            return {"score": 0.0, "method": "llm_judge_error", "error": str(e)}

    @staticmethod
    def _eval_tool_calls(**kwargs: Any) -> Dict[str, Any]:
        """评估工具调用匹配度。"""
        actual = kwargs.get("actual_tool_calls", [])
        expected = kwargs.get("expected_tool_calls", [])

        if not expected:
            return {"score": 1.0, "method": "no_expected_tools", "skipped": True}

        # 计算集合匹配度
        actual_set = set(actual)
        expected_set = set(expected)

        if not expected_set:
            return {"score": 1.0, "method": "empty_expected"}

        # 召回：期望的工具中有多少被调用了
        recall = len(actual_set & expected_set) / len(expected_set)
        # 精确：调用的工具中有多少是期望的
        precision = len(actual_set & expected_set) / len(actual_set) if actual_set else 0.0
        # F1
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        return {
            "score": f1,
            "method": "set_f1",
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "actual": actual,
            "expected": expected,
            "hits": list(actual_set & expected_set),
            "missed": list(expected_set - actual_set),
            "extra": list(actual_set - expected_set),
        }

    @staticmethod
    def _eval_step_efficiency(**kwargs: Any) -> Dict[str, Any]:
        """评估步数效率。"""
        actual_steps = kwargs.get("actual_steps", 0)
        expected_steps = kwargs.get("expected_steps", 0)

        if expected_steps <= 0:
            return {"score": 1.0, "method": "no_expected_steps", "skipped": True}

        if actual_steps <= 0:
            return {"score": 0.0, "method": "no_actual_steps"}

        # 效率 = min(expected/actual, 1.0)，步数越少越好
        efficiency = min(expected_steps / actual_steps, 1.0)

        return {
            "score": round(efficiency, 4),
            "method": "step_ratio",
            "actual_steps": actual_steps,
            "expected_steps": expected_steps,
        }
