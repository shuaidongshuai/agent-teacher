from __future__ import annotations

from typing import Any, Dict, List


class WorkingMemory:
    """
    工作记忆：结构化 scratch pad。

    存储当前任务的临时推理状态，注入到 system prompt 中帮助 LLM 保持聚焦。
    """

    def __init__(self) -> None:
        self.current_goal: str = "自由对话"
        self.key_facts: List[str] = []
        self.pending_questions: List[str] = []
        self.reasoning_steps: List[str] = []

    def update(self, data: Dict[str, Any]) -> None:
        """从 LLM 输出更新工作记忆。"""
        if "current_goal" in data:
            self.current_goal = data["current_goal"]
        if "key_facts" in data:
            self.key_facts = data["key_facts"][:10]  # 限制数量
        if "pending_questions" in data:
            self.pending_questions = data["pending_questions"][:5]
        if "reasoning_steps" in data:
            self.reasoning_steps = data["reasoning_steps"][:5]

    def to_text(self) -> str:
        """生成用于注入 system prompt 的文本。"""
        parts = [f"当前目标: {self.current_goal}"]

        if self.key_facts:
            facts = "\n".join(f"  - {f}" for f in self.key_facts)
            parts.append(f"关键事实:\n{facts}")

        if self.pending_questions:
            qs = "\n".join(f"  - {q}" for q in self.pending_questions)
            parts.append(f"待解决问题:\n{qs}")

        if self.reasoning_steps:
            steps = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(self.reasoning_steps))
            parts.append(f"推理步骤:\n{steps}")

        return "\n".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_goal": self.current_goal,
            "key_facts": self.key_facts,
            "pending_questions": self.pending_questions,
            "reasoning_steps": self.reasoning_steps,
        }

    def reset(self) -> None:
        """重置工作记忆。"""
        self.current_goal = "自由对话"
        self.key_facts.clear()
        self.pending_questions.clear()
        self.reasoning_steps.clear()
