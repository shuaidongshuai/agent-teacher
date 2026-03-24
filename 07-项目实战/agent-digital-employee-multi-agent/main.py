#!/usr/bin/env python3
"""
一个基于 LangGraph 的 Multi-Agent 数字员工示例。

升级后的版本比上一版多了两层能力：
1. 真实 LLM 调用：兼容 chat_completions / responses 两种接口风格
2. 工具执行层：专家 Agent 不只输出文本，还能规划并调用本地工具

项目中的核心角色：
1. Coordinator Agent：理解需求并拆任务
2. Dispatcher Agent：按 owner 把任务路由给不同专家
3. HR / Scheduler / Reporter / Ops Agent：分别完成各自职责
4. Tool Executor：执行专家 Agent 规划出来的工具调用
5. Reviewer Agent：补充风险提示和缺口检查
6. Synthesizer Agent：汇总所有结果，生成最终交付物
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import textwrap
import traceback
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

try:
    from typing import TypedDict
except ImportError:  # pragma: no cover
    from typing_extensions import TypedDict

try:
    from langgraph.graph import END, START, StateGraph
except ImportError as exc:  # pragma: no cover
    raise SystemExit("未安装 langgraph，请先运行：pip install -r requirements.txt") from exc

ROOT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT_DIR / "output"
DATA_DIR = ROOT_DIR / "data"
TOOL_DIR = DATA_DIR / "tool_outputs"

for directory in (OUTPUT_DIR, DATA_DIR, TOOL_DIR):
    directory.mkdir(parents=True, exist_ok=True)

TaskOwner = Literal["hr", "scheduler", "reporter", "ops"]
LLM_CLIENT: "OpenAIMultiAgentClient | None" = None
AUTO_APPROVE_HIGH_RISK = True


@dataclass
class TaskItem:
    """表示一个交给某个专家 Agent 的子任务。"""

    task_id: str
    owner: TaskOwner
    title: str
    objective: str
    difficulty_note: str = ""


class WorkflowState(TypedDict, total=False):
    """LangGraph 在节点之间共享的状态。"""

    user_request: str
    normalized_request: dict[str, Any]
    pending_tasks: list[dict[str, Any]]
    active_task: dict[str, Any] | None
    task_results: dict[str, str]
    execution_log: list[str]
    review_notes: list[str]
    risks: list[str]
    final_response: str
    pending_tool_calls: list[dict[str, Any]]
    current_tool_outputs: list[dict[str, Any]]
    draft_result: str
    approval_notes: list[str]


class OpenAIMultiAgentClient:
    """负责统一发起 OpenAI 兼容接口请求。"""

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/")
        self.model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
        self.api_style = self._read_api_style()
        self.ssl_verify = self._read_ssl_verify_setting()
        self.debug = os.getenv("LLM_DEBUG", "false").strip().lower() not in {"0", "false", "no", "off"}

        if not self.api_key:
            raise SystemExit("未检测到 OPENAI_API_KEY。这个项目现在要求真实 LLM，请先配置 API Key。")

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        """请求模型并提取纯文本输出。"""

        payload = self._build_payload(system_prompt, user_prompt)
        raw_body = self._post(payload)
        data = json.loads(raw_body)
        text_output = self._extract_text_output(data)
        if not text_output:
            raise RuntimeError(f"模型没有返回可解析文本。原始响应：{raw_body}")
        return text_output.strip()

    def generate_json(self, system_prompt: str, user_prompt: str) -> Any:
        """请求模型并解析 JSON。"""

        raw_text = self.generate_text(system_prompt, user_prompt)
        return json.loads(self._extract_json(raw_text))

    def _read_api_style(self) -> str:
        api_style = os.getenv("OPENAI_API_STYLE", "responses").strip().lower()
        if api_style not in {"responses", "chat_completions"}:
            return "responses"
        return api_style

    def _read_ssl_verify_setting(self) -> bool:
        raw = os.getenv("OPENAI_SSL_VERIFY", "true").strip().lower()
        return raw not in {"0", "false", "no", "off"}

    def _build_api_url(self) -> str:
        if self.base_url.endswith("/v1"):
            api_base = self.base_url
        else:
            api_base = f"{self.base_url}/v1"

        if self.api_style == "chat_completions":
            return f"{api_base}/chat/completions"
        return f"{api_base}/responses"

    def _build_payload(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if self.api_style == "chat_completions":
            return {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt.strip()},
                    {"role": "user", "content": user_prompt.strip()},
                ],
                "temperature": 0.2,
            }

        return {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt.strip()}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt.strip()}],
                },
            ],
        }

    def _build_ssl_context(self) -> ssl.SSLContext:
        if self.ssl_verify:
            return ssl.create_default_context()
        context = ssl._create_unverified_context()
        return context

    def _post(self, payload: dict[str, Any]) -> str:
        if self.debug:
            print("【LLM 请求入参】")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            print("=" * 60 + "\n")

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
                    timeout=120,
                    context=self._build_ssl_context(),
            ) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = ""
            try:
                error_body = exc.read().decode("utf-8")
            except Exception:
                pass
            raise RuntimeError(
                f"LLM 请求失败，HTTP {exc.code}：{error_body or exc.reason}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                "LLM 请求发生异常："
                f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            ) from exc

        if self.debug:
            print("【LLM 响应】")
            # 响应可能很大，只打印关键部分
            try:
                resp_data = json.loads(raw_body)
                # 打印简化版响应
                simplified = self._simplify_response(resp_data)
                print(json.dumps(simplified, ensure_ascii=False, indent=2))
            except Exception:
                print(raw_body[:2000])
            print("=" * 60 + "\n")

        return raw_body

    def _simplify_response(self, data: dict[str, Any]) -> dict[str, Any]:
        """简化响应数据，只保留关键部分用于调试。"""
        if self.api_style == "chat_completions":
            choices = data.get("choices", [])
            if choices:
                first_choice = choices[0]
                message = first_choice.get("message", {})
                return {
                    "model": data.get("model"),
                    "choices": [{
                        "index": first_choice.get("index"),
                        "message": {
                            "role": message.get("role"),
                            "content": message.get("content", "")[:1000] if message.get("content") else ""
                        },
                        "finish_reason": first_choice.get("finish_reason")
                    }],
                    "usage": data.get("usage")
                }
            return data
        else:
            output = data.get("output", [])
            if output:
                return {
                    "model": data.get("model"),
                    "output": [{
                        "id": output[0].get("id"),
                        "type": output[0].get("type"),
                        "content": str(output[0].get("content", ""))[:500]
                    }],
                    "usage": data.get("usage")
                }
            return data

    def _extract_text_output(self, data: dict[str, Any]) -> str:
        if self.api_style == "chat_completions":
            choices = data.get("choices", [])
            if not choices:
                return ""
            message = choices[0].get("message", {})
            content = message.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts: list[str] = []
                for item in content:
                    if isinstance(item, dict):
                        parts.append(str(item.get("text", "")))
                    else:
                        parts.append(str(item))
                return "\n".join(part for part in parts if part)
            return str(content)

        output = data.get("output", [])
        parts: list[str] = []
        for item in output:
            for content_item in item.get("content", []):
                if content_item.get("type") == "output_text":
                    parts.append(str(content_item.get("text", "")))
        if parts:
            return "\n".join(part for part in parts if part)
        return str(data.get("output_text", ""))

    def _extract_json(self, text: str) -> str:
        fenced_match = re.search(r"```json\s*(.*?)\s*```", text, re.S)
        if fenced_match:
            return fenced_match.group(1).strip()

        generic_match = re.search(r"```(?:\w+)?\s*(.*?)\s*```", text, re.S)
        if generic_match:
            return generic_match.group(1).strip()

        return text.strip()


def get_llm_client() -> OpenAIMultiAgentClient:
    """获取已初始化的全局 LLM 客户端。"""

    if LLM_CLIENT is None:  # pragma: no cover
        raise RuntimeError("LLM 客户端尚未初始化。")
    return LLM_CLIENT


def append_log(state: WorkflowState, message: str) -> list[str]:
    """往执行日志里追加一条记录。"""

    return [*state.get("execution_log", []), message]


def log_node(node_name: str):
    """节点日志装饰器：打印节点执行信息。"""
    def decorator(func):
        def wrapper(state: WorkflowState) -> WorkflowState:
            print(f"\n{'='*50}")
            print(f"【进入节点】{node_name}")
            print(f"{'='*50}")
            result = func(state)
            print(f"【离开节点】{node_name}")
            print(f"{'='*50}\n")
            return result
        return wrapper
    return decorator


def append_note(state: WorkflowState, message: str) -> list[str]:
    """往审批备注里追加一条记录。"""

    return [*state.get("approval_notes", []), message]


def build_task(
        task_id: str,
        owner: TaskOwner,
        title: str,
        objective: str,
        difficulty_note: str = "",
) -> dict[str, Any]:
    """把 dataclass 转成普通字典，方便写入图状态。"""

    return asdict(
        TaskItem(
            task_id=task_id,
            owner=owner,
            title=title,
            objective=objective,
            difficulty_note=difficulty_note,
        )
    )


def infer_request_fallback(user_request: str) -> dict[str, Any]:
    """当 LLM 结构化输出不完整时，用规则做保底补全。"""

    employee_match = re.search(r"新员工([\u4e00-\u9fa5A-Za-z0-9]{1,12})", user_request)
    employee_name = employee_match.group(1) if employee_match else "新同事"

    time_match = re.search(r"(周[一二三四五六日天][上下]午|周[一二三四五六日天]|\d{1,2}[:：]\d{2})", user_request)
    time_hint = time_match.group(1) if time_match else "本周内"

    needs_onboarding = any(keyword in user_request for keyword in ["入职", "新人", "新员工"])
    needs_schedule = any(keyword in user_request for keyword in ["会议", "日程", "培训", "安排"])
    needs_report = any(keyword in user_request for keyword in ["汇报", "总结", "摘要", "报告"])

    difficulty_flags: list[str] = []
    if any(keyword in user_request for keyword in ["审批", "预算", "权限", "对外发送"]):
        difficulty_flags.append("该请求涉及审批、权限或对外发送，真实场景中应先经过人工确认。")

    tasks: list[dict[str, Any]] = []
    if needs_onboarding:
        tasks.append(build_task("task_hr", "hr", "生成入职计划", f"为 {employee_name} 制定第一周入职计划。"))
    if needs_schedule:
        tasks.append(build_task("task_scheduler", "scheduler", "生成排期建议", f"围绕 {time_hint} 生成排期建议。"))
    if needs_report:
        tasks.append(build_task("task_reporter", "reporter", "生成主管汇报摘要", "整理为主管可直接阅读的摘要。"))
    if not tasks:
        tasks.append(build_task("task_ops", "ops", "输出综合处理建议", "先给出兜底处理方案。"))

    return {
        "employee_name": employee_name,
        "time_hint": time_hint,
        "needs_onboarding": needs_onboarding,
        "needs_schedule": needs_schedule,
        "needs_report": needs_report,
        "difficulty_flags": difficulty_flags,
        "task_count": len(tasks),
        "tasks": tasks,
    }


def normalize_tasks(raw_tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把 LLM 输出的任务列表整理成统一格式。"""

    tasks: list[dict[str, Any]] = []
    for index, raw_task in enumerate(raw_tasks, start=1):
        owner = str(raw_task.get("owner", "ops")).strip().lower()
        if owner not in {"hr", "scheduler", "reporter", "ops"}:
            owner = "ops"

        tasks.append(
            build_task(
                task_id=str(raw_task.get("task_id") or f"task_{owner}_{index}"),
                owner=owner,  # type: ignore[arg-type]
                title=str(raw_task.get("title") or f"{owner} 子任务"),
                objective=str(raw_task.get("objective") or "请完成该子任务。"),
                difficulty_note=str(raw_task.get("difficulty_note") or ""),
            )
        )
    return tasks


