from __future__ import annotations

import unittest
from pathlib import Path

from app.nodes import make_nodes
from app.prompts import PromptManager


class DummyLLMClient:
    def __init__(self) -> None:
        self.json_calls = []
        self.text_calls = []
        self.json_responses = []

    def generate_json(self, messages):
        self.json_calls.append(messages)
        if self.json_responses:
            return self.json_responses.pop(0)
        return {
            "complexity": "moderate",
            "info_points": ["盈利能力", "研发投入"],
            "initial_query": "盈利能力 研发投入",
            "strategy_note": "先做综合检索",
        }

    def generate(self, messages, max_tokens=2048):
        self.text_calls.append((messages, max_tokens))
        return "ok"


class DummyKnowledgeBase:
    def search(self, query: str, top_k=None):
        return []


class PromptManagerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]

    def test_load_prompt_from_directory(self) -> None:
        manager = PromptManager.from_project_root(self.project_root)

        prompt = manager.get("analyze_query")

        self.assertIn("查询分析", prompt)
        self.assertIn("只返回 JSON", prompt)

    def test_render_prompt_with_variables(self) -> None:
        manager = PromptManager.from_project_root(self.project_root)

        prompt = manager.render(
            "evaluate_results",
            query="问题A",
            contexts="片段A",
            retrieval_count=1,
            max_rounds=3,
        )

        self.assertIn("问题A", prompt)
        self.assertIn("片段A", prompt)
        self.assertIn("1/3", prompt)


class NodesPromptUsageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.prompt_manager = PromptManager.from_project_root(self.project_root)
        self.llm = DummyLLMClient()
        self.kb = DummyKnowledgeBase()

    def test_analyze_query_uses_external_prompt_template(self) -> None:
        nodes = make_nodes(
            llm=self.llm,
            kb=self.kb,
            prompt_manager=self.prompt_manager,
        )

        result = nodes["analyze_query"](
            {
                "user_query": "分析盈利能力和研发投入",
                "execution_log": [],
                "llm_call_count": 0,
            }
        )

        self.assertEqual(result["current_query"], "盈利能力 研发投入")
        self.assertEqual(len(self.llm.json_calls), 1)
        first_message = self.llm.json_calls[0][0]
        self.assertEqual(first_message["role"], "system")
        self.assertIn("查询分析", first_message["content"])

    def test_decide_retrieval_can_skip_search(self) -> None:
        self.llm.json_responses = [
            {
                "need_retrieval": False,
                "reason": "这是寒暄，不需要检索知识库",
            }
        ]
        nodes = make_nodes(
            llm=self.llm,
            kb=self.kb,
            prompt_manager=self.prompt_manager,
        )

        result = nodes["decide_retrieval"](
            {
                "user_query": "你好",
                "current_query": "你好",
                "execution_log": [],
                "llm_call_count": 1,
            }
        )

        self.assertEqual(result["next_action"], "answer")
        self.assertEqual(result["needs_retrieval"], False)
        self.assertIn("不需要检索", result["execution_log"][-1])


if __name__ == "__main__":
    unittest.main()
