#!/usr/bin/env python3
"""
mini_agent.py —— 从零手写一个最小 Agent 内核（L0 教学项目）

一个 Agent 的本质就三件事，这个文件把它们全摊开：
  1) 工具 tools ：一组普通函数 + JSON Schema，告诉模型“你能做什么”
  2) 循环 loop  ：模型想调工具→我执行→把结果塞回去→再问模型，直到它不再要工具
  3) 停止 stop  ：模型这一轮只回文字、不要工具 = 本次任务结束

对照 ADK：Runner 替你转的就是第 2 步；LlmAgent 替你拼的就是第 1 步工具声明。
这里不借任何框架，纯手写，让你看清“框架到底替你做了什么”。

运行：
  python3 mini_agent.py                     # mock 模式，零依赖、无需 Key，先把循环跑通看清
  python3 mini_agent.py --backend gemini    # 真实 Gemini（懒加载 google-genai，走 Vertex 读 .env）
  python3 mini_agent.py --backend openai    # 真实 OpenAI 兼容（懒加载 openai，.env 里填 OPENAI_API_KEY 即可）
  python3 mini_agent.py --real              # 向后兼容：等价于 --backend gemini

安全：write_file / run_shell 这类会改东西的工具，执行前一律要你确认（y/N）——
这就是 Agent 的“人在环中 / 权限门”，别让模型未经同意就动你的机器。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


# ------------------------------------------------------------------------
# 规范化结构：无论后端是 mock 还是 Gemini，主循环只认下面这两个结构
# ------------------------------------------------------------------------
@dataclass
class ToolCall:
    """模型这一步想调用的一个工具。"""
    name: str
    args: dict[str, Any]
    id: str | None = None   # OpenAI(Responses) 回填结果靠它当 call_id 对上 function_call；mock/gemini 用不到


@dataclass
class ModelTurn:
    """模型一次回复：可能带文字、可能带若干工具调用（也可能两者都有）。"""
    text: str | None
    tool_calls: list[ToolCall]


# ------------------------------------------------------------------------
# 第 1 件事：工具 —— 一组普通函数 + 它们的 JSON Schema
# 所有工具都限制在“工作目录”内操作，避免模型跑到别处乱动。
# ------------------------------------------------------------------------
WORKSPACE = Path(os.environ.get("AGENT_WORKSPACE", ".")).resolve()


def _safe_path(path: str) -> Path:
    """把模型给的相对路径钉在 WORKSPACE 内，挡掉 ../../ 逃逸。"""
    p = (WORKSPACE / path).resolve()
    if not str(p).startswith(str(WORKSPACE)):
        raise ValueError(f"路径越界：{path} 不在工作目录 {WORKSPACE} 内")
    return p


def read_file(path: str) -> str:
    p = _safe_path(path)
    if not p.is_file():
        return f"[错误] 文件不存在：{path}"
    text = p.read_text(encoding="utf-8", errors="replace")
    return text[:8000] + ("\n...[已截断]" if len(text) > 8000 else "")


def write_file(path: str, content: str) -> str:
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"[成功] 已写入 {path}（{len(content)} 字符）"


def list_dir(path: str = ".") -> str:
    p = _safe_path(path)
    if not p.is_dir():
        return f"[错误] 不是目录：{path}"
    names = sorted(e.name + ("/" if e.is_dir() else "") for e in p.iterdir())
    return "\n".join(names) or "（空目录）"


def run_shell(command: str) -> str:
    proc = subprocess.run(
        command, shell=True, cwd=WORKSPACE,
        capture_output=True, text=True, timeout=60,
    )
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return f"[exit={proc.returncode}]\n{out[:4000]}"


@dataclass
class Tool:
    func: Callable[..., str]
    description: str
    parameters: dict[str, Any]       # JSON Schema，告诉模型这个工具收什么参数
    needs_approval: bool = False     # True = 执行前要用户确认（会改东西的工具）


TOOLS: dict[str, Tool] = {
    "read_file": Tool(
        read_file, "读取工作目录下一个文本文件的内容",
        {"type": "object",
         "properties": {"path": {"type": "string", "description": "相对路径"}},
         "required": ["path"]},
    ),
    "list_dir": Tool(
        list_dir, "列出工作目录下某个目录里的文件",
        {"type": "object",
         "properties": {"path": {"type": "string", "description": "相对路径，默认当前目录"}},
         "required": []},
    ),
    "write_file": Tool(
        write_file, "把内容写入工作目录下的文件（会覆盖同名文件）",
        {"type": "object",
         "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
         "required": ["path", "content"]},
        needs_approval=True,
    ),
    "run_shell": Tool(
        run_shell, "在工作目录下执行一条 shell 命令并返回输出",
        {"type": "object",
         "properties": {"command": {"type": "string"}},
         "required": ["command"]},
        needs_approval=True,
    ),
}

SYSTEM_PROMPT = (
    "你是一个最小化的命令行编码助手。你可以调用工具读写文件、列目录、执行 shell。"
    "需要信息时就调用工具去拿，不要凭空编造文件内容。"
    "任务完成后用简洁中文回复用户，并且这一轮不要再调用工具。"
)


# ------------------------------------------------------------------------
# 权限门 + 工具分发
# ------------------------------------------------------------------------
@dataclass
class ToolResult:
    call: ToolCall
    output: str


def approve(call: ToolCall) -> bool:
    """危险工具执行前请用户确认——Agent 的“人在环中”。"""
    print(f"\n⚠️  模型想执行 [{call.name}] 参数：{json.dumps(call.args, ensure_ascii=False)}")
    return input("   允许吗？(y/N) ").strip().lower() in ("y", "yes")


def dispatch(call: ToolCall) -> str:
    """真正执行一个工具调用；异常也当作结果喂回模型，让它自己纠错。"""
    tool = TOOLS.get(call.name)
    if tool is None:
        return f"[错误] 未知工具：{call.name}"
    try:
        return tool.func(**call.args)
    except Exception as e:
        return f"[异常] {type(e).__name__}: {e}"


# ------------------------------------------------------------------------
# 模型后端：三个后端（mock / gemini / openai），主循环对它们一视同仁。接口约定：
#   send_user(text)            放入一条用户消息
#   generate() -> ModelTurn    让模型产出这一步，并记进自己的历史
#   send_tool_results(results) 把工具执行结果塞回历史，供下一步使用
# “历史怎么存”是各后端自己的事，主循环不关心——这正是框架的职责边界。
# ------------------------------------------------------------------------
class MockModel:
    """零依赖的假模型：按关键词规则产出工具调用，只为把循环跑通看清楚。"""

    def __init__(self) -> None:
        self.history: list[dict[str, Any]] = []
        self._just_called = False

    def send_user(self, text: str) -> None:
        self.history.append({"role": "user", "text": text})
        self._just_called = False

    def generate(self) -> ModelTurn:
        last_user = next(
            (h["text"] for h in reversed(self.history) if h["role"] == "user"), "")
        if self._just_called:                       # 上一步调过工具 → 这步给结论、收工
            self._just_called = False
            tool = next((h for h in reversed(self.history) if h["role"] == "tool"), None)
            seen = tool["output"][:200] if tool else "(无)"
            return ModelTurn(f"[mock] 工具返回如下，任务完成：\n{seen}", [])
        if any(k in last_user for k in ("列", "目录")) or "ls" in last_user.lower():
            self._just_called = True
            return ModelTurn(None, [ToolCall("list_dir", {"path": "."})])
        for token in last_user.replace("，", " ").replace("。", " ").split():
            if "." in token and len(token) > 2:     # 粗略地把“带点的词”当成文件名
                self._just_called = True
                return ModelTurn(None, [ToolCall("read_file", {"path": token})])
        return ModelTurn(f"[mock] 收到：{last_user}（试试“列目录”或给我一个文件名）", [])

    def send_tool_results(self, results: list[ToolResult]) -> None:
        for r in results:
            self.history.append({"role": "tool", "name": r.call.name, "output": r.output})


def _load_env() -> None:
    """真实模式下把 .env 读进 os.environ。

    为什么必须有这一步：google-genai 的 Client() 只认 os.environ，**不会自己去读 .env 文件**。
    放在 GeminiModel 构造时才调用（而不是模块顶部），是为了保持 mock 模式「零依赖」——
    不装 python-dotenv 也能跑 mock。
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return  # 没装 python-dotenv：假设你已手动 export 了环境变量
    here = Path(__file__).resolve().parent
    load_dotenv(here / ".env")                          # 只读本项目目录下的 .env


