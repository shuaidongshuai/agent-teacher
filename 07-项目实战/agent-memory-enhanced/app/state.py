from __future__ import annotations

from typing import Any, Dict, List
from typing_extensions import TypedDict


class MemoryState(TypedDict, total=False):
    """LangGraph 状态定义。"""

    # 对话
    messages: List[Dict[str, str]]  # [{"role": "user"/"assistant", "content": "..."}]
    current_input: str              # 当前用户输入

    # 短期记忆
    conversation_summary: str       # 对话压缩摘要
    recent_messages: List[Dict[str, str]]  # 保留的最近消息

    # 长期记忆
    relevant_memories: List[str]    # 从长期记忆中检索到的相关条目

    # 工作记忆
    working_memory: Dict[str, Any]  # 当前任务 scratch pad

    # 输出
    assistant_response: str         # 助手回复

    # 控制
    llm_call_count: int
    execution_log: List[str]
