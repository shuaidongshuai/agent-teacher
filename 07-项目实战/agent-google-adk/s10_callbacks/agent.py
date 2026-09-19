"""关卡 10：回调（Callbacks）—— 护栏、日志与拦截

学习目标：
  - 理解 ADK 的回调钩子：在"模型调用前后""工具调用前后""Agent 执行前后"插入逻辑
  - before_model_callback 返回一个 LlmResponse 就能【拦截】本次模型调用（做输入护栏）
  - before_tool_callback 返回一个 dict 就能【跳过】工具执行（做工具级管控 / 缓存）
  - 用途：安全护栏、审计日志、参数校验、限流、脱敏

运行：adk run s10_callbacks   或   adk web 后选择本关卡
（试试问天气，会看到工具日志；输入含"密码"等敏感词会被护栏拦下）
"""

import os
from typing import Any, Optional

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")

# 简单的敏感词黑名单（演示用）
BLOCKED_WORDS = ["密码", "身份证", "银行卡号"]


def guardrail_before_model(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """输入护栏：调用模型前检查用户最新消息，命中敏感词就直接拦截。"""
    # 取出最近一条用户消息的文本
    last_text = ""
    for content in reversed(llm_request.contents or []):
        if content.role == "user" and content.parts:
            last_text = "".join(p.text or "" for p in content.parts)
            break

    hit = next((w for w in BLOCKED_WORDS if w in last_text), None)
    if hit:
        # 返回 LlmResponse => 跳过真正的模型调用，直接把这段话作为回复
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text=f"⚠️ 出于安全考虑，我不能处理涉及「{hit}」的请求。")],
            )
        )
    return None  # 返回 None => 正常继续调用模型


def log_before_tool(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext
) -> Optional[dict]:
    """工具审计日志：每次调用工具前打印工具名与参数。"""
    print(f"[TOOL LOG] 调用工具 {tool.name}，参数={args}")
    return None  # 返回 None => 正常执行工具（返回 dict 则会跳过工具、直接用该 dict 当结果）


def get_weather(city: str) -> dict:
    """查询城市天气（假数据演示）。"""
    return {"status": "success", "report": f"{city}今天晴，20℃"}


root_agent = Agent(
    name="guarded_agent",
    model=MODEL,
    description="带输入护栏和工具日志的天气助手。",
    instruction="你是天气助手，用户问天气就调用 get_weather 回答。",
    tools=[get_weather],
    # 注册回调钩子
    before_model_callback=guardrail_before_model,
    before_tool_callback=log_before_tool,
)