def normalize_tool_calls(raw_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把 LLM 规划出的工具调用整理成统一格式。"""

    allowed_names = {"create_onboarding_checklist", "create_calendar_event", "draft_notification"}
    normalized: list[dict[str, Any]] = []

    for index, item in enumerate(raw_calls, start=1):
        tool_name = str(item.get("tool_name") or "").strip()
        if tool_name not in allowed_names:
            continue
        arguments = item.get("arguments", {})
        if not isinstance(arguments, dict):
            arguments = {}
        normalized.append(
            {
                "call_id": str(item.get("call_id") or f"tool_call_{index}"),
                "tool_name": tool_name,
                "reason": str(item.get("reason") or ""),
                "arguments": arguments,
            }
        )

    return normalized[:3]


def _json_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _json_dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def tool_create_onboarding_checklist(arguments: dict[str, Any]) -> dict[str, Any]:
    """生成本地 onboarding checklist 文件。"""

    employee_name = str(arguments.get("employee_name") or "新同事")
    mentor = str(arguments.get("mentor") or "待分配导师")
    file_path = TOOL_DIR / f"onboarding_{employee_name}.md"
    markdown = textwrap.dedent(
        f"""
        # {employee_name} 入职检查清单

        - [ ] 完成人事报到
        - [ ] 领取办公设备
        - [ ] 开通系统账号
        - [ ] 与导师 {mentor} 完成首次对接
        - [ ] 阅读岗位资料与团队规范
        """
    ).strip()
    file_path.write_text(markdown + "\n", encoding="utf-8")
    return {
        "tool_name": "create_onboarding_checklist",
        "status": "success",
        "summary": f"已生成入职检查清单：{file_path.name}",
        "artifact_path": str(file_path),
    }


def tool_create_calendar_event(arguments: dict[str, Any]) -> dict[str, Any]:
    """把会议或培训事件写入本地 calendar.json，模拟真实日历接入。"""

    calendar_path = TOOL_DIR / "calendar_events.json"
    payload = _json_load(calendar_path, {"events": []})
    event = {
        "title": str(arguments.get("title") or "待确认会议"),
        "time": str(arguments.get("time") or "待确认时间"),
        "attendees": arguments.get("attendees") if isinstance(arguments.get("attendees"), list) else [],
        "location": str(arguments.get("location") or "待定"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    payload["events"].append(event)
    _json_dump(calendar_path, payload)
    return {
        "tool_name": "create_calendar_event",
        "status": "success",
        "summary": f"已写入本地日历事件：{event['title']} @ {event['time']}",
        "artifact_path": str(calendar_path),
    }


def tool_draft_notification(arguments: dict[str, Any]) -> dict[str, Any]:
    """生成一份通知草稿文件，模拟消息系统接入。"""

    notifications_path = TOOL_DIR / "notification_drafts.json"
    payload = _json_load(notifications_path, {"drafts": []})
    draft = {
        "channel": str(arguments.get("channel") or "email"),
        "recipient": str(arguments.get("recipient") or "待确认收件人"),
        "subject": str(arguments.get("subject") or "数字员工通知草稿"),
        "message": str(arguments.get("message") or ""),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    payload["drafts"].append(draft)
    _json_dump(notifications_path, payload)
    return {
        "tool_name": "draft_notification",
        "status": "success",
        "summary": f"已生成通知草稿：{draft['channel']} -> {draft['recipient']}",
        "artifact_path": str(notifications_path),
    }


def execute_tool_call(tool_call: dict[str, Any]) -> dict[str, Any]:
    """根据 tool_name 分发到具体工具实现。"""

    tool_name = tool_call["tool_name"]
    arguments = tool_call.get("arguments", {})

    if tool_name == "create_onboarding_checklist":
        return tool_create_onboarding_checklist(arguments)
    if tool_name == "create_calendar_event":
        return tool_create_calendar_event(arguments)
    if tool_name == "draft_notification":
        return tool_draft_notification(arguments)

    return {
        "tool_name": tool_name,
        "status": "skipped",
        "summary": f"未识别工具：{tool_name}",
        "artifact_path": "",
    }


@log_node("Coordinator")
def coordinator_node(state: WorkflowState) -> WorkflowState:
    """Coordinator Agent：用 LLM 理解请求并拆分子任务。"""

    client = get_llm_client()
    system_prompt = """
你是一个数字员工系统中的 Coordinator Agent。
你的职责是理解用户请求，并把大任务拆成结构化子任务。

你必须只返回 JSON，不要返回解释。
"""
    user_prompt = f"""
请分析下面这个数字员工请求，并返回 JSON：

用户请求：
{state["user_request"]}

JSON 格式：
{{
  "employee_name": "员工名，没有就写 新同事",
  "time_hint": "时间线索，没有就写 本周内",
  "needs_onboarding": true,
  "needs_schedule": true,
  "needs_report": true,
  "difficulty_flags": ["风险1", "风险2"],
  "tasks": [
    {{
      "task_id": "task_hr",
      "owner": "hr | scheduler | reporter | ops",
      "title": "子任务标题",
      "objective": "子任务目标",
      "difficulty_note": "当前子任务的实现难点"
    }}
  ]
}}

要求：
1. 如果请求涉及入职，必须至少生成一个 hr 任务。
2. 如果请求涉及排期、会议、培训时间，必须至少生成一个 scheduler 任务。
3. 如果请求涉及汇报、摘要、总结，必须至少生成一个 reporter 任务。
4. 如果无法准确分类，可以生成一个 ops 兜底任务。
5. difficulty_flags 要反映真实难点，比如审批、跨系统联动、排期冲突、权限边界。
"""

    normalized = client.generate_json(system_prompt, user_prompt)
    if not isinstance(normalized, dict):
        normalized = {}
    fallback = infer_request_fallback(state["user_request"])

    tasks = normalize_tasks(normalized.get("tasks", []))
    if not tasks:
        tasks = fallback["tasks"]

    merged = {
        "employee_name": str(normalized.get("employee_name") or fallback["employee_name"]),
        "time_hint": str(normalized.get("time_hint") or fallback["time_hint"]),
        "needs_onboarding": bool(normalized.get("needs_onboarding", fallback["needs_onboarding"])),
        "needs_schedule": bool(normalized.get("needs_schedule", fallback["needs_schedule"])),
        "needs_report": bool(normalized.get("needs_report", fallback["needs_report"])),
        "difficulty_flags": list(normalized.get("difficulty_flags", fallback["difficulty_flags"])),
        "task_count": len(tasks),
        "tasks": tasks,
    }

    return {
        "normalized_request": merged,
        "pending_tasks": tasks,
        "active_task": None,
        "task_results": {},
        "review_notes": [],
        "risks": [],
        "pending_tool_calls": [],
        "current_tool_outputs": [],
        "draft_result": "",
        "approval_notes": [],
        "execution_log": append_log(state, f"Coordinator 已调用 LLM 完成任务拆解，共 {len(tasks)} 个子任务。"),
    }


@log_node("Approval Gate")
def approval_gate_node(state: WorkflowState) -> WorkflowState:
    """审批门：高风险任务先打上审批标记。"""

    difficulty_flags = list(state.get("normalized_request", {}).get("difficulty_flags", []))
    high_risk_keywords = ["审批", "预算", "权限", "对外", "发送"]
    need_approval = any(any(keyword in flag for keyword in high_risk_keywords) for flag in difficulty_flags)

    if not need_approval:
        return {
            "approval_notes": append_note(state, "Approval Gate：当前请求未识别到必须人工审批的高风险项。"),
            "execution_log": append_log(state, "Approval Gate 已检查风险，当前无需额外审批。"),
        }

    if AUTO_APPROVE_HIGH_RISK:
        return {
            "approval_notes": append_note(
                state,
                "Approval Gate：检测到高风险事项，教学模式下已自动放行，但真实场景建议接入人工审批节点。",
            ),
            "execution_log": append_log(state, "Approval Gate 检测到高风险任务，已按自动审批模式继续执行。"),
        }

    return {
        "approval_notes": append_note(
            state,
            "Approval Gate：检测到高风险事项，当前未自动审批。真实系统应在这里暂停并等待人工确认。",
        ),
        "execution_log": append_log(state, "Approval Gate 检测到高风险任务，但当前未自动审批。"),
    }


@log_node("Dispatcher")
def dispatcher_node(state: WorkflowState) -> WorkflowState:
    """Dispatcher Agent：把当前任务路由到对应专家。"""

    pending_tasks = list(state.get("pending_tasks", []))
    if not pending_tasks:
        return {
            "active_task": None,
            "execution_log": append_log(state, "Dispatcher 发现待办队列为空，准备进入 Reviewer。"),
        }

    active_task = pending_tasks.pop(0)
    return {
        "active_task": active_task,
        "pending_tasks": pending_tasks,
        "execution_log": append_log(
            state,
            f"Dispatcher 已将 `{active_task['title']}` 路由给 `{active_task['owner']}` Agent。",
        ),
    }


def dispatch_by_owner(state: WorkflowState) -> str:
    """根据 active_task.owner 决定下一跳。"""

    active_task = state.get("active_task")
    if not active_task:
        return "reviewer"
    return str(active_task["owner"])


def render_context_for_agent(state: WorkflowState) -> str:
    """把共享状态压缩成适合提示词消费的上下文。"""

    normalized = state.get("normalized_request", {})
    active_task = state.get("active_task") or {}
    previous_results = state.get("task_results", {})
    approval_notes = state.get("approval_notes", [])

    return textwrap.dedent(
        f"""
        原始用户请求：
        {state.get("user_request", "")}

        当前结构化上下文：
        {json.dumps(normalized, ensure_ascii=False, indent=2)}

        当前子任务：
        {json.dumps(active_task, ensure_ascii=False, indent=2)}

        已完成子任务结果：
        {json.dumps(previous_results, ensure_ascii=False, indent=2)}

        审批备注：
        {json.dumps(approval_notes, ensure_ascii=False, indent=2)}
        """
    ).strip()


def run_specialist_agent(state: WorkflowState, role_name: str, role_brief: str, extra_rules: str) -> WorkflowState:
    """统一执行各类专家 Agent 的 LLM 调用，并让它先规划工具调用。"""

    client = get_llm_client()
    active_task = state.get("active_task") or {}

    system_prompt = f"""
你是数字员工系统中的 {role_name}。
你的角色职责：
{role_brief}

你需要先产出该子任务的 Markdown 草稿，再判断是否需要调用工具。

你必须只返回 JSON，不要返回解释。
"""
    user_prompt = f"""
{render_context_for_agent(state)}

可用工具：
1. create_onboarding_checklist
   作用：生成本地入职检查清单
   arguments 示例：{{"employee_name":"小王","mentor":"张老师"}}
2. create_calendar_event
   作用：把会议或培训写入本地 calendar_events.json
   arguments 示例：{{"title":"新员工培训","time":"周三下午 14:00","attendees":["HR","主管","导师"],"location":"会议室A"}}
3. draft_notification
   作用：生成一份消息或邮件通知草稿
   arguments 示例：{{"channel":"email","recipient":"manager@example.com","subject":"培训安排","message":"请查收安排"}}

请返回 JSON：
{{
  "markdown": "你的 Markdown 结果",
  "tool_calls": [
    {{
      "call_id": "call_1",
      "tool_name": "create_onboarding_checklist | create_calendar_event | draft_notification",
      "reason": "为什么需要这个工具",
      "arguments": {{}}
    }}
  ]
}}

要求：
1. markdown 必须是完整可读结果。
2. 如果确实有必要，可以规划 0 到 2 个工具调用。
3. 不要伪造工具执行结果，工具结果由系统后续节点补充。
4. {extra_rules}
"""

    planned = client.generate_json(system_prompt, user_prompt)
    if not isinstance(planned, dict):
        planned = {}

    draft_result = str(planned.get("markdown") or "")
    if not draft_result:
        draft_result = f"## {role_name} 输出\n\n当前模型没有返回有效 Markdown，建议人工复核。"

    tool_calls = normalize_tool_calls(planned.get("tool_calls", []))

    return {
        "draft_result": draft_result,
        "pending_tool_calls": tool_calls,
        "current_tool_outputs": [],
        "execution_log": append_log(
            state,
            f"{role_name} 已通过真实 LLM 完成内容草稿，并规划了 {len(tool_calls)} 个工具调用。",
        ),
    }


@log_node("HR Agent")
def hr_agent_node(state: WorkflowState) -> WorkflowState:
    """HR Agent：用 LLM 生成入职计划。"""

    return run_specialist_agent(
        state,
        role_name="HR Agent",
        role_brief="负责新人入职计划、培训安排、导师机制和第一周节奏设计。",
        extra_rules="优先给出一周计划；如有必要，可调用 create_onboarding_checklist。",
    )


@log_node("Scheduler Agent")
def scheduler_agent_node(state: WorkflowState) -> WorkflowState:
    """Scheduler Agent：用 LLM 生成会议排期建议。"""

    return run_specialist_agent(
        state,
        role_name="Scheduler Agent",
        role_brief="负责把会议、培训、沟通环节排成一个可执行的时间建议方案。",
        extra_rules="优先给出排期建议；如有必要，可调用 create_calendar_event 或 draft_notification。",
    )


@log_node("Reporter Agent")
def reporter_agent_node(state: WorkflowState) -> WorkflowState:
    """Reporter Agent：用 LLM 生成给主管的汇报摘要。"""

    return run_specialist_agent(
        state,
        role_name="Reporter Agent",
        role_brief="负责基于其他 Agent 已有结果，为主管整理一份可直接阅读的执行摘要。",
        extra_rules="站在主管汇报视角组织内容；通常不需要工具，除非需要通知草稿。",
    )


@log_node("Ops Agent")
def ops_agent_node(state: WorkflowState) -> WorkflowState:
    """Ops Agent：用 LLM 输出兜底方案。"""

    return run_specialist_agent(
        state,
        role_name="Ops Agent",
        role_brief="负责在任务不明确或无法归类时给出稳妥的通用处理建议。",
        extra_rules="优先输出清晰流程与人工确认点；必要时可以规划通知草稿。",
    )


def route_after_specialist(state: WorkflowState) -> str:
    """判断专家 Agent 之后是否进入工具执行层。"""

    if state.get("pending_tool_calls"):
        return "tool_executor"
    return "commit_result"


@log_node("Tool Executor")
def tool_executor_node(state: WorkflowState) -> WorkflowState:
    """执行专家 Agent 规划出来的工具调用。"""

    tool_outputs: list[dict[str, Any]] = []
    for tool_call in state.get("pending_tool_calls", []):
        output = execute_tool_call(tool_call)
        output["reason"] = tool_call.get("reason", "")
        tool_outputs.append(output)

    return {
        "current_tool_outputs": tool_outputs,
        "execution_log": append_log(state, f"Tool Executor 已执行 {len(tool_outputs)} 个工具调用。"),
    }


@log_node("Commit Result")
def commit_result_node(state: WorkflowState) -> WorkflowState:
    """把专家草稿和工具结果合并成最终任务结果。"""

    active_task = state.get("active_task") or {}
    task_id = str(active_task.get("task_id", "unknown_task"))
    draft_result = state.get("draft_result", "").strip()
    tool_outputs = state.get("current_tool_outputs", [])

    if tool_outputs:
        tool_section_lines = ["### 工具执行结果"]
        for output in tool_outputs:
            summary = str(output.get("summary", ""))
            artifact_path = str(output.get("artifact_path", ""))
            if artifact_path:
                tool_section_lines.append(f"- {summary}，产物：`{artifact_path}`")
            else:
                tool_section_lines.append(f"- {summary}")
        final_task_result = draft_result + "\n\n" + "\n".join(tool_section_lines)
    else:
        final_task_result = draft_result

    task_results = dict(state.get("task_results", {}))
    task_results[task_id] = final_task_result
    return {
        "task_results": task_results,
        "active_task": None,
        "draft_result": "",
        "pending_tool_calls": [],
        "current_tool_outputs": [],
        "execution_log": append_log(state, f"Commit Result 已完成 `{task_id}` 的结果落库。"),
    }


@log_node("Reviewer")
def reviewer_node(state: WorkflowState) -> WorkflowState:
    """Reviewer Agent：用 LLM 检查结果完整性和风险。"""

    client = get_llm_client()
    system_prompt = """
你是数字员工系统中的 Reviewer Agent。
你的职责是检查多 Agent 结果是否完整，并指出真实落地时的风险与缺口。

只返回 JSON，不要返回解释。
"""
    user_prompt = f"""
请基于下面上下文做审核：

{render_context_for_agent(state)}

额外材料：
- difficulty_flags: {json.dumps(state.get("normalized_request", {}).get("difficulty_flags", []), ensure_ascii=False)}
- approval_notes: {json.dumps(state.get("approval_notes", []), ensure_ascii=False)}

请返回 JSON：
{{
  "review_notes": ["审核结论 1", "审核结论 2"],
  "risks": ["风险 1", "风险 2"]
}}

要求：
1. review_notes 要覆盖结果完整性、职责边界、是否需要人工确认。
2. risks 要强调真实接入外部系统时的难点。
3. 如果已有结果明显不完整，要直接指出缺失项。
4. 如果检测到工具调用只是本地模拟，也要明确指出。
"""

    reviewed = client.generate_json(system_prompt, user_prompt)
    if not isinstance(reviewed, dict):
        reviewed = {}

    review_notes = [str(item) for item in reviewed.get("review_notes", [])]
    risks = [str(item) for item in reviewed.get("risks", [])]

    if not review_notes:
        review_notes = ["Reviewer 未拿到足够结构化反馈，建议人工检查子任务结果是否完整。"]
    if not risks:
        risks = ["当前项目已接真实 LLM 和本地工具层，但仍未接入真实审批、日历和企业系统。"]

    return {
        "review_notes": review_notes,
        "risks": risks,
        "execution_log": append_log(state, "Reviewer 已通过真实 LLM 完成审核。"),
    }


@log_node("Synthesizer")
def synthesizer_node(state: WorkflowState) -> WorkflowState:
    """Synthesizer Agent：用 LLM 汇总所有结果。"""

    client = get_llm_client()
    system_prompt = """
你是数字员工系统中的 Synthesizer Agent。
你的职责是把多个 Agent 的结果整理成一个完整、清晰、可交付的最终文档。

输出要求：
1. 使用中文 Markdown。
2. 必须包含：请求摘要、各 Agent 产出整合、审批与工具执行说明、审核结论、实现难点、下一步建议。
3. 不要省略关键风险。
"""
    user_prompt = f"""
请整合下面的多 Agent 结果，生成最终交付内容：

原始请求：
{state["user_request"]}

结构化上下文：
{json.dumps(state.get("normalized_request", {}), ensure_ascii=False, indent=2)}

各 Agent 结果：
{json.dumps(state.get("task_results", {}), ensure_ascii=False, indent=2)}

审批备注：
{json.dumps(state.get("approval_notes", []), ensure_ascii=False, indent=2)}

Reviewer 结论：
{json.dumps(state.get("review_notes", []), ensure_ascii=False, indent=2)}

风险提示：
{json.dumps(state.get("risks", []), ensure_ascii=False, indent=2)}

执行日志：
{json.dumps(state.get("execution_log", []), ensure_ascii=False, indent=2)}
"""

    final_response = client.generate_text(system_prompt, user_prompt)
    return {
        "final_response": final_response,
        "execution_log": append_log(state, "Synthesizer 已通过真实 LLM 生成最终交付物。"),
    }


def build_graph():
    """构建 LangGraph 工作流。"""

    workflow = StateGraph(WorkflowState)

    workflow.add_node("coordinator", coordinator_node)
    workflow.add_node("approval_gate", approval_gate_node)
    workflow.add_node("dispatcher", dispatcher_node)
    workflow.add_node("hr", hr_agent_node)
    workflow.add_node("scheduler", scheduler_agent_node)
    workflow.add_node("reporter", reporter_agent_node)
    workflow.add_node("ops", ops_agent_node)
    workflow.add_node("tool_executor", tool_executor_node)
    workflow.add_node("commit_result", commit_result_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("synthesizer", synthesizer_node)

    workflow.add_edge(START, "coordinator")
    workflow.add_edge("coordinator", "approval_gate")
    workflow.add_edge("approval_gate", "dispatcher")
    workflow.add_conditional_edges(
        "dispatcher",
        dispatch_by_owner,
        {
            "hr": "hr",
            "scheduler": "scheduler",
            "reporter": "reporter",
            "ops": "ops",
            "reviewer": "reviewer",
        },
    )
    workflow.add_conditional_edges(
        "hr",
        route_after_specialist,
        {"tool_executor": "tool_executor", "commit_result": "commit_result"})
    workflow.add_conditional_edges(
        "scheduler",
        route_after_specialist,
        {"tool_executor": "tool_executor", "commit_result": "commit_result"},
    )
    workflow.add_conditional_edges(
        "reporter",
        route_after_specialist,
        {"tool_executor": "tool_executor", "commit_result": "commit_result"},
    )
    workflow.add_conditional_edges(
        "ops",
        route_after_specialist,
        {"tool_executor": "tool_executor", "commit_result": "commit_result"})
    workflow.add_edge("tool_executor", "commit_result")
    workflow.add_edge("commit_result", "dispatcher")
    workflow.add_edge("reviewer", "synthesizer")
    workflow.add_edge("synthesizer", END)

    return workflow.compile()


def save_outputs(result: WorkflowState, output_dir: Path) -> tuple[Path, Path]:
    """保存最终交付物和中间轨迹。"""

    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "final_result.md"
    trace_path = output_dir / "trace.json"

    markdown_path.write_text(result["final_response"], encoding="utf-8")
    trace_payload = {
        "normalized_request": result.get("normalized_request", {}),
        "task_results": result.get("task_results", {}),
        "approval_notes": result.get("approval_notes", []),
        "review_notes": result.get("review_notes", []),
        "risks": result.get("risks", []),
        "execution_log": result.get("execution_log", []),
    }
    trace_path.write_text(json.dumps(trace_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return markdown_path, trace_path


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(description="LangGraph Multi-Agent 数字员工示例")
    parser.add_argument("request", help="用户请求，例如：为新员工小王安排入职与培训计划")
    parser.add_argument(
        "--output-dir",
        default=str(OUTPUT_DIR),
        help="输出目录，默认写入项目内 output 目录",
    )
    parser.add_argument(
        "--no-auto-approve-high-risk",
        action="store_true",
        help="关闭高风险任务的自动审批模拟",
    )
    return parser.parse_args()


def main() -> None:
    """程序入口。"""

    global LLM_CLIENT
    global AUTO_APPROVE_HIGH_RISK

    args = parse_args()
    AUTO_APPROVE_HIGH_RISK = not args.no_auto_approve_high_risk
    LLM_CLIENT = OpenAIMultiAgentClient()

    graph = build_graph()
    result = graph.invoke({"user_request": args.request})

    output_dir = Path(args.output_dir).resolve()
    markdown_path, trace_path = save_outputs(result, output_dir)

    print(result["final_response"])
    print("\n---")
    print(f"结果已写入：{markdown_path}")
    print(f"轨迹已写入：{trace_path}")


if __name__ == "__main__":
    main()
