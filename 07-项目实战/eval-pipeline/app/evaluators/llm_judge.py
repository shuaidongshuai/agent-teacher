from __future__ import annotations

import logging
from typing import Any, Optional

from .base import EvalResult

logger = logging.getLogger(__name__)

LLM_JUDGE_PROMPT = """你是一个专业的答案质量评估专家。请根据以下标准对模型回答进行评分。

## 评分标准（1-5分）

- 5分：完全正确，覆盖所有要点，表述清晰
- 4分：基本正确，覆盖主要要点，有小瑕疵
- 3分：部分正确，遗漏了一些重要信息
- 2分：有明显错误或重大遗漏
- 1分：完全错误或与问题无关

## 输入

**问题**：{question}

**参考答案**：{reference}

**模型回答**：{prediction}

## 输出要求

请严格按以下 JSON 格式输出，不要有其他内容：

```json
{{
    "score": <1-5的整数>,
    "reasoning": "<简要评分理由，50字以内>"
}}
```"""


class LLMJudgeEvaluator:
    """
    LLM-as-Judge 评估器。

    使用 LLM 对模型输出打 1-5 分，并给出评分理由。
    需要传入 LLMClient 实例。
    """

    name: str = "llm_judge"

    def __init__(self, llm_client: Optional[Any] = None, max_score: int = 5):
        self.llm_client = llm_client
        self.max_score = max_score

    def evaluate(self, prediction: str, reference: str, **kwargs: Any) -> EvalResult:
        if self.llm_client is None:
            return EvalResult(
                score=0.0,
                passed=False,
                details={"error": "未配置 LLMClient，跳过 LLM Judge 评估"},
            )

        question = kwargs.get("question", kwargs.get("input", ""))

        prompt = LLM_JUDGE_PROMPT.format(
            question=question,
            reference=reference,
            prediction=prediction,
        )

        try:
            result = self.llm_client.generate_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )

            raw_score = int(result.get("score", 1))
            raw_score = max(1, min(self.max_score, raw_score))
            normalized_score = raw_score / self.max_score
            reasoning = result.get("reasoning", "")

            return EvalResult(
                score=normalized_score,
                passed=raw_score >= 4,
                details={
                    "raw_score": raw_score,
                    "max_score": self.max_score,
                    "reasoning": reasoning,
                },
            )

        except Exception as e:
            logger.warning("LLM Judge 评估失败: %s", e)
            return EvalResult(
                score=0.0,
                passed=False,
                details={"error": str(e)},
            )
