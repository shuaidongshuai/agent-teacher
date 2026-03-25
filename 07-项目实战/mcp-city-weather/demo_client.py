#!/usr/bin/env python3
"""
通用 MCP 客户端示例。

这个客户端演示：
1. 如何读取 mcp.json 配置
2. 如何连接多个 MCP Server
3. 如何发现每个服务暴露的工具
4. 如何按 server + tool + arguments 调用指定工具

兼容两种常见配置格式：
- {"mcpServers": {...}}  # Cursor 常见格式
- {"servers": {...}}     # VS Code 常见格式
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client


def parse_args() -> argparse.Namespace:
    default_config = Path(__file__).resolve().parent / "mcp.json"

    parser = argparse.ArgumentParser(description="通用 MCP 客户端")
    parser.add_argument("--config", default=str(default_config), help="mcp.json 配置文件路径")
    parser.add_argument("--server", help="要连接的 server 名称")
    parser.add_argument("--tool", help="要调用的 tool 名称")
    parser.add_argument(
        "--arguments",
        default="{}",
        help='工具参数，JSON 字符串，例如: \'{"city":"上海"}\'',
    )
    parser.add_argument("--list-only", action="store_true", help="只列出配置中的 server 和工具，不执行调用")
    parser.add_argument("--http-debug", action="store_true", help="打印服务端 HTTP 请求入参与返回值摘要")
    parser.add_argument("--verbose", action="store_true", help="打印详细结果")
    return parser.parse_args()


def load_mcp_config(path: str) -> dict[str, Any]:
    config_path = Path(path).expanduser().resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"未找到配置文件: {config_path}")

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    servers = payload.get("mcpServers") or payload.get("servers")
    if not isinstance(servers, dict) or not servers:
        raise ValueError("mcp.json 必须包含非空的 mcpServers 或 servers 字段")

    return {"path": config_path, "servers": servers}


def build_server_params(
    server_name: str,
    server_config: dict[str, Any],
    config_path: Path,
    http_debug: bool = False,
) -> StdioServerParameters:
    server_type = server_config.get("type", "stdio")
    if server_type != "stdio":
        raise ValueError(f"当前客户端只支持 stdio server，{server_name} 的 type={server_type}")

    command = server_config.get("command")
    if not command:
        raise ValueError(f"{server_name} 缺少 command 配置")

    args = server_config.get("args", [])
    if not isinstance(args, list):
        raise ValueError(f"{server_name} 的 args 必须是数组")

    env = server_config.get("env")
    cwd = server_config.get("cwd")
    if cwd:
        cwd = str((config_path.parent / cwd).resolve()) if not Path(cwd).is_absolute() else cwd

    merged_env = dict(os.environ)
    if isinstance(env, dict):
        merged_env.update({str(key): str(value) for key, value in env.items()})
    if http_debug:
        merged_env["MCP_HTTP_DEBUG"] = "1"

    return StdioServerParameters(
        command=command,
        args=[str(item) for item in args],
        env=merged_env,
        cwd=cwd,
    )


def print_tool_result(result: types.CallToolResult, verbose: bool = False) -> None:
    print("=== Tool Call Result ===")
    print(f"isError: {result.isError}")

    if result.structuredContent:
        print("structuredContent:")
        print(json.dumps(result.structuredContent, ensure_ascii=False, indent=2))

    if verbose and result.content:
        print("content blocks:")
        for block in result.content:
            if isinstance(block, types.TextContent):
                print(f"- TextContent: {block.text}")
            else:
                print(f"- {type(block).__name__}: {block}")


async def list_tools_for_server(
    server_name: str,
    server_config: dict[str, Any],
    config_path: Path,
    http_debug: bool = False,
) -> list[types.Tool]:
    server_params = build_server_params(server_name, server_config, config_path, http_debug=http_debug)
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            return tools.tools


async def call_tool_for_server(
    server_name: str,
    server_config: dict[str, Any],
    config_path: Path,
    tool_name: str,
    arguments: dict[str, Any],
    verbose: bool,
    http_debug: bool,
) -> None:
    server_params = build_server_params(server_name, server_config, config_path, http_debug=http_debug)
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = [tool.name for tool in tools.tools]

            print(f"=== Server: {server_name} ===")
            print(f"Available tools: {tool_names}")
            print()
            print(f"Calling tool: {tool_name}")
            print(f"Arguments: {json.dumps(arguments, ensure_ascii=False)}")
            print()

            result = await session.call_tool(tool_name, arguments=arguments)
            print_tool_result(result, verbose=verbose)


async def list_all_servers(config: dict[str, Any]) -> None:
    config_path: Path = config["path"]
    servers: dict[str, Any] = config["servers"]

    for server_name, server_config in servers.items():
        print(f"=== Server: {server_name} ===")
        try:
            tools = await list_tools_for_server(server_name, server_config, config_path)
            if not tools:
                print("(no tools)")
            for tool in tools:
                print(f"- {tool.name}: {tool.description or ''}")
        except Exception as exc:
            print(f"[ERROR] {server_name}: {exc}")
        print()


async def main_async() -> None:
    args = parse_args()
    config = load_mcp_config(args.config)
    config_path: Path = config["path"]
    servers: dict[str, Any] = config["servers"]

    if args.list_only or not args.server:
        await list_all_servers(config)
        return

    if args.server not in servers:
        available = ", ".join(sorted(servers.keys()))
        raise ValueError(f"未找到 server: {args.server}。可选值: {available}")

    if not args.tool:
        tools = await list_tools_for_server(args.server, servers[args.server], config_path)
        print(f"=== Server: {args.server} ===")
        for tool in tools:
            print(f"- {tool.name}: {tool.description or ''}")
        return

    arguments = json.loads(args.arguments)
    if not isinstance(arguments, dict):
        raise ValueError("--arguments 必须是 JSON object")

    await call_tool_for_server(
        server_name=args.server,
        server_config=servers[args.server],
        config_path=config_path,
        tool_name=args.tool,
        arguments=arguments,
        verbose=args.verbose,
        http_debug=args.http_debug,
    )


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
