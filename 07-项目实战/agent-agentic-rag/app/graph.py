from __future__ import annotations

"""
Agentic RAG LangGraph 图构建。

图的拓扑结构：
    START → analyze_query → retrieve → evaluate_results ─┬─→ refine_query → retrieve
                                                          ├─→ retrieve（换 query 直接重试）
                                                          └─→ generate_answer → format_output → END

核心设计：
1. evaluate_results 是唯一的条件路由节点
2. refine_query 和 retrieve 形成循环，但受 max_rounds 约束
3. 所有决策都记录在 execution_log 中，方便教学观察
"""

import logging
from typing import Any, Dict

from app.config import AgenticRAGConfig
from app.knowledge_base import KnowledgeBase
from app.llm_client import LLMClient
from app.nodes import make_nodes
from app.state import AgenticRAGState

logger = logging.getLogger(__name__)


def route_after_evaluation(state: AgenticRAGState) -> str:
    """
    条件路由函数：根据 evaluate_results 的决策选择下一个节点。

    这个函数被 LangGraph 的 add_conditional_edges 调用，
    决定图的执行路径。
    """
    action = state.get("next_action", "answer")
    logger.info("路由决策: %s", action)
    if action == "refine_query":
        return "refine_query"
    elif action == "retrieve":
        return "retrieve"
    else:
        return "generate_answer"


def build_graph(config: AgenticRAGConfig, kb: KnowledgeBase):
    """
    构建 Agentic RAG 的 LangGraph 图。

    返回编译后的 graph，可以直接调用 graph.invoke(state)。
    """
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        raise ImportError("请安装 langgraph: pip install langgraph>=0.2.0")

    # 创建 LLM 客户端
    llm = LLMClient(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        model=config.openai_model,
    )

    # 创建节点函数
    nodes = make_nodes(
        llm=llm,
        kb=kb,
        max_rounds=config.max_retrieval_rounds,
        max_llm_calls=config.max_llm_calls,
    )

    # ── 构建图 ──
    graph = StateGraph(AgenticRAGState)

    # 添加节点
    graph.add_node("analyze_query", nodes["analyze_query"])
    graph.add_node("retrieve", nodes["retrieve"])
    graph.add_node("evaluate_results", nodes["evaluate_results"])
    graph.add_node("refine_query", nodes["refine_query"])
    graph.add_node("generate_answer", nodes["generate_answer"])
    graph.add_node("format_output", nodes["format_output"])

    # 添加边
    graph.add_edge(START, "analyze_query")
    graph.add_edge("analyze_query", "retrieve")
    graph.add_edge("retrieve", "evaluate_results")

    # 条件路由：evaluate_results 的输出决定走向
    graph.add_conditional_edges(
        "evaluate_results",
        route_after_evaluation,
        {
            "refine_query": "refine_query",
            "retrieve": "retrieve",
            "generate_answer": "generate_answer",
        },
    )

    graph.add_edge("refine_query", "retrieve")
    graph.add_edge("generate_answer", "format_output")
    graph.add_edge("format_output", END)

    # 编译
    compiled = graph.compile()
    logger.info("Agentic RAG 图编译完成")
    return compiled, llm
