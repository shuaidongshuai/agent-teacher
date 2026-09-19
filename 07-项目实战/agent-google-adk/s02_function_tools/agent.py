"""关卡 02：函数工具（Function Tools）—— 让 Agent 会"动手"

学习目标：
  - 用普通 Python 函数当工具，交给 Agent 调用
  - 理解 ADK 靠"函数签名 + docstring"自动生成工具描述（所以类型标注和文档字符串很重要）
  - 工具建议返回 dict，并带一个 status 字段，方便模型判断成功/失败

运行：adk run s02_function_tools   或   adk web 后选择本关卡
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")


# ---- 工具就是普通函数：类型标注 + docstring 会被 ADK 读取成工具 schema ----
def get_weather(city: str) -> dict:
    """查询指定城市当前的天气情况。

    Args:
        city: 城市名，例如 "北京"、"上海"。

    Returns:
        dict: 含 status 与天气描述 report（失败时含 error_message）。
    """
    # 这里用假数据演示；真实场景可换成调用天气 API
    fake_db = {
        "北京": "晴，18℃，微风",
        "上海": "多云，22℃，东南风 3 级",
        "深圳": "阵雨，27℃，湿度较高",
    }
    if city in fake_db:
        return {"status": "success", "report": f"{city}当前天气：{fake_db[city]}"}
    return {"status": "error", "error_message": f"暂时查不到「{city}」的天气数据。"}


def get_current_time(city: str) -> dict:
    """查询指定城市的当前时间。

    Args:
        city: 城市名，目前支持 "北京"（东八区）。
    """
    tz_map = {"北京": "Asia/Shanghai", "上海": "Asia/Shanghai", "深圳": "Asia/Shanghai"}
    tz_name = tz_map.get(city)
    if not tz_name:
        return {"status": "error", "error_message": f"没有「{city}」的时区信息。"}
    now = datetime.now(ZoneInfo(tz_name))
    return {"status": "success", "report": now.strftime(f"{city}现在是 %Y-%m-%d %H:%M:%S")}


root_agent = Agent(
    name="weather_time_agent",
    model=MODEL,
    description="能查询城市天气和当前时间的助手。",
    instruction=(
        "你是生活助手。当用户问天气就调用 get_weather，问时间就调用 get_current_time。"
        "工具返回 status=error 时，把 error_message 用友好的话转述给用户，不要编造数据。"
    ),
    # 把函数直接塞进 tools 列表即可，ADK 会自动包装成工具
    tools=[get_weather, get_current_time],
)
