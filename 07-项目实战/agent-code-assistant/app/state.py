from __future__ import annotations

from typing import Any, Dict, List
from typing_extensions import TypedDict


class CodeAgentState(TypedDict, total=False):
    """LangGraph 状态定义。"""

    # 任务
    task_description: str
    task_type: str  # fix_bug / explain_code / add_feature

    # 代码上下文
    relevant_files: List[str]
    code_contents: Dict[str, str]  # {path: content}
    test_results: str

    # 计划
    diagnosis: str
    plan: List[Dict[str, Any]]
    current_step_index: int

    # 执行
    execution_history: List[Dict[str, Any]]  # 每步的操作和结果
    changes_made: List[str]  # 修改过的文件列表
    tool_call_count: int

    # 验证
    fix_round: int
    all_tests_passed: bool

    # 输出
    final_summary: str

    # 控制
    llm_call_count: int
    execution_log: List[str]
