# 导入未来版本的类型注解语法（Python 3.10+ 支持）
from __future__ import annotations

# 标准库导入
import json
import os
import re
import ssl
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from urllib.request import urlopen

# FastAPI 相关导入 - 用于构建 Web API
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# LangChain 相关导入 - 用于构建 LLM 和工具
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool

# LangGraph 相关导入 - 用于构建状态图和工作流
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

# Pydantic 用于数据验证
from pydantic import BaseModel
from typing_extensions import Annotated, TypedDict

# 可选：Open-Meteo 官方库（如果未安装则设为 None）
try:
    from open_meteo import OpenMeteo
    from open_meteo.models import DailyParameters
    OpenMeteoClient = OpenMeteo
except ImportError:  # pragma: no cover
    OpenMeteoClient = None

# 可选：LangChain OpenAI 集成（如果未安装则设为 None）
try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover
    ChatOpenAI = None


# ============ 项目常量定义 ============
ROOT_DIR = Path(__file__).resolve().parent  # 项目根目录
DATA_DIR = ROOT_DIR / "data"  # 数据存储目录
MEMORY_DIR = DATA_DIR / "memory"  # 长期记忆存储目录
SESSION_DIR = DATA_DIR / "sessions"  # 会话日志存储目录
STATIC_DIR = ROOT_DIR / "static"  # 静态文件目录（HTML/CSS/JS）

# 创建必要的目录（如果不存在）
for directory in (DATA_DIR, MEMORY_DIR, SESSION_DIR, STATIC_DIR):
    directory.mkdir(parents=True, exist_ok=True)


# ============ 数据模型定义 ============

# ChatState: LangGraph 图的状态定义
# 这是整个图的核心状态结构，在各个节点之间传递
class ChatState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]  # 消息历史（自动合并）
    user_profile: dict[str, Any]  # 用户画像（从长期记忆提取的事实）
    memory_summary: str  # 记忆摘要（最近几轮对话的概要）


# ChatRequest: API 请求模型
# 用于 /api/chat 接口的请求体验证
class ChatRequest(BaseModel):
    thread_id: str | None = None  # 会话线程 ID（可选，用于区分不同对话）
    message: str  # 用户发送的消息


# ============ 工具函数 ============

# 创建不验证 SSL 证书的上下文（用于解决 macOS/Windows 上的证书问题）
def _create_unverified_context():
    return ssl.create_default_context() if hasattr(ssl, 'create_default_context') else None


# 安全的 urlopen 封装，自动处理 SSL 证书问题
def _urlopen(url: str, timeout: int = 10):
    # 创建不验证 SSL 证书的上下文
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return urlopen(url, timeout=timeout, context=ctx)

# 从 JSON 文件加载数据，如果文件不存在则返回默认值
def _json_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


# 将数据保存到 JSON 文件（自动创建父目录）
def _json_dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


# 从各种格式的 LangChain 消息中提取纯文本内容
# 支持：字符串、包含 "type": "text" 的字典、多部分内容
def _message_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(part for part in parts if part)
    return str(content)


# 获取当前时间的 ISO 格式字符串（精确到秒）
def _iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ============ 长期记忆存储类 ============
# 负责将用户的长期记忆（个人信息、偏好、备注、摘要）保存到本地 JSON 文件
# 每个 thread_id 对应一个 JSON 文件，实现多用户/多会话的记忆隔离

