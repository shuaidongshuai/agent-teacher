from __future__ import annotations

from typing import Any, Dict

from .config import CodeAgentConfig
from .llm_client import LLMClient
from .nodes import make_nodes
from .sandbox import Sandbox
from .state import CodeAgentState


def build_graph(llm: LLMClient, sandbox: Sandbox, config: CodeAgentConfig):
    """
    构建 LangGraph 图。

    图拓扑:
    START → analyze_task → plan_approach → execute_step → [循环执行所有步骤]
          → verify_result ─┬─ [通过] → summarize → END
                           └─ [失败且未超限] → plan_approach → execute_step → ...
    """
    from langgraph.graph import END, START, StateGraph

    nodes = make_nodes(
        llm, sandbox,
        max_fix_rounds=config.max_fix_rounds,
        max_tool_calls=config.max_tool_calls,
        max_llm_calls=config.max_llm_calls,
    )

    graph = StateGraph(CodeAgentState)

    # 添加节点
    for name, fn in nodes.items():
        graph.add_node(name, fn)

    # 边
    graph.add_edge(START, "analyze_task")
    graph.add_edge("analyze_task", "plan_approach")
    graph.add_edge("plan_approach", "execute_step")

    # execute_step 后：如果还有步骤则继续执行，否则去验证
    def route_after_execute(state: CodeAgentState) -> str:
        step_idx = state.get("current_step_index", 0)
        plan = state.get("plan", [])
        tool_count = state.get("tool_call_count", 0)
        max_tools = config.max_tool_calls

        if step_idx < len(plan) and tool_count < max_tools:
            return "execute_step"  # 继续执行下一步
        return "verify_result"  # 所有步骤完成，去验证

    graph.add_conditional_edges(
        "execute_step",
        route_after_execute,
        {"execute_step": "execute_step", "verify_result": "verify_result"},
    )

    # verify_result 后：通过则总结，失败则重新规划
    def route_after_verify(state: CodeAgentState) -> str:
        all_passed = state.get("all_tests_passed", False)
        fix_round = state.get("fix_round", 0)
        llm_count = state.get("llm_call_count", 0)

        if all_passed:
            return "summarize"
        if fix_round >= config.max_fix_rounds:
            return "summarize"  # 达到最大轮数，强制总结
        if llm_count >= config.max_llm_calls:
            return "summarize"  # 达到 LLM 调用上限
        return "plan_approach"  # 重新规划

    graph.add_conditional_edges(
        "verify_result",
        route_after_verify,
        {
            "summarize": "summarize",
            "plan_approach": "plan_approach",
        },
    )

    graph.add_edge("summarize", END)

    return graph.compile()
