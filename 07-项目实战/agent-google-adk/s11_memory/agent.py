"""关卡 11：记忆（State 短期记忆 + 跨会话长期记忆）

学习目标：
  - 短期记忆：同一次会话里，用 tool_context.state 读写状态，让 Agent 记住上下文
  - 长期记忆：跨会话保留用户偏好——这里用本地 JSON 文件做最小演示
  - 了解 ADK 原生方案（见文末注释）：InMemoryMemoryService + load_memory 工具

说明：ADK 里工具函数只要声明 tool_context: ToolContext 形参，ADK 就会自动注入，
     通过它可以访问 state、调用记忆服务等。

运行：adk run s11_memory   或   adk web 后选择本关卡
（先说"我更喜欢简短的回答"，再问它"你还记得我的偏好吗？"）
"""

import json
import os
from pathlib import Path

from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")

# 长期记忆落地到本地文件（演示用；生产可换数据库/向量库）
PROFILE_FILE = Path(__file__).parent / "user_profile.json"


def remember_preference(key: str, value: str, tool_context: ToolContext) -> dict:
    """记住用户的一条偏好。

    Args:
        key: 偏好名，如 "回答风格"、"称呼"。
        value: 偏好值，如 "简短"、"叫我老王"。
    """
    # 1) 写入会话 state（短期：本次会话内其他步骤可直接读）
    tool_context.state[f"pref:{key}"] = value
    # 2) 写入本地文件（长期：下次新会话也能读到）
    profile = _load_profile()
    profile[key] = value
    PROFILE_FILE.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "success", "message": f"已记住偏好：{key} = {value}"}


def recall_preferences(tool_context: ToolContext) -> dict:
    """回忆已记住的所有用户偏好（跨会话）。"""
    profile = _load_profile()
    if not profile:
        return {"status": "empty", "message": "目前还没有记录任何偏好。"}
    return {"status": "success", "preferences": profile}


def _load_profile() -> dict:
    if PROFILE_FILE.exists():
        try:
            return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


root_agent = Agent(
    name="memory_agent",
    model=MODEL,
    description="能记住并回忆用户偏好的助手。",
    instruction=(
        "你是有记忆的助手。"
        "当用户表达某种偏好（如喜欢简短回答、希望被怎么称呼），调用 remember_preference 记下来。"
        "当用户问你是否记得，或你需要按偏好调整回答时，调用 recall_preferences 查看。"
        "始终尽量遵守已记住的偏好。"
    ),
    tools=[remember_preference, recall_preferences],
)

# 进阶（ADK 原生长期记忆思路，供参考）：
#   from google.adk.memory import InMemoryMemoryService
#   from google.adk.tools import load_memory   # 让 Agent 主动检索历史会话
#   Runner 里传入 memory_service=InMemoryMemoryService()，
#   会话结束后 memory_service.add_session_to_memory(session)，
#   下次 Agent 用 load_memory 工具即可跨会话检索。