class PersistentMemoryStore:
    def __init__(self, memory_dir: Path):
        self.memory_dir = memory_dir

    # 根据 thread_id 生成对应的 JSON 文件路径
    def _path_for(self, thread_id: str) -> Path:
        return self.memory_dir / f"{thread_id}.json"

    # 加载指定会话的记忆记录
    # 如果文件不存在，返回默认的空记录结构
    def load(self, thread_id: str) -> dict[str, Any]:
        return _json_load(
            self._path_for(thread_id),
            {
                "thread_id": thread_id,
                "facts": {},  # 用户事实（如姓名、城市、职业等）
                "notes": [],  # 用户要求记住的事项
                "summary": "",  # 最近对话的摘要
                "updated_at": _iso_now(),
            },
        )

    # 保存记忆记录到文件（自动更新时间戳）
    def save(self, thread_id: str, record: dict[str, Any]) -> None:
        record["updated_at"] = _iso_now()
        _json_dump(self._path_for(thread_id), record)

    # 从文本中提取用户事实信息
    # 使用正则表达式匹配：姓名、城市、工作地点、角色、喜欢/不喜欢的事物
    def extract_facts(self, text: str) -> tuple[dict[str, Any], list[str]]:
        facts: dict[str, Any] = {}
        notes: list[str] = []
        patterns = [
            (r"我叫([A-Za-z0-9_\u4e00-\u9fa5]{1,20})", "name"),
            (r"你可以叫我([A-Za-z0-9_\u4e00-\u9fa5]{1,20})", "name"),
            (r"我来自([\u4e00-\u9fa5A-Za-z]{2,20})", "city"),
            (r"我住在([\u4e00-\u9fa5A-Za-z]{2,20})", "city"),
            (r"我在([\u4e00-\u9fa5A-Za-z]{2,20})工作", "job_location"),
            (r"我是([\u4e00-\u9fa5A-Za-z]{2,20})", "role"),
        ]
        for pattern, key in patterns:
            match = re.search(pattern, text)
            if match:
                facts[key] = match.group(1).strip()

        # 匹配"我喜欢..."模式
        like_match = re.search(r"我喜欢(.+)", text)
        if like_match:
            facts["likes"] = like_match.group(1).strip("。！! ")

        # 匹配"我不喜欢..."模式
        dislike_match = re.search(r"我不喜欢(.+)", text)
        if dislike_match:
            facts["dislikes"] = dislike_match.group(1).strip("。！! ")

        # 匹配"请记住..."模式（用户要求记住的事项）
        remember_match = re.search(r"请记住(.+)", text)
        if remember_match:
            notes.append(remember_match.group(1).strip("。！! "))

        return facts, notes

    # 更新长期记忆：提取新事实、备注，并根据最近用户消息更新摘要
    # 注意：这里不再保存完整对话原文，原文应该进入会话日志而不是长期记忆
    def update(
        self,
        thread_id: str,
        user_text: str,
        assistant_text: str,
        recent_user_topics: list[str] | None = None,
    ) -> dict[str, Any]:
        record = self.load(thread_id)
        facts, notes = self.extract_facts(user_text)
        record["facts"].update(facts)
        for note in notes:
            if note and note not in record["notes"]:
                record["notes"].append(note)
        latest_topics = [topic.strip() for topic in (recent_user_topics or [user_text]) if topic.strip()][-4:]
        if latest_topics:
            record["summary"] = "最近重要话题：" + "；".join(latest_topics)
        self.save(thread_id, record)
        return record


# ============ 会话日志存储类 ============
# 负责保存完整的对话原文，属于会话级/短中期记录，不等同于长期记忆

class SessionHistoryStore:
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir

    def _path_for(self, thread_id: str) -> Path:
        return self.session_dir / f"{thread_id}.json"

    def load(self, thread_id: str) -> dict[str, Any]:
        return _json_load(
            self._path_for(thread_id),
            {
                "thread_id": thread_id,
                "history": [],
                "updated_at": _iso_now(),
            },
        )

    def save(self, thread_id: str, record: dict[str, Any]) -> None:
        record["updated_at"] = _iso_now()
        _json_dump(self._path_for(thread_id), record)

    def append_turn(self, thread_id: str, user_text: str, assistant_text: str) -> dict[str, Any]:
        record = self.load(thread_id)
        record["history"].extend(
            [
                {"role": "user", "content": user_text, "created_at": _iso_now()},
                {"role": "assistant", "content": assistant_text, "created_at": _iso_now()},
            ]
        )
        record["history"] = record["history"][-40:]
        self.save(thread_id, record)
        return record


