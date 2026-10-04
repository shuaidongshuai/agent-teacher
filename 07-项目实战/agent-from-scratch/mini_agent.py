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
  python3 mini_agent.py           # mock 模式，零依赖、无需 Key，先把循环跑通看清
  python3 mini_agent.py --real    # 真实 Gemini（懒加载 google-genai，走 Vertex 读 .env）

安全：write_file / run_shell 这类会改东西的工具，执行前一律要你确认（y/N）——
这就是 Agent 的“人在环中 / 权限门”，别让模型未经同意就动你的机器。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
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
# 模型后端：两个后端，主循环对它们一视同仁。接口约定：
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


class GeminiModel:
    """真实后端：懒加载 google-genai，手动 function calling，走 Vertex（读环境变量）。"""

    def __init__(self, model: str = "gemini-2.5-flash") -> None:
        from google import genai            # 懒加载：mock 模式下根本不导入它
        from google.genai import types

        self._t = types
        self.client = genai.Client()        # 自动读 .env 里的 Vertex / API Key 配置
        self.model = model
        self.contents: list[Any] = []
        decls = [
            types.FunctionDeclaration(
                name=name, description=t.description, parameters_json_schema=t.parameters)
            for name, t in TOOLS.items()
        ]
        self.config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT, tools=[types.Tool(function_declarations=decls)])

    def send_user(self, text: str) -> None:
        t = self._t
        self.contents.append(t.Content(role="user", parts=[t.Part.from_text(text=text)]))

    def generate(self) -> ModelTurn:
        resp = self.client.models.generate_content(
            model=self.model, contents=self.contents, config=self.config)
        self.contents.append(resp.candidates[0].content)      # 记下模型这一步
        calls = [ToolCall(fc.name, dict(fc.args or {})) for fc in (resp.function_calls or [])]
        try:
            text = resp.text
        except Exception:
            text = None
        return ModelTurn(text or None, calls)

    def send_tool_results(self, results: list[ToolResult]) -> None:
        t = self._t
        parts = [t.Part.from_function_response(name=r.call.name, response={"result": r.output})
                 for r in results]
        self.contents.append(t.Content(role="tool", parts=parts))   # Gemini 用 role="tool" 回传


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
    parser.add_argument("--real", action="store_true",
                        help="用真实 Gemini（需 google-genai + Vertex 环境变量）")
    parser.add_argument("--model", default="gemini-2.5-flash")
    args = parser.parse_args()

    if args.real:
        backend: Any = GeminiModel(model=args.model)
        print(f"后端：真实 Gemini（{args.model}）")
    else:
        backend = MockModel()
        print("后端：MockModel（零依赖演示；加 --real 切真实 Gemini）")
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





