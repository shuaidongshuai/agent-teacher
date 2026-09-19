"""进阶 02：接入 MCP 工具（MCPToolset）

学习目标：
  - 用 MCPToolset 把一个 MCP（Model Context Protocol）服务器暴露的工具接进 ADK
  - 理解 ADK 既能"提供"MCP，也能"消费"MCP —— 这里演示消费
  - 对比关卡 02 的函数工具：函数工具是本进程内的 Python 函数；
    MCP 工具来自一个【独立进程/服务】，通过标准协议通信，可复用整个 MCP 生态

本例接入官方文件系统 MCP 服务器（server-filesystem），让 Agent 能列目录、读文件。

前置条件（运行时才需要，import 不需要）：
  - 已安装 Node.js（提供 npx）
  - 首次运行会用 npx 自动拉起 @modelcontextprotocol/server-filesystem
  - Agent 只被授权访问下面 ALLOWED_DIR 这个目录（安全边界）

运行：adk run adv_02_mcp_tools   或   adk web 后选择本关卡
（试试问："列一下当前目录有哪些文件" / "读一下 __init__.py"）
"""

import os
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import MCPToolset, StdioConnectionParams
from mcp import StdioServerParameters

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")

# 只允许访问本关卡目录，作为文件系统工具的安全沙箱
ALLOWED_DIR = str(Path(__file__).parent.resolve())

root_agent = LlmAgent(
    name="filesystem_agent",
    model=MODEL,
    description="能通过 MCP 文件系统工具浏览、读取本地文件的助手。",
    instruction=(
        "你可以使用文件系统工具浏览和读取文件（仅限被授权的目录）。"
        "当用户想看目录内容或某个文件时，调用相应工具，再用中文清楚地转述结果。"
        "不要假装读到内容——一切以工具返回为准。"
    ),
    tools=[
        MCPToolset(
            # StdioConnectionParams：通过标准输入输出和 MCP 服务器进程通信
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="npx",
                    args=[
                        "-y",
                        "@modelcontextprotocol/server-filesystem",
                        ALLOWED_DIR,
                    ],
                ),
                timeout=30,
            )
            # 可选：tool_filter=["list_directory", "read_file"] 只暴露部分工具
        )
    ],
)