# ============ 日历/日程存储类 ============
# 负责管理本地日历事件，支持添加和查询日程
# 数据存储在 data/calendar.json 文件中

class CalendarStore:
    def __init__(self, path: Path):
        self.path = path

    # 从 JSON 文件加载所有日程
    def _load(self) -> list[dict[str, str]]:
        return _json_load(self.path, [])

    # 保存日程列表到 JSON 文件
    def _save(self, events: list[dict[str, str]]) -> None:
        _json_dump(self.path, events)

    # 添加新日程
    # 参数：标题、开始时间、结束时间、备注（可选）
    # 时间必须使用 ISO 格式（如：2024-01-15T10:00）
    def add_event(self, title: str, start_time: str, end_time: str, note: str = "") -> dict[str, str]:
        # 验证时间格式是否有效
        datetime.fromisoformat(start_time)
        datetime.fromisoformat(end_time)
        events = self._load()
        event = {
            "id": str(uuid.uuid4())[:8],  # 生成短 UUID 作为唯一标识
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "note": note,
        }
        events.append(event)
        # 按开始时间排序
        events.sort(key=lambda item: item["start_time"])
        self._save(events)
        return event

    # 查询日程列表
    # 如果指定了 day 参数，则只返回该日期的日程（格式：YYYY-MM-DD）
    # 否则返回最近 10 条日程
    def list_events(self, day: str = "") -> list[dict[str, str]]:
        events = self._load()
        if not day:
            return events[-10:]
        return [event for event in events if event["start_time"].startswith(day)]


# ============ 工具注册中心 ============
# 简单的工具注册表，用于管理 Agent 可用的所有工具

class ToolRegistry:
    def __init__(self):
        self._tools: list[BaseTool] = []

    # 注册一个工具
    def register(self, tool_obj: BaseTool) -> None:
        self._tools.append(tool_obj)

    # 获取所有已注册的工具
    def all(self) -> list[BaseTool]:
        return list(self._tools)


# ============ LangGraph 聊天 Agent 核心类 ============
# 这是整个项目的核心类，整合了：
# - LLM（大语言模型）
# - 工具（天气查询、网络搜索、日历管理）
# - 记忆系统（短期记忆 + 长期记忆）
# - 状态图工作流

