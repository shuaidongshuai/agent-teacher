#!/usr/bin/env python3
"""
城市天气 MCP 服务。

教学目标：
1. 使用官方 Python MCP SDK 暴露一个真实可用的 Tool
2. 让 VS Code 等 MCP Host 通过 stdio 直接接入
3. 演示“城市名 -> 地理编码 -> 天气查询 -> 结构化结果”的完整链路
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("city-weather")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("city-weather")
HTTP_DEBUG_ENABLED = os.getenv("MCP_HTTP_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}

WEATHER_CODE_MAP = {
    0: "晴",
    1: "大部晴朗",
    2: "局部多云",
    3: "阴",
    45: "有雾",
    48: "冻雾",
    51: "毛毛雨",
    53: "中等毛毛雨",
    55: "强毛毛雨",
    56: "冻毛毛雨",
    57: "强冻毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨",
    67: "强冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "雪粒",
    80: "小阵雨",
    81: "中等阵雨",
    82: "强阵雨",
    85: "小阵雪",
    86: "强阵雪",
    95: "雷暴",
    96: "雷暴伴轻微冰雹",
    99: "雷暴伴强冰雹",
}


async def geocode_city(city: str) -> dict[str, Any] | None:
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": city,
        "count": 1,
        "language": "zh",
        "format": "json",
    }

    if HTTP_DEBUG_ENABLED:
        logger.info("[HTTP request] GET %s params=%s", url, params)

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()

    if HTTP_DEBUG_ENABLED:
        preview = payload.get("results", [])[:1]
        logger.info("[HTTP response] status=%s body_preview=%s", response.status_code, preview)

    results = payload.get("results") or []
    if not results:
        return None
    return results[0]


async def fetch_current_weather(latitude: float, longitude: float, timezone: str) -> dict[str, Any]:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
        "timezone": timezone,
        "forecast_days": 1,
    }

    if HTTP_DEBUG_ENABLED:
        logger.info("[HTTP request] GET %s params=%s", url, params)

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()

    if HTTP_DEBUG_ENABLED:
        logger.info(
            "[HTTP response] status=%s current=%s",
            response.status_code,
            payload.get("current"),
        )
    return payload


def build_clothing_advice(temperature: Any, weather_desc: str) -> str:
    try:
        value = float(temperature)
    except (TypeError, ValueError):
        return "建议根据实时体感温度灵活调整穿着。"

    if "雨" in weather_desc:
        if value < 12:
            return "今天偏凉且可能有雨，建议穿外套并带伞。"
        return "今天可能有雨，建议带伞，穿着以轻便防水为主。"
    if value < 8:
        return "气温较低，建议穿厚外套或羽绒服。"
    if value < 18:
        return "体感偏凉，建议穿长袖并备一件薄外套。"
    if value < 28:
        return "温度比较舒适，正常春秋装即可。"
    return "天气偏热，建议穿轻薄透气的衣物并注意补水。"


@mcp.tool()
async def get_city_weather(city: str) -> dict[str, Any]:
    """
    根据输入的城市名称查询当前天气。

    参数:
        city: 城市名，例如 上海、北京、Hangzhou、Tokyo
    """
    city = city.strip()
    if not city:
        return {"ok": False, "message": "city 不能为空"}

    try:
        location = await geocode_city(city)
        if location is None:
            return {"ok": False, "message": f"未找到城市: {city}"}

        matched_name = location.get("name", city)
        country = location.get("country", "")
        admin1 = location.get("admin1", "")
        latitude = float(location["latitude"])
        longitude = float(location["longitude"])
        timezone = location.get("timezone") or "Asia/Shanghai"

        weather_payload = await fetch_current_weather(latitude, longitude, timezone)
        current = weather_payload.get("current", {})
        weather_code = current.get("weather_code")
        weather_desc = WEATHER_CODE_MAP.get(weather_code, f"未知天气代码 {weather_code}")

        result = {
            "ok": True,
            "query_city": city,
            "matched_city": matched_name,
            "country": country,
            "region": admin1,
            "timezone": timezone,
            "latitude": latitude,
            "longitude": longitude,
            "time": current.get("time"),
            "temperature_c": current.get("temperature_2m"),
            "apparent_temperature_c": current.get("apparent_temperature"),
            "relative_humidity": current.get("relative_humidity_2m"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "weather_code": weather_code,
            "weather_desc": weather_desc,
        }
        result["clothing_advice"] = build_clothing_advice(
            result["apparent_temperature_c"], weather_desc
        )
        result["summary"] = (
            f"{matched_name}"
            f"{('，' + admin1) if admin1 else ''}"
            f"{('，' + country) if country else ''}"
            f"当前{weather_desc}，温度 {result['temperature_c']}°C，"
            f"体感 {result['apparent_temperature_c']}°C，"
            f"相对湿度 {result['relative_humidity']}%，"
            f"风速 {result['wind_speed_kmh']} km/h。"
        )

        logger.info("weather query success: city=%s matched=%s", city, matched_name)
        return result
    except httpx.HTTPError as exc:
        logger.exception("weather query failed due to network error")
        return {
            "ok": False,
            "message": f"天气服务请求失败: {exc}",
        }
    except Exception as exc:  # pragma: no cover - 教学项目保留兜底
        logger.exception("weather query failed due to unexpected error")
        return {
            "ok": False,
            "message": f"服务内部异常: {exc}",
        }


def main() -> None:
    # stdio 最适合 VS Code / Claude Desktop 这类本地宿主接入。
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