class GeminiModel:
    """真实后端：懒加载 google-genai，手动 function calling，走 Vertex（读环境变量）。"""

    def __init__(self, model: str = "gemini-2.5-flash") -> None:
        _load_env()                        # 先把 .env 灌进环境变量（见下方说明）
        from google import genai            # 懒加载：mock 模式下根本不导入它
        from google.genai import types

        self._t = types
        # genai.Client() 只读 os.environ，自己不会读 .env 文件——所以上面必须先 _load_env()
        self.client = genai.Client()        # 读环境变量里的 Vertex / API Key 配置
        self.model = model
        self.contents: list[Any] = []
        decls = [
            types.FunctionDeclaration(name=name, description=t.description, parameters_json_schema=t.parameters)
            for name, t in TOOLS.items()
        ]
        self.config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT, tools=[types.Tool(function_declarations=decls)])

    def send_user(self, text: str) -> None:
        t = self._t
        self.contents.append(t.Content(role="user", parts=[t.Part.from_text(text=text)]))

    def _render_contents(self) -> str:
        """把这次发给 Gemini 的 contents 压成一行可读字符串（供日志打印真实入参）。"""
        items: list[dict[str, Any]] = []
        for c in self.contents:
            role = getattr(c, "role", "?")
            for p in getattr(c, "parts", None) or []:
                if getattr(p, "text", None):
                    items.append({"role": role, "text": p.text})
                elif getattr(p, "function_call", None):
                    fc = p.function_call
                    items.append({"role": role, "call": fc.name, "args": dict(fc.args or {})})
                elif getattr(p, "function_response", None):
                    fr = p.function_response
                    items.append({"role": role, "resp": fr.name, "result": fr.response})
        return json.dumps(items, ensure_ascii=False)

    def generate(self) -> ModelTurn:
        prompt_in = self._render_contents()                    # 发出去之前的真实入参
        t0 = time.perf_counter()
        resp = self.client.models.generate_content(
            model=self.model, contents=self.contents, config=self.config)
        elapsed = time.perf_counter() - t0
        self.contents.append(resp.candidates[0].content)      # 记下模型这一步
        calls = [ToolCall(fc.name, dict(fc.args or {})) for fc in (resp.function_calls or [])]
        try:
            text = resp.text
        except Exception:
            text = None
        # 一行日志：真实入参提示词 + 返回值（文字 + 工具调用）+ 耗时
        ret = {"text": text, "tool_calls": [{"name": c.name, "args": c.args} for c in calls]}
        print(f"[gemini] 入参={prompt_in} | 返回={json.dumps(ret, ensure_ascii=False)} "
              f"| 耗时={elapsed:.2f}s")
        return ModelTurn(text or None, calls)

    def send_tool_results(self, results: list[ToolResult]) -> None:
        t = self._t
        parts = [t.Part.from_function_response(name=r.call.name, response={"result": r.output})
                 for r in results]
        self.contents.append(t.Content(role="tool", parts=parts))   # Gemini 用 role="tool" 回传