class LangGraphChatAgent:
    # 初始化：创建所有组件
    def __init__(self):
        self.memory_store = PersistentMemoryStore(MEMORY_DIR)  # 长期记忆存储
        self.session_store = SessionHistoryStore(SESSION_DIR)  # 会话日志存储
        self.calendar_store = CalendarStore(DATA_DIR / "calendar.json")  # 日历存储
        self.registry = ToolRegistry()  # 工具注册中心
        self._register_default_tools()  # 注册默认工具
        self.tools = self.registry.all()  # 获取所有工具
        self.tool_node = ToolNode(self.tools)  # LangGraph 工具节点
        self.checkpointer = MemorySaver()  # 短期记忆检查点（内存）
        self.llm = self._build_llm()  # 构建 LLM
        self.graph = self._build_graph()  # 构建状态图

    # 构建 LLM（支持 OpenAI API）
    # 如果没有设置 OPENAI_API_KEY，则返回 None（使用本地 fallback 模式）
    def _build_llm(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or ChatOpenAI is None:
            return None
        return ChatOpenAI(
            api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL"),
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,  # 温度为 0，保持回答的确定性
        )

    # 注册默认工具：
    # 1. web_search - 网络搜索（使用 DuckDuckGo API）
    # 2. get_weather - 天气查询（使用 Open-Meteo API）
    # 3. calendar_add_event - 添加日程
    # 4. calendar_list_events - 查看日程
    def _register_default_tools(self) -> None:
        calendar_store = self.calendar_store

        @tool
        def web_search(query: str) -> str:
            """Search public web information for a topic."""
            try:
                # 使用 DuckDuckGo 开放 API 进行搜索
                url = (
                    "https://api.duckduckgo.com/"
                    f"?q={quote_plus(query)}&format=json&no_html=1&skip_disambig=1"
                )
                with _urlopen(url, timeout=10) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                # 提取搜索结果：摘要、来源、相关主题
                answer = payload.get("AbstractText", "").strip()
                source = payload.get("AbstractURL", "").strip()
                related_topics = payload.get("RelatedTopics", [])[:3]
                lines: list[str] = []
                if answer:
                    lines.append(f"摘要: {answer}")
                if source:
                    lines.append(f"来源: {source}")
                for topic in related_topics:
                    if isinstance(topic, dict):
                        text = topic.get("Text", "").strip()
                        topic_url = topic.get("FirstURL", "").strip()
                        if text:
                            lines.append(f"- {text}")
                        if topic_url:
                            lines.append(f"  {topic_url}")
                if not lines:
                    return "没有找到足够可靠的公开结果，可以换一个更具体的关键词再试一次。"
                return "\n".join(lines)
            except Exception as exc:  # pragma: no cover
                return f"网络搜索暂时失败：{exc}"

        @tool
        def get_weather(city: str) -> str:
            """Get current weather for a city."""
            try:
                # 使用地理编码 API 获取城市坐标
                geo_url = (
                    "https://geocoding-api.open-meteo.com/v1/search"
                    f"?name={quote_plus(city)}&count=1&language=zh&format=json"
                )
                with _urlopen(geo_url, timeout=10) as response:
                    geo_payload = json.loads(response.read().decode("utf-8"))
                results = geo_payload.get("results") or []
                if not results:
                    return f"没有找到城市 {city} 的地理信息。"
                location = results[0]
                latitude = location["latitude"]
                longitude = location["longitude"]

                # 使用 Open-Meteo 官方库获取天气数据
                if OpenMeteoClient is not None:
                    import asyncio

                    async def fetch_weather():
                        async with OpenMeteoClient() as client:
                            forecast = await client.forecast(
                                latitude=latitude,
                                longitude=longitude,
                                current_weather=True,
                            )
                            return forecast.current

                    current = asyncio.run(fetch_weather())
                else:
                    # Fallback: 直接使用 API
                    weather_url = (
                        "https://api.open-meteo.com/v1/forecast"
                        f"?latitude={latitude}"
                        f"&longitude={longitude}"
                        "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m"
                        "&timezone=auto"
                    )
                    with _urlopen(weather_url, timeout=10) as response:
                        weather_payload = json.loads(response.read().decode("utf-8"))
                    current = weather_payload.get("current", {})

                # 天气代码映射（WMO 天气代码）
                weather_map = {
                    0: "晴朗",
                    1: "大致晴朗",
                    2: "局部多云",
                    3: "阴天",
                    45: "有雾",
                    61: "小雨",
                    63: "中雨",
                    65: "大雨",
                    71: "小雪",
                    80: "阵雨",
                    95: "雷暴",
                }
                description = weather_map.get(current.get("weather_code"), "天气情况未知")
                return (
                    f"{location['name']} 当前天气：{description}，"
                    f"气温 {current.get('temperature_2m')}°C，"
                    f"体感 {current.get('apparent_temperature')}°C，"
                    f"湿度 {current.get('relative_humidity_2m')}%，"
                    f"风速 {current.get('wind_speed_10m')} km/h。"
                )
            except Exception as exc:  # pragma: no cover
                return f"天气查询暂时失败：{exc}"

        @tool
        def calendar_add_event(title: str, start_time: str, end_time: str, note: str = "") -> str:
            """Add an event into the local calendar. Time must use ISO format."""
            event = calendar_store.add_event(
                title=title,
                start_time=start_time,
                end_time=end_time,
                note=note,
            )
            return (
                f"已创建日程 {event['title']}，"
                f"开始时间 {event['start_time']}，结束时间 {event['end_time']}。"
            )

        @tool
        def calendar_list_events(day: str = "") -> str:
            """List events in the local calendar. Day format is YYYY-MM-DD."""
            events = calendar_store.list_events(day=day)
            if not events:
                return "当前没有匹配的日程。"
            lines = ["日程列表："]
            for event in events:
                line = f"- {event['title']} | {event['start_time']} -> {event['end_time']}"
                if event.get("note"):
                    line += f" | 备注: {event['note']}"
                lines.append(line)
            return "\n".join(lines)

        # 将所有工具注册到注册中心
        for tool_obj in (web_search, get_weather, calendar_add_event, calendar_list_events):
            self.registry.register(tool_obj)

    # ============ 构建 LangGraph 状态图 ============
    # 图结构：
    # START -> hydrate_memory -> assistant -> (条件路由)
    #                                      |
    #                    +-----------------+-----------------+
    #                    |                                   |
    #                  "tools"                           "persist_memory"
    #                    |                                   |
    #                    +---> assistant (循环)           -> END
    #
    # 说明：
    # 1. hydrate_memory: 加载用户长期记忆
    # 2. assistant: 调用 LLM 生成回复（可能触发工具调用）
    # 3. tools: 执行工具调用
    # 4. persist_memory: 保存对话到长期记忆
    def _build_graph(self):
        graph = StateGraph(ChatState)

        # 添加 4 个节点
        graph.add_node("hydrate_memory", self.hydrate_memory)
        graph.add_node("assistant", self.assistant_node)
        graph.add_node("tools", self.tool_node)
        graph.add_node("persist_memory", self.persist_memory)

        # 设置边（节点之间的连接）
        graph.add_edge(START, "hydrate_memory")  # 开始 -> 加载记忆
        graph.add_edge("hydrate_memory", "assistant")  # 加载记忆 -> AI 回复

        # 条件边：根据 assistant 的输出决定下一步
        # - 如果有 tool_calls，跳转到 tools 节点
        # - 否则跳转到 persist_memory 节点
        graph.add_conditional_edges(
            "assistant",
            self.route_after_assistant,
            {"tools": "tools", "persist_memory": "persist_memory"},
        )
        graph.add_edge("tools", "assistant")  # 工具执行完后回到 AI 节点（循环）
        graph.add_edge("persist_memory", END)  # 保存记忆后结束

        # 使用 MemorySaver 作为检查点，支持多轮对话
        return graph.compile(checkpointer=self.checkpointer)

    # ============ 图节点实现 ============

    # hydrate_memory 节点：从长期存储加载用户记忆
    def hydrate_memory(self, state: ChatState, config: RunnableConfig) -> ChatState:
        thread_id = config["configurable"]["thread_id"]
        record = self.memory_store.load(thread_id)
        return {
            "user_profile": record.get("facts", {}),
            "memory_summary": record.get("summary", ""),
        }

    # assistant 节点：AI 对话核心节点
    # 1. 如果没有配置 LLM，使用本地规则引擎（fallback 模式）
    # 2. 否则调用 LLM + 工具生成回复
    def assistant_node(self, state: ChatState, config: RunnableConfig) -> ChatState:
        if self.llm is None:
            ai_message = self.local_assistant(state, config)
            return {"messages": [ai_message]}

        # 构建系统提示词，包含用户画像和记忆摘要
        profile = json.dumps(state.get("user_profile", {}), ensure_ascii=False)
        summary = state.get("memory_summary", "") or "暂无长期记忆。"
        system_prompt = (
            "你是一个教学示例里的自定义 LangGraph 聊天 Agent。"
            "你的任务是和用户自然聊天，并在需要时主动调用工具。"
            "请优先体现以下能力：\n"
            "1. 记忆：结合已知用户信息和最近话题继续对话。\n"
            "2. 工具：需要事实、天气、日历时优先调用工具。\n"
            "3. 调度：多轮使用工具时要先获取信息，再组织成最终回答。\n"
            "4. 风格：回答清晰、友好、偏中文教学表达。\n\n"
            f"已知用户画像：{profile}\n"
            f"最近记忆摘要：{summary}\n"
            "如果用户要求你记住某件事，请在回答里明确告诉对方你已经记住了。"
        )

        # 构建消息列表
        messages = [SystemMessage(content=system_prompt), *state["messages"]]

        # ============ 打印 LLM 请求入参 ============
        print("\n" + "=" * 60)
        print("【LLM 请求入参】")
        print("-" * 60)
        for i, msg in enumerate(messages):
            role = type(msg).__name__.replace("Message", "")
            content_preview = _message_text(msg)[:400] + "..." if len(_message_text(msg)) > 100 else _message_text(msg)
            # 如果是 AI 消息且包含工具调用，额外打印工具调用信息
            if isinstance(msg, AIMessage) and msg.tool_calls:
                print(f"  [{i}] {role}: {content_preview}")
                print(f"       └── tool_calls: {msg.tool_calls}")
            else:
                print(f"  [{i}] {role}: {content_preview}")
        print("-" * 60)

        # 绑定工具并调用 LLM
        llm_with_tools = self.llm.bind_tools(self.tools)
        response = llm_with_tools.invoke(messages)

        # ============ 打印 LLM 返回值 ============
        print("【LLM 返回值】")
        print("-" * 60)
        if response.tool_calls:
            print(f"  类型: 工具调用")
            print(f"  内容: {response.content[:400] if response.content else '(空)'}")
            print(f"  tool_calls:")
            for tc in response.tool_calls:
                print(f"    - name: {tc['name']}")
                print(f"      args: {json.dumps(tc['args'], ensure_ascii=False)}")
        else:
            print(f"  类型: 文本回复")
            content_preview = response.content[:500] + "..." if len(response.content) > 500 else response.content
            print(f"  内容: {content_preview}")
        print("=" * 60 + "\n")

        return {"messages": [response]}

    # 条件路由函数：判断 assistant 节点之后的下一步
    # - 如果 AI 消息包含 tool_calls，说明需要调用工具
    # - 否则直接保存记忆
    def route_after_assistant(self, state: ChatState) -> str:
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        return "persist_memory"

    # persist_memory 节点：持久化本轮结果
    # 1. 完整对话原文写入会话日志
    # 2. 结构化事实、备注、摘要写入长期记忆
    def persist_memory(self, state: ChatState, config: RunnableConfig) -> ChatState:
        thread_id = config["configurable"]["thread_id"]
        user_text = ""
        assistant_text = ""
        # 从后往前遍历消息，找到最后一轮对话
        for message in reversed(state["messages"]):
            if not assistant_text and isinstance(message, AIMessage) and not message.tool_calls:
                assistant_text = _message_text(message)
            if not user_text and isinstance(message, HumanMessage):
                user_text = _message_text(message)
            if user_text and assistant_text:
                break
        # 先保存完整会话日志，再更新长期记忆
        if user_text and assistant_text:
            session = self.session_store.append_turn(thread_id, user_text, assistant_text)
            recent_user_topics = [
                item["content"]
                for item in session.get("history", [])
                if item.get("role") == "user"
            ][-4:]
            record = self.memory_store.update(
                thread_id,
                user_text,
                assistant_text,
                recent_user_topics=recent_user_topics,
            )
            return {
                "user_profile": record.get("facts", {}),
                "memory_summary": record.get("summary", ""),
            }
        return {}

    # ============ 本地规则引擎（Fallback 模式） ============
    # 当没有配置 OpenAI API Key 时使用
    # 通过规则匹配关键词来触发工具调用，模拟 Agent 行为

    def local_assistant(self, state: ChatState, config: dict[str, Any]) -> AIMessage:
        last_message = state["messages"][-1]

        # 如果上一条消息是 ToolMessage，说明工具已执行完成
        # 整理工具结果并返回给用户
        if isinstance(last_message, ToolMessage):
            tool_messages = [msg for msg in state["messages"] if isinstance(msg, ToolMessage)][-3:]
            tool_text = "\n".join(_message_text(msg) for msg in tool_messages if _message_text(msg))
            return AIMessage(
                content=(
                    "我已经根据工具结果整理好了：\n"
                    f"{tool_text}\n\n"
                    "如果你愿意，我还可以继续帮你追问细节，或者把这些信息整理成行动建议。"
                )
            )

        # 如果不是人类消息，返回准备就绪提示
        if not isinstance(last_message, HumanMessage):
            return AIMessage(content="我准备好了，你可以继续和我聊。")

        text = _message_text(last_message)

        # 关键词匹配：天气查询
        if any(keyword in text for keyword in ["天气", "气温", "下雨"]):
            city = self._guess_city(text, state)
            return AIMessage(
                content="我先帮你查一下天气。",
                tool_calls=[
                    {
                        "id": f"tool_weather_{uuid.uuid4().hex[:6]}",
                        "name": "get_weather",
                        "args": {"city": city},
                    }
                ],
            )

        # 关键词匹配：网络搜索
        if any(keyword in text for keyword in ["搜索", "查一下", "新闻", "最新", "网上"]):
            query = text.replace("帮我", "").replace("查一下", "").strip()
            return AIMessage(
                content="我先去查一下公开网络信息。",
                tool_calls=[
                    {
                        "id": f"tool_web_{uuid.uuid4().hex[:6]}",
                        "name": "web_search",
                        "args": {"query": query},
                    }
                ],
            )

        # 关键词匹配：日历/日程
        if any(keyword in text for keyword in ["日程", "日历", "会议", "提醒"]):
            # 尝试解析创建日程的文本（格式：xxx 从 2024-01-15 10:00 到 2024-01-15 11:00）
            create_match = re.search(
                r"(.+?)从(\d{4}-\d{2}-\d{2} \d{2}:\d{2})到(\d{4}-\d{2}-\d{2} \d{2}:\d{2})",
                text,
            )
            if create_match:
                title = create_match.group(1).replace("帮我创建", "").replace("创建", "").strip()
                start_time = create_match.group(2).replace(" ", "T")
                end_time = create_match.group(3).replace(" ", "T")
                return AIMessage(
                    content="我先把这个日程记录下来。",
                    tool_calls=[
                        {
                            "id": f"tool_calendar_add_{uuid.uuid4().hex[:6]}",
                            "name": "calendar_add_event",
                            "args": {
                                "title": title or "新日程",
                                "start_time": start_time,
                                "end_time": end_time,
                                "note": "local fallback mode",
                            },
                        }
                    ],
                )
            # 尝试解析查询日程的日期
            day_match = re.search(r"(\d{4}-\d{2}-\d{2}|今天|明天)", text)
            day = ""
            if day_match:
                day = day_match.group(1)
                if day == "今天":
                    day = datetime.now().strftime("%Y-%m-%d")
                elif day == "明天":
                    tomorrow = datetime.now() + timedelta(days=1)
                    day = tomorrow.strftime("%Y-%m-%d")
            return AIMessage(
                content="我先看一下你的日程。",
                tool_calls=[
                    {
                        "id": f"tool_calendar_list_{uuid.uuid4().hex[:6]}",
                        "name": "calendar_list_events",
                        "args": {"day": day},
                    }
                ],
            )

        # 默认回复：展示记忆功能和提示用户可以使用的功能
        profile = state.get("user_profile", {})
        summary = state.get("memory_summary", "")
        remember_hint = ""
        if "记住" in text:
            remember_hint = "我会把这件事记下来，下一轮还能接着聊。"
        return AIMessage(
            content=(
                "这是本地教学模式下的回复，我没有连接真实大模型，但会继续展示记忆和工具调度结构。\n"
                f"{remember_hint}\n"
                f"当前记住的用户信息：{json.dumps(profile, ensure_ascii=False)}\n"
                f"最近话题：{summary or '暂无'}\n"
                f"你刚才说的是：{text}\n"
                "你可以继续让我查天气、搜网络信息，或者创建和查看日程。"
            ).strip()
        )

    # 从文本中提取城市名（用于天气查询）
    # 优先从文本中查找"XX的天气"格式，否则使用用户画像中的城市
    def _guess_city(self, text: str, state: ChatState) -> str:
        match = re.search(r"([\u4e00-\u9fa5A-Za-z]{2,20})的天气", text)
        if match:
            return match.group(1)
        profile = state.get("user_profile", {})
        return str(profile.get("city") or "上海")  # 默认上海

    # ============ 对外 API ============

    # 处理用户消息的主要入口
    # 1. 构建配置（包含 thread_id）
    # 2. 调用 LangGraph 图处理消息
    # 3. 提取 AI 回复内容
    # 4. 返回完整结果（包括记忆、消息历史等）
    def invoke(self, thread_id: str, message: str) -> dict[str, Any]:
        config = {"configurable": {"thread_id": thread_id}}
        result = self.graph.invoke({"messages": [HumanMessage(content=message)]}, config=config)

        # 提取 AI 回复（排除工具调用消息）
        reply = ""
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and not msg.tool_calls:
                reply = _message_text(msg)
                break

        # 找到最后一轮人类消息的索引（用于返回当前轮次消息）
        last_human_index = 0
        for index in range(len(result["messages"]) - 1, -1, -1):
            if isinstance(result["messages"][index], HumanMessage):
                last_human_index = index
                break

        # 加载当前记忆状态
        memory = self.memory_store.load(thread_id)

        return {
            "thread_id": thread_id,
            "reply": reply,
            "mode": "llm" if self.llm is not None else "fallback",  # 显示当前模式
            "memory": memory,
            "messages": self.serialize_messages(result["messages"]),
            "turn_messages": self.serialize_messages(result["messages"][last_human_index:]),
        }

    # 获取指定会话的记忆历史
    def history(self, thread_id: str) -> dict[str, Any]:
        memory = self.memory_store.load(thread_id)
        session = self.session_store.load(thread_id)
        return {
            "thread_id": thread_id,
            "facts": memory.get("facts", {}),
            "notes": memory.get("notes", []),
            "summary": memory.get("summary", ""),
            "updated_at": memory.get("updated_at", ""),
            "session_history": session.get("history", []),
        }

    # 将 LangChain 消息对象序列化为可 JSON 序列化的字典列表
    # 用于 API 响应返回给前端
    def serialize_messages(self, messages: list[BaseMessage]) -> list[dict[str, str]]:
        visible: list[dict[str, str]] = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                visible.append({"role": "user", "content": _message_text(msg)})
            elif isinstance(msg, AIMessage) and not msg.tool_calls:
                visible.append({"role": "assistant", "content": _message_text(msg)})
            elif isinstance(msg, ToolMessage):
                visible.append({"role": "tool", "content": _message_text(msg)})
        return visible


# ============ FastAPI Web 应用 ============

# 创建全局 Agent 实例（单例）
agent = LangGraphChatAgent()

# 创建 FastAPI 应用
app = FastAPI(title="LangGraph Chat Agent Demo")

# 挂载静态文件目录（用于服务 HTML 前端）
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ============ API 路由 ============

# 主页：返回 HTML 前端页面
@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# 聊天接口：POST /api/chat
# 接收用户消息，返回 Agent 回复
# 请求体：{"thread_id": "可选", "message": "必填"}
# 响应：包含回复内容、记忆状态、消息历史等
@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    # 如果没有提供 thread_id，则生成一个随机的 8 位 ID
    thread_id = request.thread_id or str(uuid.uuid4())[:8]
    return agent.invoke(thread_id=thread_id, message=message)


# 历史记录接口：GET /api/history/{thread_id}
# 获取指定会话的记忆和对话历史
@app.get("/api/history/{thread_id}")
def history(thread_id: str) -> dict[str, Any]:
    return agent.history(thread_id)


# ============ 启动入口 ============
if __name__ == "__main__":
    import uvicorn

    # 启动 uvicorn 服务器
    # 访问地址：http://127.0.0.1:8000
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
