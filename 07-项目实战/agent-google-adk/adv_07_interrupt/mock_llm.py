"""一个离线的「假模型」(BaseLlm)，让本关卡不配任何 API Key 也能把打断机制跑起来。

它不是真的在推理，而是用一套关键词规则「扮演」一个会做 function calling 的模型：
  - 看到「调研/研究/报告」等 -> 走【多工具流水线】：搜索 -> 统计 -> 写笔记 -> 汇总
    （一次任务里连续调用多个工具，中间有多个可打断点，方便观察中断/纠正）
  - 看到用户问搜索 -> 产出一个 web_search 的函数调用
  - 看到「停/算了」 -> 直接产出一句收尾文本，不再调用工具
  - 看到工具结果     -> 产出一句总结文本（单工具任务的终态）

关键点：它实现的是 ADK 的 BaseLlm 协议 ——
  `generate_content_async(llm_request, stream)` 是一个异步生成器，产出 LlmResponse。
因此 Agent / Runner / 工具执行 / 事件流 全都是**真正的 ADK 流程**，
只是把「大模型」这一环换成了确定性的本地实现，方便离线教学与演示。
"""

from __future__ import annotations

import asyncio
import re
from typing import AsyncGenerator, List, Optional

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

# 模拟「思考」耗时：给「流式/工具前」留出一点打断窗口。
THINK_DELAY = 0.6

_STOP_WORDS = ("停", "停止", "别弄了", "算了", "取消", "stop", "cancel")
# 触发「多工具流水线」任务的关键词：一次任务里连续调多个工具（搜索->统计->写笔记->汇总），
# 中间有多个可打断点，专门方便观察「中断/纠正」。
_PIPELINE_WORDS = ("调研", "研究", "报告", "多步", "依次", "pipeline", "多工具")


class MockLlm(BaseLlm):
    """确定性的离线假模型，实现 ADK 的 BaseLlm 接口。"""

    def __init__(self) -> None:
        # BaseLlm 是 pydantic 模型，需要一个 model 名字段。
        super().__init__(model="mock-interrupt-demo")

    @staticmethod
    def supported_models() -> List[str]:
        return [r"mock-.*"]

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        await asyncio.sleep(THINK_DELAY)  # 模拟思考，留出打断窗口
        contents = list(llm_request.contents or [])
        text = _last_user_text(contents) or ""

        # 停止意图最优先：即便在多工具流水线中途被纠正为「停」，也要能停下来。
        if any(w in text for w in _STOP_WORDS):
            yield _text_response("好的，我已经停下来了，不再继续之前的操作。")
            return

        # 多工具流水线任务：按「已完成几个工具」决定下一步调哪个工具（或收尾）。
        if any(w in text for w in _PIPELINE_WORDS):
            yield _pipeline_step(contents, text)
            return

        # 否则：若上一步是「工具结果」，产出最终总结（单工具任务的终态）。
        fr = _last_function_response(contents)
        if fr is not None:
            name, response = fr
            yield _text_response(f"（根据工具 {name} 的结果）结论：{response}")
            return

        # 单工具任务：按关键词选一个工具。
        if "转账" in text or "transfer" in text.lower():
            m = re.search(r"(\d+(?:\.\d+)?)", text)
            amount = float(m.group(1)) if m else 100.0
            to = "老王" if "老王" in text else "对方账户"
            yield _call_response("transfer", {"to": to, "amount": amount})
            return

        if "写" in text and ("笔记" in text or "note" in text.lower() or "文件" in text):
            note = text.split("写", 1)[-1].strip() or "一条笔记"
            yield _call_response("write_note", {"filename": "note.txt", "content": note})
            return

        if re.search(r"\d+\s*[\+\-\*/]", text):
            expr = re.sub(r"[^0-9\+\-\*/\(\)\.]", "", text) or "1+1"
            yield _call_response("calculator", {"expression": expr})
            return

        # 兜底：当成搜索。去掉「改成/查一下/天气」等词，让 query 更干净。
        query = re.sub(r"(帮我|请|改成|换成|查一下|查询|搜索|搜一下|的信息|天气)", "", text).strip()
        yield _call_response("web_search", {"query": query or text or "示例查询"})


# ---------------------------------------------------------------------------
# 构造 LlmResponse 的小工具
# ---------------------------------------------------------------------------

def _text_response(text: str) -> LlmResponse:
    """一条纯文本回复（无函数调用 -> ADK 视为终态）。"""
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


def _call_response(name: str, args: dict, note: Optional[str] = None) -> LlmResponse:
    """一条「函数调用」回复 -> ADK 会据此执行对应工具。

    note 不为空时，在函数调用前附一句说明文本（多工具流水线用它标注「第几步」）。
    """
    parts = []
    if note:
        parts.append(types.Part(text=note))
    parts.append(types.Part(function_call=types.FunctionCall(name=name, args=args)))
    return LlmResponse(content=types.Content(role="model", parts=parts))


def _last_user_text(contents) -> Optional[str]:
    for c in reversed(contents):
        if getattr(c, "role", None) == "user":
            for p in (c.parts or []):
                if getattr(p, "text", None):
                    return p.text
    return None


def _last_function_response(contents):
    """返回最近一条内容里的 (工具名, 结果)，若最近一步不是工具结果则返回 None。"""
    if not contents:
        return None
    last = contents[-1]
    for p in (last.parts or []):
        fr = getattr(p, "function_response", None)
        if fr is not None:
            return getattr(fr, "name", "?"), getattr(fr, "response", None)
    return None


def _results_since_last_user_text(contents) -> int:
    """统计「最后一条用户文本消息之后」已经产生了几个工具结果。

    用它判断多工具流水线进行到第几步（用户每发一条新请求都会重置计数）。
    """
    last_text_idx = -1
    for i, c in enumerate(contents):
        if getattr(c, "role", None) == "user" and any(
            getattr(p, "text", None) for p in (c.parts or [])
        ):
            last_text_idx = i
    count = 0
    for c in contents[last_text_idx + 1:]:
        for p in (c.parts or []):
            if getattr(p, "function_response", None) is not None:
                count += 1
    return count


def _pipeline_step(contents, text: str) -> LlmResponse:
    """多工具流水线：搜索 -> 统计 -> 写笔记 -> 汇总，共调用 3 个工具。

    按「已完成几个工具」决定这一步做什么，中间每一步都是一个可打断点：
        第1步 web_search(2s) → 第2步 calculator(瞬时) → 第3步 write_note(1s) → 汇总
    """
    topic = re.sub(
        r"(调研|研究|报告|多步|依次|pipeline|多工具|一下|帮我|请|改成|换成|关于|的)", "", text
    ).strip() or "指定主题"
    n = _results_since_last_user_text(contents)
    if n == 0:
        return _call_response("web_search", {"query": topic}, note=f"开始调研「{topic}」。第1步：联网搜资料。")
    if n == 1:
        return _call_response("calculator", {"expression": "1+2+3+4"}, note="第2步：统计要点数量。")
    if n == 2:
        return _call_response(
            "write_note",
            {"filename": "report.txt", "content": f"关于「{topic}」的调研结论（已搜资料并统计要点）"},
            note="第3步：把结论写进 report.txt。",
        )
    return _text_response(f"「{topic}」调研完成：已联网搜资料、统计要点、并写入 report.txt。")
