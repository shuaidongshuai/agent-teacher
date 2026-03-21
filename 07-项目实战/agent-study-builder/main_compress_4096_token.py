#!/usr/bin/env python3
"""
一个使用 ReAct 模式的学习资料整理 Agent。

核心特点：
1. LLM 每一轮先思考当前任务状态
2. LLM 自主决定是否调用工具、调用什么工具
3. Agent 负责执行工具，并把结果反馈给 LLM
4. 循环直到 LLM 主动宣布任务完成

这比“LLM 只生成一次答案”更接近真正的 Agent。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import textwrap
import traceback
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def slugify(text: str) -> str:
    lowered = text.strip().lower()
    lowered = re.sub(r"\s+", "-", lowered)
    lowered = re.sub(r"[^a-z0-9\-\u4e00-\u9fff]", "", lowered)
    return lowered or "study-topic"


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: Dict[str, str]


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    message: str
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReActStep:
    round_id: int
    thought: str
    action: str
    action_input: Dict[str, Any]
    observation: str


@dataclass
class AgentState:
    topic: str
    audience: str
    output_dir: Path
    current_round: int = 0
    completed: bool = False
    final_answer: str = ""
    llm_available: bool = False
    llm_rounds: int = 0
    tool_calls: int = 0
    steps: List[ReActStep] = field(default_factory=list)


class BaseTool:
    spec: ToolSpec

    def run(self, **kwargs: Any) -> ToolResult:
        raise NotImplementedError


class WorkspaceTool(BaseTool):
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()

    def resolve_path(self, raw_path: str) -> Path:
        """
        将工具收到的相对路径限制在输出目录中，避免 Agent 随意写到别处。
        """

        candidate = Path(raw_path)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self.workspace_root / candidate).resolve()

        if resolved != self.workspace_root and self.workspace_root not in resolved.parents:
            raise ValueError(f"路径越界，不允许访问输出目录之外的文件：{raw_path}")

        return resolved


class ListDirTool(WorkspaceTool):
    spec = ToolSpec(
        name="list_dir",
        description="列出某个目录下的文件和子目录，用于观察当前工作区状态。",
        input_schema={"path": "目录路径，通常传 . 或某个相对路径"},
    )

    def run(self, **kwargs: Any) -> ToolResult:
        raw_path = str(kwargs.get("path", "."))
        directory = self.resolve_path(raw_path)
        directory.mkdir(parents=True, exist_ok=True)
        entries = []
        for item in sorted(directory.iterdir(), key=lambda value: value.name):
            entries.append(
                {
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                }
            )
        return ToolResult(
            tool_name=self.spec.name,
            success=True,
            message=f"成功列出目录：{directory}",
            payload={"entries": entries},
        )


class ReadFileTool(WorkspaceTool):
    spec = ToolSpec(
        name="read_file",
        description="读取文件内容，用于检查之前生成的结果或理解已有内容。",
        input_schema={"path": "文件路径，相对输出目录"},
    )

    def run(self, **kwargs: Any) -> ToolResult:
        path = self.resolve_path(str(kwargs["path"]))
        if not path.exists():
            return ToolResult(self.spec.name, False, f"文件不存在：{path}")
        if path.is_dir():
            return ToolResult(self.spec.name, False, f"目标是目录，不是文件：{path}")

        content = path.read_text(encoding="utf-8")
        return ToolResult(
            tool_name=self.spec.name,
            success=True,
            message=f"成功读取文件：{path.name}",
            payload={"content": content, "length": len(content)},
        )


class WriteFileTool(WorkspaceTool):
    spec = ToolSpec(
        name="write_file",
        description="创建或覆盖文件内容。适合一次性写入完整文档。",
        input_schema={
            "path": "文件路径，相对输出目录",
            "content": "要写入的完整字符串内容",
        },
    )

    def run(self, **kwargs: Any) -> ToolResult:
        path = self.resolve_path(str(kwargs["path"]))
        content = str(kwargs["content"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ToolResult(
            tool_name=self.spec.name,
            success=True,
            message=f"成功写入文件：{path.name}",
            payload={"path": str(path), "length": len(content)},
        )


class AppendFileTool(WorkspaceTool):
    spec = ToolSpec(
        name="append_file",
        description="向已有文件末尾追加内容。适合增量补充文档。",
        input_schema={
            "path": "文件路径，相对输出目录",
            "content": "要追加的字符串内容",
        },
    )

    def run(self, **kwargs: Any) -> ToolResult:
        path = self.resolve_path(str(kwargs["path"]))
        content = str(kwargs["content"])
        path.parent.mkdir(parents=True, exist_ok=True)
        previous = ""
        if path.exists():
            previous = path.read_text(encoding="utf-8")
        path.write_text(previous + content, encoding="utf-8")
        return ToolResult(
            tool_name=self.spec.name,
            success=True,
            message=f"成功追加文件：{path.name}",
            payload={"path": str(path), "appended_length": len(content)},
        )


class MakeDirTool(WorkspaceTool):
    spec = ToolSpec(
        name="make_dir",
        description="创建目录，适合组织文档结构。",
        input_schema={"path": "目录路径，相对输出目录"},
    )

    def run(self, **kwargs: Any) -> ToolResult:
        path = self.resolve_path(str(kwargs["path"]))
        path.mkdir(parents=True, exist_ok=True)
        return ToolResult(
            tool_name=self.spec.name,
            success=True,
            message=f"成功创建目录：{path}",
            payload={"path": str(path)},
        )


class FileExistsTool(WorkspaceTool):
    spec = ToolSpec(
        name="file_exists",
        description="检查某个文件或目录是否存在。",
        input_schema={"path": "文件或目录路径，相对输出目录"},
    )

    def run(self, **kwargs: Any) -> ToolResult:
        path = self.resolve_path(str(kwargs["path"]))
        exists = path.exists()
        return ToolResult(
            tool_name=self.spec.name,
            success=True,
            message=f"存在性检查完成：{path.name} -> {exists}",
            payload={"exists": exists, "path": str(path)},
        )


class ToolRegistry:
    """
    可扩展工具注册表。

    你后面想加新工具时，只需要：
    1. 实现一个 BaseTool 子类
    2. 调用 register() 注册进去
    """

    def __init__(self) -> None:
        self.tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self.tools[tool.spec.name] = tool

    def call(self, tool_name: str, tool_input: Dict[str, Any]) -> ToolResult:
        if tool_name not in self.tools:
            return ToolResult(tool_name, False, f"未知工具：{tool_name}")
        try:
            return self.tools[tool_name].run(**tool_input)
        except Exception as exc:
            return ToolResult(tool_name, False, f"{type(exc).__name__}: {exc}")

    def describe_tools(self) -> List[Dict[str, Any]]:
        descriptions = []
        for tool in self.tools.values():
            descriptions.append(
                {
                    "name": tool.spec.name,
                    "description": tool.spec.description,
                    "input_schema": tool.spec.input_schema,
                }
            )
        return descriptions


class OpenAICompatibleClient:
    """
    兼容 responses / chat_completions 的 LLM 客户端。

    这里的关键不是“写一次文档”，而是：
    每一轮把任务、历史轨迹、工具列表交给模型，让模型决定下一步。
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/")
        self.model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
        self.api_style = self._read_api_style()
        self.ssl_verify = self._read_ssl_verify_setting()

    def available(self) -> bool:
        return bool(self.api_key)

    def request_json(self, prompt: str, purpose: str) -> Optional[Dict[str, Any]]:
        text_output = self._request_text(prompt, purpose=purpose)
        if not text_output:
            return None

        text_output = self._strip_code_fence(text_output)

        try:
            return json.loads(text_output)
        except Exception as exc:
            self._log_exception(exc)
            self._log("LLM 返回的文本无法解析成 JSON：")
            self._log(text_output)
            return None

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        """剥离 LLM 常见的 markdown code fence 包裹，如 ```json ... ```。"""
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json|JSON)?\s*\n?", "", stripped)
            stripped = re.sub(r"\n?```\s*$", "", stripped)
        return stripped.strip()

    def _request_text(self, prompt: str, purpose: str) -> Optional[str]:
        if not self.available():
            return None

        payload = self._build_payload(prompt)
        self._log(f"准备调用 LLM：{purpose}")
        self._log(f"接口风格：{self.api_style}")
        self._log(f"请求地址：{self._build_api_url()}")
        self._log("请求入参：")
        self._log(json.dumps(payload, ensure_ascii=False, indent=2))

        request = urllib.request.Request(
            self._build_api_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=60,
                context=self._build_ssl_context(),
            ) as response:
                body = response.read().decode("utf-8")
                self._log("接口原始返回：")
                self._log(body)
        except Exception as exc:
            self._log_exception(exc)
            return None

        try:
            data = json.loads(body)
            text_output = self._extract_text_output(data)
            if text_output:
                self._log("提取到的文本结果：")
                self._log(text_output)
            return text_output
        except Exception as exc:
            self._log_exception(exc)
            return None

    def _build_api_url(self) -> str:
        api_base = self.base_url if self.base_url.endswith("/v1") else f"{self.base_url}/v1"
        if self.api_style == "chat_completions":
            return f"{api_base}/chat/completions"
        return f"{api_base}/responses"

    def _build_payload(self, prompt: str) -> Dict[str, Any]:
        if self.api_style == "chat_completions":
            return {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            }
        return {"model": self.model, "input": prompt}

    def _build_ssl_context(self) -> ssl.SSLContext:
        if self.ssl_verify:
            return ssl.create_default_context()
        return ssl._create_unverified_context()

    def _extract_text_output(self, response_json: Dict[str, Any]) -> Optional[str]:
        if self.api_style == "chat_completions":
            choices = response_json.get("choices", [])
            if not choices:
                return None
            content = choices[0].get("message", {}).get("content")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                texts: List[str] = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_value = item.get("text", "")
                        if text_value:
                            texts.append(text_value)
                if texts:
                    return "\n".join(texts).strip()
            return None

        output = response_json.get("output", [])
        texts: List[str] = []
        for item in output:
            for content in item.get("content", []):
                text_value = content.get("text")
                if text_value:
                    texts.append(text_value)

        if texts:
            return "\n".join(texts).strip()

        fallback = response_json.get("output_text")
        if isinstance(fallback, str):
            return fallback.strip()
        return None

    @staticmethod
    def _read_api_style() -> str:
        raw = os.getenv("OPENAI_API_STYLE", "responses").strip().lower()
        if raw in {"chat", "chat_completions", "chat-completions"}:
            return "chat_completions"
        return "responses"

    @staticmethod
    def _read_ssl_verify_setting() -> bool:
        raw = os.getenv("OPENAI_SSL_VERIFY", "true").strip().lower()
        return raw not in {"false", "0", "no", "off"}

    @staticmethod
    def _log(message: str) -> None:
        print(f"[OpenAICompatibleClient] {message}", file=sys.stderr)

    def _log_exception(self, exc: Exception) -> None:
        self._log(f"{type(exc).__name__}: {exc}")
        if isinstance(exc, urllib.error.HTTPError):
            try:
                self._log(exc.read().decode("utf-8"))
            except Exception:
                pass
        self._log(traceback.format_exc())


