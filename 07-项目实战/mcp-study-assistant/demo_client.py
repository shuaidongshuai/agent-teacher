#!/usr/bin/env python3
"""
最小 MCP 客户端示例。

这个客户端会：
1. 启动本地 MCP 服务端子进程
2. 发送 initialize / initialized
3. 发现 tools / resources / prompts
4. 调用搜索工具
5. 读取最相关文档
6. 获取一个教学 prompt
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

PROTOCOL_VERSION = "2025-03-26"
CLIENT_INFO = {"name": "study-demo-client", "version": "0.1.0"}


class McpClient:
    def __init__(self, server_script: Path, verbose: bool = False) -> None:
        self.server_script = server_script
        self.verbose = verbose
        self.request_id = 0
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        self.process = subprocess.Popen(
            # Windows 下显式开启 UTF-8，避免服务端输出中文时解码失败。
            [sys.executable, "-X", "utf8", str(server_script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env,
        )

        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("启动 MCP 服务端失败")

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def _next_id(self) -> int:
        self.request_id += 1
        return self.request_id

    def notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        payload: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._write(payload)

    def request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        request_id = self._next_id()
        payload: Dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._write(payload)
        response = self._read()

        # 最小客户端也要做基本校验，否则很难发现协议链路问题。
        if response.get("id") != request_id:
            raise RuntimeError(f"响应 id 不匹配: expected={request_id}, got={response.get('id')}")
        if "error" in response:
            raise RuntimeError(f"MCP 错误: {response['error']}")
        return response["result"]

    def _write(self, payload: Dict[str, Any]) -> None:
        if self.process.stdin is None:
            raise RuntimeError("服务端 stdin 不可用")
        wire = json.dumps(payload, ensure_ascii=False)
        if self.verbose:
            print(f"[client -> server] {wire}")
        self.process.stdin.write(wire + "\n")
        self.process.stdin.flush()

    def _read(self) -> Dict[str, Any]:
        if self.process.stdout is None:
            raise RuntimeError("服务端 stdout 不可用")

        while True:
            line = self.process.stdout.readline()
            if not line:
                stderr_output = ""
                if self.process.stderr is not None:
                    stderr_output = self.process.stderr.read()
                raise RuntimeError(f"服务端已退出。\n{stderr_output}")

            payload = json.loads(line)
            if self.verbose:
                print(f"[server -> client] {json.dumps(payload, ensure_ascii=False)}")
            return payload


def extract_tool_payload(tool_result: Dict[str, Any]) -> Dict[str, Any]:
    structured = tool_result.get("structuredContent")
    if isinstance(structured, dict):
        return structured

    # 某些客户端可能只依赖文本 content，这里保留一个兜底解析。
    content = tool_result.get("content", [])
    if content and isinstance(content[0], dict):
        text = content[0].get("text", "{}")
        return json.loads(text)
    return {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MCP 学习资料助手客户端")
    parser.add_argument("--query", default="MCP", help="文档搜索关键词")
    parser.add_argument("--topic", default="MCP", help="学习计划主题")
    parser.add_argument("--days", type=int, default=7, help="学习计划天数")
    parser.add_argument("--audience", default="初学者", help="Prompt 目标受众")
    parser.add_argument("--verbose", action="store_true", help="打印协议交互日志")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = Path(__file__).resolve().parent
    server_script = project_dir / "mcp_server.py"

    client = McpClient(server_script=server_script, verbose=args.verbose)
    try:
        # 先 initialize，再发送 initialized 通知，这是最小 MCP 握手流程。
        init_result = client.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"roots": {"listChanged": False}},
                "clientInfo": CLIENT_INFO,
            },
        )
        client.notify("notifications/initialized")

        tools = client.request("tools/list")
        resources = client.request("resources/list")
        prompts = client.request("prompts/list")

        search_result = client.request(
            "tools/call",
            {"name": "search_docs", "arguments": {"query": args.query, "limit": 5}},
        )
        search_payload = extract_tool_payload(search_result)
        matches = search_payload.get("matches", [])

        plan_result = client.request(
            "tools/call",
            {"name": "build_study_plan", "arguments": {"topic": args.topic, "days": args.days}},
        )
        plan_payload = extract_tool_payload(plan_result)

        resource_payload: Dict[str, Any] = {}
        if matches:
            # 读取搜索排名第一的文档，演示 Tool 和 Resource 是怎么串起来的。
            resource_payload = client.request("resources/read", {"uri": matches[0]["uri"]})

        prompt_payload = client.request(
            "prompts/get",
            {
                "name": "explain_topic",
                "arguments": {"topic": args.topic, "audience": args.audience},
            },
        )

        print("=== MCP Study Assistant Demo ===")
        print(f"协议版本: {init_result['protocolVersion']}")
        print(f"服务端: {init_result['serverInfo']['name']} {init_result['serverInfo']['version']}")
        print()

        print("[1] 服务端能力概览")
        print(f"- Tools: {', '.join(tool['name'] for tool in tools['tools'])}")
        print(f"- Resources: 共 {len(resources['resources'])} 个示例资源")
        print(f"- Prompts: {', '.join(prompt['name'] for prompt in prompts['prompts'])}")
        print()

        print(f"[2] 搜索结果: {args.query}")
        if matches:
            for index, item in enumerate(matches, start=1):
                print(f"{index}. {item['title']} ({item['path']})")
                print(f"   score={item['score']}")
                print(f"   preview={item['preview']}")
        else:
            print("未找到匹配文档。")
        print()

        print(f"[3] 学习计划: {args.topic} / {args.days} 天")
        for item in plan_payload.get("plan", []):
            print(f"Day {item['day']}: {item['goal']}")
            print(f"  action={item['action']}")
            print(f"  deliverable={item['deliverable']}")
        print()

        if resource_payload:
            first_content = resource_payload["contents"][0]
            preview_lines = first_content["text"].splitlines()[:12]
            print("[4] 读取首个资源")
            print(f"- URI: {first_content['uri']}")
            print("- 内容预览:")
            for line in preview_lines:
                print(f"  {line}")
            print()

        print("[5] Prompt 模板")
        print(f"- 描述: {prompt_payload['description']}")
        print(f"- 内容: {prompt_payload['messages'][0]['content']['text']}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
