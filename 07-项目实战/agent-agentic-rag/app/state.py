from __future__ import annotations

from typing import Any, Dict, List, TypedDict

import operator


class AgenticRAGState(TypedDict, total=False):
    """
    Agentic RAG 的 LangGraph 状态定义。

    这个状态在图的各个节点之间流转，记录了：
    - 用户输入
    - Agent 的推理过程
    - 检索历史和累积的上下文
    - 路由决策
    - 最终输出
    """

    # ── 用户输入 ──
    user_query: str

    # ── 查询分析结果 ──
    complexity: str                         # simple | moderate | complex
    info_points: List[str]                  # 需要获取的信息点

    # ── 检索状态 ──
    current_query: str                      # 当前用于检索的 query
    query_history: List[str]                # 所有用过的 query
    retrieval_count: int                    # 已检索轮数
    retrieval_results: List[Dict[str, Any]] # 最近一次检索结果
    accumulated_contexts: List[Dict[str, Any]]  # 所有累积的有效上下文（去重）

    # ── 评估与路由 ──
    next_action: str                        # answer | refine_query | retrieve
    coverage_summary: str                   # 当前信息覆盖摘要
    missing_info: List[str]                 # 缺失信息列表

    # ── 最终输出 ──
    final_answer: str

    # ── 执行日志（用于调试和教学观察） ──
    execution_log: List[str]
    llm_call_count: int
