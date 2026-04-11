from __future__ import annotations

"""
Agentic RAG 图节点实现。

每个函数对应 LangGraph 图中的一个节点，接收 state、修改 state、返回更新。
这是 Agentic RAG 的核心逻辑所在。
"""

import logging
from typing import Any, Dict

from app.knowledge_base import KnowledgeBase
from app.llm_client import LLMClient
from app.prompts import (
    ANALYZE_QUERY_PROMPT,
    EVALUATE_RESULTS_PROMPT,
    GENERATE_ANSWER_PROMPT,
    REFINE_QUERY_PROMPT,
)
from app.state import AgenticRAGState

logger = logging.getLogger(__name__)


def make_nodes(llm: LLMClient, kb: KnowledgeBase, max_rounds: int = 3, max_llm_calls: int = 8):
    """
    创建所有图节点。

    使用闭包将 llm 和 kb 注入到节点函数中，
    避免在 state 中传递大对象。
    """

    def analyze_query(state: AgenticRAGState) -> Dict[str, Any]:
        """
        节点1: 分析用户查询。

        LLM 分析问题的复杂度和信息需求，制定初始检索策略。
        这一步决定了后续检索的起点。
        """
        query = state["user_query"]
        log = list(state.get("execution_log", []))
        log.append(f"[analyze_query] 开始分析: '{query}'")

        messages = [
            {"role": "system", "content": ANALYZE_QUERY_PROMPT},
            {"role": "user", "content": f"用户问题：{query}"},
        ]

        try:
            result = llm.generate_json(messages)
            complexity = result.get("complexity", "moderate")
            info_points = result.get("info_points", [query])
            initial_query = result.get("initial_query", query)
            strategy = result.get("strategy_note", "")

            log.append(f"[analyze_query] 复杂度={complexity}, 信息点={info_points}")
            log.append(f"[analyze_query] 初始检索 query: '{initial_query}'")
            log.append(f"[analyze_query] 策略: {strategy}")

            return {
                "complexity": complexity,
                "info_points": info_points,
                "current_query": initial_query,
                "query_history": [initial_query],
                "retrieval_count": 0,
                "accumulated_contexts": [],
                "execution_log": log,
                "llm_call_count": state.get("llm_call_count", 0) + 1,
            }

        except Exception as e:
            log.append(f"[analyze_query] 分析失败: {e}，使用原始 query")
            return {
                "complexity": "moderate",
                "info_points": [query],
                "current_query": query,
                "query_history": [query],
                "retrieval_count": 0,
                "accumulated_contexts": [],
                "execution_log": log,
                "llm_call_count": state.get("llm_call_count", 0) + 1,
            }

    def retrieve(state: AgenticRAGState) -> Dict[str, Any]:
        """
        节点2: 执行检索。

        这个节点不调用 LLM，直接使用 KnowledgeBase 执行混合检索+重排序。
        检索结果会累积到 accumulated_contexts 中（去重）。
        """
        query = state["current_query"]
        count = state.get("retrieval_count", 0) + 1
        accumulated = list(state.get("accumulated_contexts", []))
        log = list(state.get("execution_log", []))

        log.append(f"[retrieve] 第 {count} 轮检索, query: '{query}'")

        # 执行检索
        results = kb.search(query)
        log.append(f"[retrieve] 返回 {len(results)} 条结果")

        # 去重累积（按 chunk_id）
        existing_ids = {ctx["chunk_id"] for ctx in accumulated}
        new_count = 0
        for r in results:
            if r["chunk_id"] not in existing_ids:
                accumulated.append(r)
                existing_ids.add(r["chunk_id"])
                new_count += 1

        log.append(f"[retrieve] 新增 {new_count} 条，累计 {len(accumulated)} 条上下文")

        return {
            "retrieval_results": results,
            "retrieval_count": count,
            "accumulated_contexts": accumulated,
            "execution_log": log,
        }

    def evaluate_results(state: AgenticRAGState) -> Dict[str, Any]:
        """
        节点3: 评估检索结果。

        LLM 判断当前累积的上下文是否足以回答用户问题。
        这是 Agentic RAG 的核心决策点：
        - 信息充分 → 进入答案生成
        - 信息不足 → 改写 query 继续检索
        - 达到上限 → 强制用已有信息回答
        """
        query = state["user_query"]
        accumulated = state.get("accumulated_contexts", [])
        count = state.get("retrieval_count", 0)
        log = list(state.get("execution_log", []))
        llm_calls = state.get("llm_call_count", 0)

        # 安全控制：达到最大轮数或 LLM 调用上限
        if count >= max_rounds or llm_calls >= max_llm_calls - 1:
            reason = f"达到最大轮数({count}/{max_rounds})" if count >= max_rounds else f"达到 LLM 调用上限({llm_calls}/{max_llm_calls})"
            log.append(f"[evaluate_results] {reason}，强制进入答案生成")
            return {
                "next_action": "answer",
                "coverage_summary": "已用完检索机会，用现有信息尽力回答",
                "missing_info": [],
                "execution_log": log,
            }

        # 格式化上下文
        contexts_text = ""
        for i, ctx in enumerate(accumulated, 1):
            section = " > ".join(ctx["section_path"]) if ctx["section_path"] else "未知"
            pages = ", ".join(str(p) for p in ctx["page_span"])
            contexts_text += f"[片段{i}] 页{pages}, {section}\n{ctx['content']}\n\n"

        prompt = EVALUATE_RESULTS_PROMPT.format(
            query=query,
            contexts=contexts_text,
            retrieval_count=count,
            max_rounds=max_rounds,
        )

        messages = [
            {"role": "system", "content": "你是一个金融投研分析助手的结果评估模块。"},
            {"role": "user", "content": prompt},
        ]

        try:
            result = llm.generate_json(messages)
            next_action = result.get("next_action", "answer")
            coverage = result.get("coverage_summary", "")
            missing = result.get("missing_info", [])
            reasoning = result.get("reasoning", "")

            log.append(f"[evaluate_results] 判断: {next_action}")
            log.append(f"[evaluate_results] 覆盖: {coverage}")
            log.append(f"[evaluate_results] 缺失: {missing}")
            log.append(f"[evaluate_results] 理由: {reasoning}")

            # 合法性检查
            if next_action not in ("answer", "refine_query", "retrieve"):
                next_action = "answer"

            return {
                "next_action": next_action,
                "coverage_summary": coverage,
                "missing_info": missing,
                "execution_log": log,
                "llm_call_count": llm_calls + 1,
            }

        except Exception as e:
            log.append(f"[evaluate_results] 评估失败: {e}，默认生成答案")
            return {
                "next_action": "answer",
                "coverage_summary": "评估失败，用已有信息回答",
                "missing_info": [],
                "execution_log": log,
                "llm_call_count": llm_calls + 1,
            }

    def refine_query(state: AgenticRAGState) -> Dict[str, Any]:
        """
        节点4: 改写查询。

        当评估认为信息不足时，LLM 根据已有信息和缺失点生成新的检索 query。
        这体现了 Agentic RAG 的自适应能力——Agent 不是机械重试，
        而是有针对性地调整检索策略。
        """
        query = state["user_query"]
        query_history = list(state.get("query_history", []))
        coverage = state.get("coverage_summary", "")
        missing = state.get("missing_info", [])
        log = list(state.get("execution_log", []))
        llm_calls = state.get("llm_call_count", 0)

        prompt = REFINE_QUERY_PROMPT.format(
            query=query,
            query_history="\n".join(f"- {q}" for q in query_history),
            coverage_summary=coverage,
            missing_info="\n".join(f"- {m}" for m in missing),
        )

        messages = [
            {"role": "system", "content": "你是一个金融投研分析助手的查询改写模块。"},
            {"role": "user", "content": prompt},
        ]

        try:
            result = llm.generate_json(messages)
            new_query = result.get("new_query", missing[0] if missing else query)
            target = result.get("target_info", "")

            log.append(f"[refine_query] 新 query: '{new_query}'")
            log.append(f"[refine_query] 目标: {target}")
            query_history.append(new_query)

            return {
                "current_query": new_query,
                "query_history": query_history,
                "execution_log": log,
                "llm_call_count": llm_calls + 1,
            }

        except Exception as e:
            # 如果改写失败，用缺失信息的第一项作为 query
            fallback = missing[0] if missing else query
            log.append(f"[refine_query] 改写失败: {e}，使用 fallback: '{fallback}'")
            query_history.append(fallback)
            return {
                "current_query": fallback,
                "query_history": query_history,
                "execution_log": log,
                "llm_call_count": llm_calls + 1,
            }

    def generate_answer(state: AgenticRAGState) -> Dict[str, Any]:
        """
        节点5: 生成最终答案。

        基于所有累积的上下文，生成带引用的结构化回答。
        """
        query = state["user_query"]
        accumulated = state.get("accumulated_contexts", [])
        log = list(state.get("execution_log", []))
        llm_calls = state.get("llm_call_count", 0)

        log.append(f"[generate_answer] 基于 {len(accumulated)} 条上下文生成答案")

        # 构建上下文文本
        contexts_text = ""
        for i, ctx in enumerate(accumulated, 1):
            section = " > ".join(ctx["section_path"]) if ctx["section_path"] else "未知"
            pages = ", ".join(str(p) for p in ctx["page_span"])
            contexts_text += f"【参考文档 {i}】\n  来源: 页{pages}, {section}\n  内容: {ctx['content']}\n\n"

        system_prompt = GENERATE_ANSWER_PROMPT.format(contexts=contexts_text)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"用户问题：{query}"},
        ]

        try:
            answer = llm.generate(messages, max_tokens=4096)
            log.append(f"[generate_answer] 答案生成完成，{len(answer)} 字符")
            return {
                "final_answer": answer,
                "execution_log": log,
                "llm_call_count": llm_calls + 1,
            }

        except Exception as e:
            log.append(f"[generate_answer] 生成失败: {e}")
            fallback = "答案生成失败。以下是检索到的相关文档片段：\n\n"
            for i, ctx in enumerate(accumulated, 1):
                fallback += f"[{i}] {ctx['content'][:200]}...\n\n"
            return {
                "final_answer": fallback,
                "execution_log": log,
                "llm_call_count": llm_calls + 1,
            }

    def format_output(state: AgenticRAGState) -> Dict[str, Any]:
        """
        节点6: 格式化输出。

        整理最终的输出，包括答案、推理轨迹、检索统计。
        主要用于教学观察和调试。
        """
        log = list(state.get("execution_log", []))
        log.append("[format_output] 输出格式化完成")

        return {"execution_log": log}

    return {
        "analyze_query": analyze_query,
        "retrieve": retrieve,
        "evaluate_results": evaluate_results,
        "refine_query": refine_query,
        "generate_answer": generate_answer,
        "format_output": format_output,
    }