class ScriptedFallbackAgent:
    """
    当用户没有配置 LLM 时，给出一个最小本地回退。

    这个分支不是重点，只是为了保证项目还能跑。
    真正的教学重点在上面的 ReAct + 工具循环。
    """

    def __init__(self, output_dir: Path, topic: str, audience: str) -> None:
        self.output_dir = output_dir
        self.topic = topic
        self.audience = audience

    def build_files(self) -> Dict[str, str]:
        return {
            "README.md": textwrap.dedent(
                f"""
                # {self.topic} 学习资料包

                ## 学习目标

                这套资料面向 {self.audience}，用于帮助你建立 {self.topic} 的整体认知。

                ## 目录

                1. 主题概览
                2. 核心概念
                3. 常见误区
                4. 练习与答案

                ## 使用建议

                建议先快速浏览整体结构，再逐篇精读，并把重点内容转写成自己的语言。

                ## 总结与下一步建议

                看完后请立刻做一个最小项目，把理解转成真实产出。
                """
            ).strip()
            + "\n"
        }


class StudyMaterialReActAgent:
    """
    真正的 ReAct Agent。

    它不再是“规则先决定、LLM 补内容”，而是：
    1. 给 LLM 一个完整任务
    2. 给 LLM 当前环境、历史轨迹、可用工具
    3. LLM 自己决定是直接结束还是调用工具
    4. Agent 执行工具，并把结果返回给 LLM
    5. 周而复始，直到任务完成
    """

    # ── 上下文压缩参数 ──────────────────────────────────────────────
    MAX_INPUT_TOKENS = 4096    # 输入 token 硬上限
    RECENT_WINDOW = 3          # 保留最近 N 轮完整轨迹
    MAX_OBS_CHARS = 300        # 每条 observation 最大保留字符数
    SUMMARIZE_EVERY = 4        # 每积累 N 轮旧步骤触发一次 LLM 摘要
    MAX_SUMMARY_CHARS = 300    # 历史摘要最大字符数

    def __init__(self, topic: str, audience: str, output_dir: Path, max_rounds: int = 20) -> None:
        self.topic = topic
        self.audience = audience
        self.output_dir = output_dir
        self.max_rounds = max_rounds
        self.client = OpenAICompatibleClient()
        self.registry = ToolRegistry()
        self._register_default_tools()
        self._tools_desc_cache: Optional[str] = None   # 工具描述缓存
        self._history_summary: str = ""                 # 早期轮次的 LLM 摘要
        self.state = AgentState(
            topic=topic,
            audience=audience,
            output_dir=output_dir,
            llm_available=self.client.available(),
        )

    def _register_default_tools(self) -> None:
        self.registry.register(ListDirTool(self.output_dir))
        self.registry.register(ReadFileTool(self.output_dir))
        self.registry.register(WriteFileTool(self.output_dir))
        self.registry.register(AppendFileTool(self.output_dir))
        self.registry.register(MakeDirTool(self.output_dir))
        self.registry.register(FileExistsTool(self.output_dir))

    def run(self) -> AgentState:
        if not self.client.available():
            self._run_local_fallback()
            return self.state

        # self._log("检测到可用 OPENAI_API_KEY，进入真正的 ReAct + 工具循环。")
        self._log(f"输出目录：{self.output_dir}")

        for round_id in range(1, self.max_rounds + 1):
            self.state.current_round = round_id
            self._log(f"\n=== ReAct Round {round_id} ===")

            # 检查是否需要压缩历史轨迹
            self._maybe_summarize_history()

            decision = self.client.request_json(
                self._build_react_prompt(),
                purpose=f"ReAct 第 {round_id} 轮决策",
            )
            self.state.llm_rounds += 1

            if not decision:
                raise RuntimeError("LLM 没有返回可解析的 ReAct 决策 JSON。")

            thought = str(decision.get("thought", "")).strip()
            action_type = str(decision.get("action", "")).strip()
            tool_name = str(decision.get("tool_name", "")).strip()
            tool_input = decision.get("tool_input", {})
            final_answer = str(decision.get("final_answer", "")).strip()

            if not isinstance(tool_input, dict):
                raise RuntimeError("LLM 返回的 tool_input 不是 JSON object。")

            self._log(f"Thought: {thought}")

            if action_type == "finish":
                self.state.completed = True
                self.state.final_answer = final_answer or "任务完成。"
                self.state.steps.append(
                    ReActStep(
                        round_id=round_id,
                        thought=thought,
                        action="finish",
                        action_input={},
                        observation="LLM 认为任务已经完成，不再调用工具。",
                    )
                )
                return self.state

            if action_type != "tool":
                raise RuntimeError(f"LLM 返回了不支持的 action 类型：{action_type}")

            result = self.registry.call(tool_name, tool_input)
            self.state.tool_calls += 1
            observation = self._format_tool_result(result)

            self._log(f"Action: {tool_name}")
            self._log(f"Action Input: {json.dumps(tool_input, ensure_ascii=False)}")
            self._log(f"Observation: {observation}")

            self.state.steps.append(
                ReActStep(
                    round_id=round_id,
                    thought=thought,
                    action=tool_name,
                    action_input=tool_input,
                    observation=observation,
                )
            )

        raise RuntimeError("达到最大轮数，LLM 仍未完成任务。")

    def _run_local_fallback(self) -> None:
        self._log("未检测到可用 OPENAI_API_KEY，回退到最小本地模式。")
        fallback = ScriptedFallbackAgent(self.output_dir, self.topic, self.audience)
        files = fallback.build_files()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        for index, (filename, content) in enumerate(files.items(), start=1):
            path = self.output_dir / filename
            path.write_text(content, encoding="utf-8")
            self.state.steps.append(
                ReActStep(
                    round_id=index,
                    thought="本地回退模式：直接生成最小入口文档。",
                    action="write_file",
                    action_input={"path": filename, "content": content[:120] + "..."},
                    observation=f"成功写入 {filename}",
                )
            )

        self.state.completed = True
        self.state.final_answer = "本地回退模式已生成最小资料包。"

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """
        粗略估算 token 数。

        中文约 1.5 字符/token，英文/符号约 4 字符/token。
        对中英混合文本取保守值 ~1.8 字符/token。
        """
        if not text:
            return 0
        # 统计中文字符占比，动态调整比率
        cjk_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        ratio = len(text) / max(len(text), 1)
        cjk_ratio = cjk_count / max(len(text), 1)
        # 中文多时用更小的除数（更多 token），英文多时用更大的除数
        chars_per_token = 1.5 * cjk_ratio + 4.0 * (1 - cjk_ratio)
        chars_per_token = max(chars_per_token, 1.2)
        return int(len(text) / chars_per_token) + 1

    @staticmethod
    def _truncate_text(text: str, max_chars: int) -> str:
        """截断过长文本，保留头部为主。"""
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "...(已截断)"

    @staticmethod
    def _truncate_observation(obs: str, limit: int) -> str:
        """截断过长的 observation，保留头部。"""
        if len(obs) <= limit:
            return obs
        return obs[:limit] + "...(已截断)"

    def _build_trajectory(self, token_budget: int) -> tuple[str, str]:
        """
        在 token 预算内构建压缩后的历史轨迹。

        返回 (摘要部分, 最近轮次 JSON)。
        """
        steps = self.state.steps
        recent_window = self.RECENT_WINDOW

        old_steps = steps[:-recent_window] if len(steps) > recent_window else []
        recent_steps = steps[-recent_window:]

        # ── 早期轮次 → 单行摘要 ──
        summary_lines: List[str] = []
        if self._history_summary:
            summary_lines.append(self._truncate_text(
                self._history_summary, self.MAX_SUMMARY_CHARS
            ))
        for s in old_steps:
            status = "ok" if "成功" in s.observation or '"success": true' in s.observation else "fail"
            summary_lines.append(f"R{s.round_id}:{s.action}->{status}")
        summary_text = "\n".join(summary_lines) if summary_lines else ""

        # ── 最近轮次 → 紧凑 JSON ──
        # 先尝试正常构建，如果超预算则逐步压缩
        obs_limit = self.MAX_OBS_CHARS
        for attempt in range(4):
            recent_trajectory = []
            for step in recent_steps:
                is_finish = step.action == "finish"
                entry: Dict[str, Any] = {
                    "round": step.round_id,
                    "action": "finish" if is_finish else "tool",
                    "tool_name": "" if is_finish else step.action,
                    "tool_input": step.action_input,
                    "observation": self._truncate_observation(step.observation, obs_limit),
                }
                # 只在预算充裕时保留 thought
                if attempt < 2:
                    entry["thought"] = self._truncate_text(step.thought, 100)
                recent_trajectory.append(entry)
            recent_json = json.dumps(recent_trajectory, ensure_ascii=False, separators=(",", ":"))

            total_tokens = self._estimate_tokens(summary_text) + self._estimate_tokens(recent_json)
            if total_tokens <= token_budget:
                break
            # 逐步压缩
            obs_limit = obs_limit // 2
            if attempt == 1:
                summary_text = ""  # 丢弃摘要
            if attempt >= 2:
                # 减少最近轮次窗口
                recent_steps = recent_steps[-max(1, len(recent_steps) - 1):]

        return summary_text, recent_json

    def _maybe_summarize_history(self) -> None:
        """
        当累积的旧步骤达到阈值时，调用 LLM 将它们压缩为一段摘要，
        然后清理已摘要的步骤，只保留最近窗口。
        """
        steps = self.state.steps
        old_count = max(0, len(steps) - self.RECENT_WINDOW)
        if old_count < self.SUMMARIZE_EVERY:
            return

        old_steps = steps[:old_count]
        old_desc = "\n".join(
            f"R{s.round_id}:{s.action}({s.observation[:60]})"
            for s in old_steps
        )
        summary_prompt = (
            "用2-3句话总结以下Agent轨迹的进展，保留文件名：\n" + old_desc
        )
        result = self.client._request_text(summary_prompt, purpose="压缩历史")
        if result:
            self._history_summary = self._truncate_text(
                result.strip(), self.MAX_SUMMARY_CHARS
            )
            self.state.steps = steps[old_count:]
            self._log(f"历史已压缩，摘要 {len(self._history_summary)} 字符")

    def _get_tools_description(self) -> str:
        """缓存紧凑格式的工具描述。"""
        if self._tools_desc_cache is None:
            # 用紧凑单行格式代替完整 JSON，节省 token
            lines = []
            for tool in self.registry.tools.values():
                params = ",".join(f"{k}" for k in tool.spec.input_schema)
                lines.append(f"- {tool.spec.name}({params}): {tool.spec.description}")
            self._tools_desc_cache = "\n".join(lines)
        return self._tools_desc_cache

    def _build_react_prompt(self) -> str:
        """
        构建 prompt，严格控制在 MAX_INPUT_TOKENS 以内。

        策略：
        1. 先构建固定部分（系统指令 + 工具描述 + 输出格式），计算基础 token
        2. 剩余 token 预算全部分配给历史轨迹
        3. _build_trajectory 在预算内自适应压缩
        """
        tools_desc = self._get_tools_description()

        # ── 固定部分模板（精简后的 prompt） ──
        system_part = textwrap.dedent(
            f"""
            你是ReAct模式的学习资料整理Agent。
            任务：围绕"{self.topic}"，面向"{self.audience}"，在目录 {self.output_dir} 中生成教学文档。
            文档要求：含主标题、目录、学习目标、概念与例子、总结。

            工具：
            {tools_desc}

            返回JSON：
            {{"thought":"思考","action":"tool或finish","tool_name":"工具名","tool_input":{{}},"final_answer":"finish时填写"}}

            要求：先list_dir检查目录；用write_file/append_file写完整内容；确认完成才finish；只返回JSON。
            """
        ).strip()

        base_tokens = self._estimate_tokens(system_part)
        trajectory_budget = self.MAX_INPUT_TOKENS - base_tokens - 50  # 留 50 token 余量

        if trajectory_budget < 100:
            # 极端情况：基础部分已经接近上限，不附加轨迹
            self._log(f"token 预算紧张，基础占 {base_tokens}，轨迹预算仅 {trajectory_budget}")
            return system_part

        summary_text, recent_json = self._build_trajectory(trajectory_budget)

        # ── 组装最终 prompt ──
        parts = [system_part]
        if summary_text:
            parts.append(f"\n历史摘要：\n{summary_text}")
        if recent_json and recent_json != "[]":
            parts.append(f"\n最近轮次：\n{recent_json}")

        prompt = "\n".join(parts)

        # ── 最终兜底检查 ──
        final_tokens = self._estimate_tokens(prompt)
        if final_tokens > self.MAX_INPUT_TOKENS:
            # 强制截断到字符上限（保守按 1.5 字符/token）
            max_chars = int(self.MAX_INPUT_TOKENS * 1.5)
            prompt = prompt[:max_chars] + "\n...(已截断)"
            self._log(f"最终 prompt {final_tokens} tokens 超限，已强制截断")

        self._log(f"prompt 预估 {self._estimate_tokens(prompt)} tokens")
        return prompt

    @staticmethod
    def _format_tool_result(result: ToolResult) -> str:
        return json.dumps(
            {
                "tool_name": result.tool_name,
                "success": result.success,
                "message": result.message,
                "payload": result.payload,
            },
            ensure_ascii=False,
            indent=2,
        )

    def render_report(self) -> str:
        lines = [
            "=== ReAct Study Material Agent ===",
            f"主题：{self.topic}",
            f"适用人群：{self.audience}",
            f"输出目录：{self.output_dir}",
            f"是否检测到 LLM：{self.state.llm_available}",
            f"LLM 决策轮数：{self.state.llm_rounds}",
            f"工具调用次数：{self.state.tool_calls}",
            "",
            "[执行轨迹]",
        ]

        for step in self.state.steps:
            lines.extend(
                [
                    f"{step.round_id}. Thought：{step.thought}",
                    f"   Action：{step.action}",
                    f"   Action Input：{json.dumps(step.action_input, ensure_ascii=False)}",
                    f"   Observation：{step.observation}",
                ]
            )

        lines.extend(["", "[最终结果]", self.state.final_answer or "任务结束"])
        return "\n".join(lines)

    @staticmethod
    def _log(message: str) -> None:
        print(f"[StudyMaterialReActAgent] {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="学习资料整理 ReAct Agent")
    parser.add_argument("topic", help="要生成资料的主题，例如：RAG 入门")
    parser.add_argument("--audience", default="初学者", help="目标读者，默认是 初学者")
    parser.add_argument("--output", default="", help="输出目录")
    parser.add_argument("--max-rounds", type=int, default=20, help="最大 ReAct 轮数")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    topic = args.topic.strip()
    if not topic:
        print("主题不能为空。")
        return 1

    if args.output:
        output_dir = Path(args.output).expanduser().resolve()
    else:
        project_root = Path(__file__).resolve().parent
        output_dir = project_root / "generated" / slugify(topic)

    agent = StudyMaterialReActAgent(
        topic=topic,
        audience=args.audience.strip() or "初学者",
        output_dir=output_dir,
        max_rounds=args.max_rounds,
    )

    try:
        state = agent.run()
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1

    print()
    print(agent.render_report())
    return 0 if state.completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
