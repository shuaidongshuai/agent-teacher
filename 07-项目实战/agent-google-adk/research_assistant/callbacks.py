"""capstone 用到的回调：输入护栏 + 工具审计日志。"""

from typing import Any, Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types

# 简单的主题黑名单（演示护栏）
BLOCKED_TOPICS = ["制造武器", "攻击他人系统"]


def input_guardrail(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """研究主题护栏：命中黑名单直接拒绝，不再调用模型。"""
    last_text = ""
    for content in reversed(llm_request.contents or []):
        if content.role == "user" and content.parts:
            last_text = "".join(p.text or "" for p in content.parts)
            break

    hit = next((t for t in BLOCKED_TOPICS if t in last_text), None)
    if hit:
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text=f"⚠️ 我不能就「{hit}」这类主题生成研究报告。")],
            )
        )
    return None


def tool_logger(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext
) -> Optional[dict]:
    """审计日志：记录每次工具调用（便于观测整条流水线）。"""
    print(f"[TOOL] {tool.name} <- {args}")
    return None
