#!/usr/bin/env python3
"""
最小 MCP 服务端示例。

教学目标：
1. 用最少的代码展示 MCP 的核心交互
2. 同时暴露 Tools / Resources / Prompts
3. 不依赖外部 SDK，便于直接阅读协议消息
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROTOCOL_VERSION = "2025-03-26"
SERVER_INFO = {"name": "course-study-mcp", "version": "0.1.0"}
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


def log(message: str) -> None:
    print(f"[mcp_server] {message}", file=sys.stderr, flush=True)


def safe_rel_path(path: Path) -> str:
    return path.relative_to(WORKSPACE_ROOT).as_posix()


def list_markdown_files() -> List[Path]:
    excluded_parts = {".git", "__pycache__"}
    files: List[Path] = []
    for path in WORKSPACE_ROOT.rglob("*.md"):
        if any(part in excluded_parts for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def build_resource_uri(path: Path) -> str:
    # 用一个稳定的自定义 URI，把本地文件映射成 MCP Resource。
    return f"course://{safe_rel_path(path)}"


def parse_resource_uri(uri: str) -> Optional[Path]:
    prefix = "course://"
    if not uri.startswith(prefix):
        return None
    relative = uri[len(prefix) :].strip()
    if not relative:
        return None

    # 只允许读取工作区里的文件，避免通过伪造 URI 访问工作区外路径。
    candidate = (WORKSPACE_ROOT / relative).resolve()
    try:
        candidate.relative_to(WORKSPACE_ROOT)
    except ValueError:
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate


def summarize_text(text: str, limit: int = 140) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def extract_first_heading(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return "未命名文档"


def top_markdown_resources(limit: int = 30) -> List[Dict[str, Any]]:
    resources: List[Dict[str, Any]] = []
    for path in list_markdown_files()[:limit]:
        content = path.read_text(encoding="utf-8", errors="ignore")
        resources.append(
            {
                "uri": build_resource_uri(path),
                "name": extract_first_heading(content),
                "description": summarize_text(content),
                "mimeType": "text/markdown",
            }
        )
    return resources


def keyword_score(query: str, text: str, title: str) -> int:
    tokens = [token.lower() for token in re.split(r"\s+", query.strip()) if token]
    if not tokens:
        return 0
    lower_text = text.lower()
    lower_title = title.lower()
    score = 0
    for token in tokens:
        # 标题命中比正文命中更重要，方便把更相关的讲义排在前面。
        score += lower_text.count(token)
        score += lower_title.count(token) * 3
    return score


def tool_search_docs(arguments: Dict[str, Any]) -> Dict[str, Any]:
    query = str(arguments.get("query", "")).strip()
    limit = int(arguments.get("limit", 5))
    limit = max(1, min(limit, 10))

    if not query:
        return {"query": query, "matches": [], "message": "query 不能为空"}

    matches: List[Dict[str, Any]] = []
    for path in list_markdown_files():
        content = path.read_text(encoding="utf-8", errors="ignore")
        title = extract_first_heading(content)
        score = keyword_score(query, content, title)
        if score <= 0:
            continue
        matches.append(
            {
                "title": title,
                "path": safe_rel_path(path),
                "uri": build_resource_uri(path),
                "score": score,
                "preview": summarize_text(content, limit=160),
            }
        )

    matches.sort(key=lambda item: (-item["score"], item["path"]))
    return {"query": query, "matches": matches[:limit], "total": len(matches)}


def tool_build_study_plan(arguments: Dict[str, Any]) -> Dict[str, Any]:
    topic = str(arguments.get("topic", "")).strip() or "MCP"
    days = int(arguments.get("days", 7))
    days = max(1, min(days, 30))

    found = tool_search_docs({"query": topic, "limit": min(days, 6)})
    references = found.get("matches", [])

    plan: List[Dict[str, Any]] = []
    if not references:
        references = [{"title": f"{topic} 入门", "path": "未找到现成文档，可先自己搭大纲"}]

    for index, item in enumerate(references, start=1):
        # 直接复用搜索结果，把“找到资料”和“生成计划”串成一条教学链路。
        plan.append(
            {
                "day": index,
                "goal": f"学习 {item['title']}",
                "action": f"阅读 {item['path']}，整理核心概念、问题边界和一个例子",
                "deliverable": "一页笔记或一个最小实验",
            }
        )

    while len(plan) < days:
        current_day = len(plan) + 1
        plan.append(
            {
                "day": current_day,
                "goal": f"{topic} 复盘与实战补充",
                "action": "回看前面资料，补一轮练习题或把最小 demo 改一版",
                "deliverable": "复盘记录和待改进项",
            }
        )

    return {"topic": topic, "days": days, "plan": plan}


TOOLS = [
    # Tools 是“可执行动作”，客户端可以通过 tools/list 发现它们。
    {
        "name": "search_docs",
        "title": "搜索课程文档",
        "description": "按关键词搜索仓库中的 Markdown 教学资料。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "limit": {
                    "type": "integer",
                    "description": "最多返回条数，默认 5，最大 10",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "build_study_plan",
        "title": "生成学习计划",
        "description": "根据主题和天数，为学习者生成一个简单学习计划。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "学习主题"},
                "days": {"type": "integer", "description": "计划天数，默认 7", "default": 7},
            },
            "required": ["topic"],
        },
        "annotations": {"readOnlyHint": True},
    },
]


PROMPTS = [
    # Prompt 单独暴露出来，是为了演示 MCP 不只支持工具，也支持提示模板复用。
    {
        "name": "explain_topic",
        "title": "讲解主题",
        "description": "生成一个适合教学讲解的 Prompt 模板。",
        "arguments": [
            {"name": "topic", "required": True, "description": "要讲解的主题"},
            {"name": "audience", "required": False, "description": "受众，默认初学者"},
        ],
    }
]


def make_response(request_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def make_error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_initialize(request_id: Any) -> Dict[str, Any]:
    return make_response(
        request_id,
        {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"listChanged": False},
                "prompts": {"listChanged": False},
            },
            "serverInfo": SERVER_INFO,
        },
    )


def handle_tools_list(request_id: Any) -> Dict[str, Any]:
    return make_response(request_id, {"tools": TOOLS})


def handle_tools_call(request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    name = params.get("name")
    arguments = params.get("arguments", {})

    if name == "search_docs":
        payload = tool_search_docs(arguments)
    elif name == "build_study_plan":
        payload = tool_build_study_plan(arguments)
    else:
        return make_error(request_id, -32601, f"未知工具: {name}")

    return make_response(
        request_id,
        {
            # 既返回文本，也返回结构化内容，方便不同客户端按需消费。
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
            "structuredContent": payload,
            "isError": False,
        },
    )


def handle_resources_list(request_id: Any) -> Dict[str, Any]:
    return make_response(request_id, {"resources": top_markdown_resources()})


def handle_resources_read(request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    uri = str(params.get("uri", ""))
    path = parse_resource_uri(uri)
    if path is None:
        return make_error(request_id, -32602, f"无效资源 URI: {uri}")

    content = path.read_text(encoding="utf-8", errors="ignore")
    return make_response(
        request_id,
        {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/markdown",
                    "text": content,
                }
            ]
        },
    )


def handle_prompts_list(request_id: Any) -> Dict[str, Any]:
    return make_response(request_id, {"prompts": PROMPTS})


def handle_prompts_get(request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    name = params.get("name")
    arguments = params.get("arguments", {})
    if name != "explain_topic":
        return make_error(request_id, -32601, f"未知 Prompt: {name}")

    topic = str(arguments.get("topic", "")).strip() or "MCP"
    audience = str(arguments.get("audience", "")).strip() or "初学者"
    prompt_text = (
        f"请面向{audience}讲解“{topic}”。"
        "要求包含：它是什么、解决什么问题、核心流程、常见误区、一个最小实践建议。"
        "优先使用教学语气，不只罗列定义。"
    )

    return make_response(
        request_id,
        {
            "description": f"面向{audience}讲解 {topic} 的教学 Prompt",
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": prompt_text},
                }
            ],
        },
    )


def handle_request(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params", {}) or {}

    # 这个分发函数就是最小 MCP 服务端的“路由表”。
    if method == "initialize":
        return handle_initialize(request_id)
    if method == "tools/list":
        return handle_tools_list(request_id)
    if method == "tools/call":
        return handle_tools_call(request_id, params)
    if method == "resources/list":
        return handle_resources_list(request_id)
    if method == "resources/read":
        return handle_resources_read(request_id, params)
    if method == "prompts/list":
        return handle_prompts_list(request_id)
    if method == "prompts/get":
        return handle_prompts_get(request_id, params)
    if method == "notifications/initialized":
        log("收到 initialized 通知")
        return None

    if request_id is None:
        log(f"忽略未知通知: {method}")
        return None
    return make_error(request_id, -32601, f"未知方法: {method}")


def main() -> int:
    log(f"workspace root = {WORKSPACE_ROOT}")
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            # 这里用一行一个 JSON-RPC 消息，保持示例尽量直观。
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            log(f"JSON 解析失败: {exc}")
            continue

        response = handle_request(message)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