class OpenAIModel:
    """真实后端：懒加载 openai，走 **Responses API** 手动 function calling（读环境变量）。

    最省事的真实后端：.env 里只要有 OPENAI_API_KEY 就能跑；想接厂内/第三方兼容网关，
    再配一个 OPENAI_BASE_URL 指过去即可（官方 OpenAI 留空）。对比 GeminiModel 走 Vertex
    那套（要项目号、凭证、代理），这里就是「填个 key（+base_url）就用」。

    用的是 Responses API（client.responses.create），不是老的 chat.completions：
      - 工具声明是「扁平」结构：{type:function, name, description, parameters}
        （chat.completions 则要嵌在 function:{...} 里）。
      - 历史是一个 input 项列表：用户消息、模型输出项（resp.output，含 function_call）、
        工具结果（function_call_output）混在一起，一路往后 append。
      - 工具结果用 function_call_output + call_id 跟模型输出的 function_call 对上
        （所以把每个调用的 call_id 透过 ToolCall.id 带出去，回填时按它塞回来）。
    """

    def __init__(self, model: str = "gpt-4o") -> None:
        _load_env()                        # 先把 .env 灌进环境变量（和 Gemini 后端同一套机制）
        try:
            from openai import OpenAI       # 懒加载：mock/gemini 模式下根本不导入它
        except ImportError:
            raise SystemExit("未安装 openai 包：请先 pip install openai，再用 --backend openai")

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise SystemExit("缺少 OPENAI_API_KEY：在 .env 或环境变量里配好后再用 --backend openai")
        base_url = os.environ.get("OPENAI_BASE_URL") or None   # 兼容端点可选，官方留空
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        # 整段历史：用户消息 / 模型输出项 / 工具结果 混在一个 input 列表里，一路往后 append
        self.input: list[Any] = []
        # Responses API 的工具声明是「扁平」结构（chat.completions 才嵌在 function 里）
        self.tools = [
            {"type": "function", "name": name,
             "description": t.description, "parameters": t.parameters}
            for name, t in TOOLS.items()
        ]

    def send_user(self, text: str) -> None:
        self.input.append({"role": "user", "content": text})

    def _render_input(self) -> str:
        """把这次要发给 Responses API 的 input 压成一行可读字符串（供日志打印真实入参）。

        input 里混着 dict（用户消息 / function_call_output）和 SDK 的输出项对象
        （message / function_call），这里统一渲染，和 Gemini 的 _render_contents 一个思路。
        """
        items: list[dict[str, Any]] = []
        for it in self.input:
            if isinstance(it, dict):
                if it.get("role"):
                    items.append({"role": it["role"], "text": it.get("content")})
                elif it.get("type") == "function_call_output":
                    items.append({"resp": it.get("call_id"), "result": it.get("output")})
                else:
                    items.append(it)
                continue
            typ = getattr(it, "type", None)                      # 模型输出项（SDK 对象）
            if typ == "function_call":
                items.append({"call": it.name, "args": it.arguments})
            elif typ == "message":
                txt = "".join(getattr(c, "text", "") for c in (getattr(it, "content", None) or []))
                items.append({"role": getattr(it, "role", "assistant"), "text": txt})
            else:
                items.append({"type": typ})                      # reasoning 等其它项
        return json.dumps(items, ensure_ascii=False)

    def generate(self) -> ModelTurn:
        prompt_in = self._render_input()                         # 发出去之前的真实入参
        t0 = time.perf_counter()
        resp = self.client.responses.create(
            model=self.model, instructions=SYSTEM_PROMPT,
            input=self.input, tools=self.tools)
        elapsed = time.perf_counter() - t0
        self.input += list(resp.output)                          # 模型这步的所有输出项原样接回历史
        calls = [
            ToolCall(it.name, json.loads(it.arguments or "{}"), id=it.call_id)
            for it in resp.output if getattr(it, "type", None) == "function_call"
        ]
        text = resp.output_text or None                          # 只有工具调用、没文字时为空
        # 一行日志：真实入参 + 返回值（文字 + 工具调用）+ 耗时（和 Gemini 后端对齐）
        ret = {"text": text, "tool_calls": [{"name": c.name, "args": c.args} for c in calls]}
        print(f"[openai] 入参={prompt_in} | 返回={json.dumps(ret, ensure_ascii=False)} "
              f"| 耗时={elapsed:.2f}s")
        return ModelTurn(text, calls)

    def send_tool_results(self, results: list[ToolResult]) -> None:
        for r in results:
            # Responses API 用 function_call_output + call_id 跟模型输出的 function_call 对上
            self.input.append(
                {"type": "function_call_output", "call_id": r.call.id, "output": r.output})


