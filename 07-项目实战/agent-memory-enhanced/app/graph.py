from __future__ import annotations

from typing import Any, Dict

from .llm_client import LLMClient
from .memory.long_term import LongTermMemory
from .memory.short_term import ShortTermMemory
from .memory.working import WorkingMemory
from .nodes import make_nodes
from .state import MemoryState


def build_graph(
    llm: LLMClient,
    short_term: ShortTermMemory,
    long_term: LongTermMemory,
    working: WorkingMemory,
):
    """
    构建 LangGraph 图。

    图拓扑:
    START → load_memory → chat → extract_and_store → compress_if_needed → END
    """
    from langgraph.graph import END, START, StateGraph

    nodes = make_nodes(llm, short_term, long_term, working)

    graph = StateGraph(MemoryState)

    # 添加节点
    for name, fn in nodes.items():
        graph.add_node(name, fn)

    # 添加边
    graph.add_edge(START, "load_memory")
    graph.add_edge("load_memory", "chat")
    graph.add_edge("chat", "extract_and_store")
    graph.add_edge("extract_and_store", "compress_if_needed")
    graph.add_edge("compress_if_needed", END)

    return graph.compile()


def run_turn(
    compiled_graph: Any,
    user_input: str,
    previous_state: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    执行一轮对话。

    Args:
        compiled_graph: 编译后的 LangGraph 图
        user_input: 用户输入
        previous_state: 上一轮的状态（用于传递 llm_call_count 等）

    Returns:
        更新后的状态
    """
    initial_state: MemoryState = {
        "current_input": user_input,
        "messages": previous_state.get("messages", []) if previous_state else [],
        "conversation_summary": previous_state.get("conversation_summary", "") if previous_state else "",
        "relevant_memories": [],
        "working_memory": previous_state.get("working_memory", {}) if previous_state else {},
        "assistant_response": "",
        "llm_call_count": previous_state.get("llm_call_count", 0) if previous_state else 0,
        "execution_log": [],
    }

    result = compiled_graph.invoke(initial_state)
    return result
