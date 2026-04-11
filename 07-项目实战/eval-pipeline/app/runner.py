from __future__ import annotations

import logging
import sys
from typing import Any, Callable, Dict, List, Optional

from .evaluators.base import EvalResult, EvalSummary

logger = logging.getLogger(__name__)


class EvalRunner:
    """
    评测运行器。

    加载评测集 → 对每条数据调用评估器 → 收集结果。
    """

    def run(
        self,
        eval_set: List[Dict[str, Any]],
        evaluators: List[Any],
        predict_fn: Optional[Callable[[str], str]] = None,
    ) -> Dict[str, EvalSummary]:
        """
        运行评测。

        Args:
            eval_set: 评测数据列表
            evaluators: 评估器列表
            predict_fn: 可选的预测函数。传入时自动生成 prediction；
                       不传则使用数据中的 prediction 字段

        Returns:
            Dict[evaluator_name, EvalSummary]
        """
        summaries: Dict[str, EvalSummary] = {}

        for evaluator in evaluators:
            results: List[EvalResult] = []
            passed_count = 0
            total_score = 0.0

            print(f"\n{'='*60}")
            print(f"评估器: {evaluator.name}")
            print(f"{'='*60}")

            for i, item in enumerate(eval_set):
                # 获取 prediction
                prediction = self._get_prediction(item, predict_fn)
                if prediction is None:
                    logger.warning("第 %d 条无 prediction，跳过", i + 1)
                    continue

                # 获取 reference
                reference = item.get("reference", item.get("reference_answer", ""))

                # 构造 kwargs
                kwargs = {k: v for k, v in item.items()
                          if k not in ("prediction", "reference", "reference_answer", "evaluators")}

                try:
                    result = evaluator.evaluate(prediction, reference, **kwargs)
                except Exception as e:
                    logger.error("第 %d 条评估失败: %s", i + 1, e)
                    result = EvalResult(
                        score=0.0, passed=False, details={"error": str(e)}
                    )

                results.append(result)
                total_score += result.score
                if result.passed:
                    passed_count += 1

                # 打印进度
                status = "✓" if result.passed else "✗"
                item_id = item.get("id", f"#{i+1}")
                print(f"  [{status}] {item_id}: score={result.score:.2f}")

            total = len(results)
            avg_score = total_score / total if total > 0 else 0.0

            summary = EvalSummary(
                evaluator_name=evaluator.name,
                total=total,
                passed=passed_count,
                avg_score=avg_score,
                results=results,
            )
            summaries[evaluator.name] = summary

            print(f"\n  汇总: {passed_count}/{total} 通过, 平均分={avg_score:.3f}")

        return summaries

    @staticmethod
    def _get_prediction(
        item: Dict[str, Any],
        predict_fn: Optional[Callable[[str], str]],
    ) -> Optional[str]:
        """获取预测结果：优先使用 predict_fn，其次使用数据中的 prediction 字段。"""
        if predict_fn is not None:
            input_text = item.get("input", item.get("query", ""))
            if input_text:
                return predict_fn(input_text)

        return item.get("prediction")