# ========================================================================
# 第 2 + 3 件事：主循环。这段就是 Agent 的心脏——看懂它你就看懂了 Agent。
# ========================================================================
MAX_STEPS = 12   # 停止条件之一：单任务最多工具轮数，防止模型陷入死循环


def agent_turn(backend: Any, user_input: str) -> None:
    backend.send_user(user_input)
    for _ in range(MAX_STEPS):
        turn = backend.generate()
        if turn.text:
            print(f"\n🤖 {turn.text}")
        if not turn.tool_calls:
            return                                   # 模型不再要工具 → 任务结束（停止）
        results: list[ToolResult] = []
        for call in turn.tool_calls:
            tool = TOOLS.get(call.name)
            print(f"\n🔧 调用 {call.name}({json.dumps(call.args, ensure_ascii=False)})")
            if tool and tool.needs_approval and not approve(call):
                results.append(ToolResult(call, "[被拒绝] 用户不允许执行该操作"))
                continue
            output = dispatch(call)
            print(f"   ↳ {(output.splitlines() or [''])[0]}"[:120])
            results.append(ToolResult(call, output))
        backend.send_tool_results(results)           # 结果塞回去，进入下一步循环
    print("\n⚠️  达到最大步数，已停止。")


def main() -> None:
    parser = argparse.ArgumentParser(description="从零手写的最小 Agent 内核")
    parser.add_argument("--backend", choices=["mock", "gemini", "openai"], default="mock",
                        help="选后端：mock（默认，零依赖）/ gemini（走 Vertex）/ openai（填 api_key 即用）")
    parser.add_argument("--real", action="store_true",
                        help="向后兼容：等价于 --backend gemini")
    parser.add_argument("--model", default=None,
                        help="模型名；不填按后端给默认（gemini→gemini-2.5-flash，openai→gpt-4o）")
    args = parser.parse_args()

    # --real 是老开关，只在没显式指定 --backend 时把它解释成 gemini
    backend_name = "gemini" if (args.real and args.backend == "mock") else args.backend

    if backend_name == "gemini":
        backend: Any = GeminiModel(model=args.model or "gemini-2.5-flash")
        print(f"后端：真实 Gemini（{backend.model}）")
    elif backend_name == "openai":
        backend = OpenAIModel(model=args.model or "gpt-6-sol")
        print(f"后端：OpenAI 兼容（{backend.model}）")
    else:
        backend = MockModel()
        print("后端：MockModel（零依赖演示；加 --backend gemini/openai 切真实模型）")
    print(f"工作目录：{WORKSPACE}")
    print("试试：列一下目录 / 读取 README.md 并总结。输入 exit 退出。\n")

    while True:
        try:
            user_input = input("你 › ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            break
        agent_turn(backend, user_input)


if __name__ == "__main__":
    main()





