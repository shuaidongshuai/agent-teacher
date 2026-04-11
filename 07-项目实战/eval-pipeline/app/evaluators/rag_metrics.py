from __future__ import annotations

from typing import Any, List

from .base import EvalResult


class RAGMetricsEvaluator:
    """
    RAG 检索质量评估器。

    计算三个核心指标：
    1. Recall@K — 召回率：ground truth 文档在检索结果中命中的比例
    2. MRR — 平均倒数排名：第一个正确结果的排名倒数
    3. Context Precision — 上下文精确率：检索结果中相关文档的比例
    """

    name: str = "rag_metrics"

    def __init__(self, k: int = 5):
        self.k = k

    def evaluate(self, prediction: str, reference: str, **kwargs: Any) -> EvalResult:
        """
        评估 RAG 检索质量。

        kwargs 中需要提供：
        - retrieved_contexts: List[str] — 检索到的文档 ID 列表
        - ground_truth_contexts: List[str] — 正确的文档 ID 列表
        """
        retrieved = kwargs.get("retrieved_contexts", [])
        ground_truth = kwargs.get("ground_truth_contexts", [])

        if not ground_truth:
            return EvalResult(
                score=0.0,
                passed=False,
                details={"error": "未提供 ground_truth_contexts"},
            )

        # 截取 top-k
        retrieved_at_k = retrieved[: self.k]

        recall = self._recall_at_k(retrieved_at_k, ground_truth)
        mrr = self._mrr(retrieved, ground_truth)
        precision = self._context_precision(retrieved_at_k, ground_truth)

        # 综合得分：三个指标的加权平均
        score = 0.4 * recall + 0.3 * mrr + 0.3 * precision

        return EvalResult(
            score=score,
            passed=recall >= 0.5,
            details={
                "recall_at_k": round(recall, 4),
                "mrr": round(mrr, 4),
                "context_precision": round(precision, 4),
                "k": self.k,
                "retrieved_count": len(retrieved),
                "ground_truth_count": len(ground_truth),
                "hits": [ctx for ctx in retrieved_at_k if ctx in ground_truth],
            },
        )

    @staticmethod
    def _recall_at_k(retrieved: List[str], ground_truth: List[str]) -> float:
        """Recall@K：ground truth 中被检索到的比例。"""
        if not ground_truth:
            return 0.0
        gt_set = set(ground_truth)
        hits = sum(1 for ctx in retrieved if ctx in gt_set)
        return hits / len(ground_truth)

    @staticmethod
    def _mrr(retrieved: List[str], ground_truth: List[str]) -> float:
        """MRR：第一个正确结果的排名倒数。"""
        gt_set = set(ground_truth)
        for i, ctx in enumerate(retrieved):
            if ctx in gt_set:
                return 1.0 / (i + 1)
        return 0.0

    @staticmethod
    def _context_precision(retrieved: List[str], ground_truth: List[str]) -> float:
        """Context Precision：检索结果中相关文档的比例。"""
        if not retrieved:
            return 0.0
        gt_set = set(ground_truth)
        relevant = sum(1 for ctx in retrieved if ctx in gt_set)
        return relevant / len(retrieved)
