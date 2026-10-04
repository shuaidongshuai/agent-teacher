"""自研 WebSocket 服务器：把「中断总线 + 安全检查点」架到 ADK 的 Runner 之上。

为什么要自己写服务器，而不是用 `adk web`？
    `adk web` 的标准 UI 是**回合制**的：发一句、等一句回完，没法在「流式输出中途」
    再插一句话。而本关卡要演示的正是「任务进行中，用户再发话打断/纠正」。
    所以这里用 WebSocket 做**双向、全双工**通道：浏览器可以在 Agent 正忙时继续发消息。

核心机制（和纯手写版一脉相承，只是执行引擎换成了 ADK Runner）：
    1. 一个协程持续从 WebSocket 读用户输入，丢进 inbox（永不阻塞执行）。
    2. 执行协程消费 ADK 的事件流（runner.run_async），同时并发监听 inbox。
    3. 收到新输入时，**不立刻硬切**，而是等到「安全边界」：
       当前没有悬空的函数调用（function_call 都已拿到 function_response）。
       —— 这就保证了会话历史里绝不会留下「没有配对结果的函数调用」。
    4. 到达安全边界后，中止当前 turn，用新输入开启下一个 turn（ADK 会带着
       已有的会话历史重新规划）。
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .agent import MODEL, USE_MOCK, root_agent

APP_NAME = "adv_07_interrupt"
WEB_DIR = Path(__file__).parent / "web"

app = FastAPI(title="可打断聊天 Agent（ADK）")
session_service = InMemorySessionService()
runner = Runner(app_name=APP_NAME, agent=root_agent, session_service=session_service)


def _short(obj, limit: int = 400) -> str:
    s = str(obj)
    return s if len(s) <= limit else s[:limit] + "…"


def event_to_ui(ev) -> list[dict]:
    """把一个 ADK Event 翻译成若干条「界面消息」。"""
    out: list[dict] = []
    is_partial = bool(getattr(ev, "partial", False))
    if ev.content and ev.content.parts:
        for p in ev.content.parts:
            if getattr(p, "text", None):
                out.append({"type": "assistant", "text": p.text, "partial": is_partial})
    # 关键：SSE 流式下，同一个函数调用会同时出现在 partial 事件和最终(非 partial)事件里
    # （ADK 也只在非 partial 事件上真正执行工具）。只渲染非 partial 的那次，
    # 否则页面会把「调用 web_search(...)」打印两遍。
    if not is_partial:
        for fc in ev.get_function_calls():
            out.append({"type": "tool_call", "name": fc.name, "args": dict(fc.args or {})})
        for fr in ev.get_function_responses():
            out.append({"type": "tool_result", "name": fr.name, "content": _short(fr.response)})
    return out


@app.get("/")
async def index() -> HTMLResponse:
    return HTMLResponse((WEB_DIR / "index.html").read_text(encoding="utf-8"))


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    await Driver(ws).start()


# 连接断开时放进 inbox 的「关闭哨兵」：让 _drive / _run_single_turn 能优雅收尾退出，
# 而不是靠取消任务（取消会在某些客户端上冒出 CancelledError，也更难清理干净）。
_CLOSE = object()


class Driver:
    """每个 WebSocket 连接一个 Driver，持有自己独立的 ADK 会话。"""

    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.user_id = "web"
        self.session_id = uuid.uuid4().hex
        self.inbox: asyncio.Queue = asyncio.Queue()
        self._closing = False  # 连接已断开，正在收尾
        # SSE 流式：真实模型下可逐 token 产出 partial 事件；mock 下是整条产出。
        self.run_cfg = RunConfig(streaming_mode=StreamingMode.SSE, max_llm_calls=20)

    async def _send(self, obj: dict) -> None:
        try:
            await self.ws.send_json(obj)
        except Exception:  # noqa: BLE001  连接已断，忽略
            pass

    async def start(self) -> None:
        await session_service.create_session(
            app_name=APP_NAME, user_id=self.user_id, session_id=self.session_id
        )
        reader = asyncio.create_task(self._read_ws())
        try:
            # _drive 会在 reader 投递 _CLOSE 哨兵后优雅返回（无需取消任务）。
            await self._drive()
        finally:
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)

    async def _read_ws(self) -> None:
        """持续读浏览器消息 -> inbox。这一步让「读输入」永不卡住执行循环。"""
        try:
            while True:
                data = await self.ws.receive_json()
                text = (data.get("text") or "").strip()
                if text:
                    await self.inbox.put(text)
        except Exception:  # noqa: BLE001  断开/格式错误 -> 结束读取
            pass
        finally:
            # 唤醒可能正卡在 inbox.get() 的 _drive / _run_single_turn，让它们收尾退出。
            self._closing = True
            await self.inbox.put(_CLOSE)

    async def _drive(self) -> None:
        """主循环（整条连接里 inbox 的唯一「空闲」消费者）：
        等一句用户输入 -> 跑一个（可能被多次纠正的）任务链。
        单个任务出错不拖垮整条连接；连接断开则优雅退出。"""
        while not self._closing:
            try:
                first = await self.inbox.get()
                if first is _CLOSE:
                    return
                await self._send({"type": "user_echo", "text": first})
                await self._run_chain(first)
            except Exception as exc:  # noqa: BLE001
                await self._send({"type": "error", "text": f"内部错误：{exc!r}"})
                await self._send({"type": "status", "text": "idle"})

    async def _run_chain(self, text: str) -> None:
        """一个「任务」可能因为被纠正而重开多轮；每次用新文本重开一个 ADK turn。"""
        current: str | None = text
        while current is not None and not self._closing:
            await self._send({"type": "status", "text": "working"})
            current = await self._run_single_turn(current)
        await self._send({"type": "status", "text": "idle"})

    async def _run_single_turn(self, text: str) -> str | None:
        """跑一个 ADK turn，并在安全边界响应打断。

        返回值：None 表示本 turn 自然结束；返回文本表示要用它重开下一个 turn
        （可能是「执行途中打断」的纠正，也可能是刚好在收尾瞬间到达的下一条输入）。

        并发要点（修复「发送后偶发不生效」的根因）：
            整条连接里 inbox 始终只有「一个」读取任务；本函数退出时会把它
            干净地取消 / 回收，绝不泄漏一个悬空的 inbox.get() 把下一条消息吃掉。
        """
        content = types.Content(role="user", parts=[types.Part(text=text)])
        # runner.run_async：ADK 的核心入口，驱动 Agent 跑完这一轮（one turn）。它会：
        #   1) 按 user_id + session_id 找到会话（历史、state 都在里面），把 new_message 追加进去；
        #   2) 驱动 Agent：请求模型 → 模型要调工具就执行工具 → 工具结果回填给模型 → 可能再调……
        #      直到给出最终回复（多智能体还会处理 transfer_to_agent 委派）；
        #   3) 返回一个【异步生成器】：每产出一步就 yield 一个 Event（一段文本 / 一个 function_call /
        #      一个 function_response），并把这些事件写回会话历史。
        # 所以下面是 `async for ev in agen` 边产边收，而不是等它整轮跑完才拿到结果。
        # 本关的「打断」正建立在这个粒度上：到安全边界就 aclose() 掉这个生成器、用新输入另开一个
        # run_async；会话历史仍在 session 里，ADK 会带着上文重新规划。
        agen = runner.run_async(
            user_id=self.user_id, session_id=self.session_id,
            new_message=content, run_config=self.run_cfg,
        )

        # feed_events：把 ADK 事件流搬进内存队列（内存队列，取消无副作用）。
        merged: asyncio.Queue = asyncio.Queue()

        async def feed_events() -> None:
            try:
                async for ev in agen:
                    await merged.put(("event", ev))
            except Exception as exc:  # noqa: BLE001
                await merged.put(("error", repr(exc)))
            finally:
                await merged.put(("done", None))

        ev_task = asyncio.create_task(feed_events())
        get_event = asyncio.create_task(merged.get())        # 读 ADK 事件
        get_input = asyncio.create_task(self.inbox.get())    # 读用户新输入（唯一 inbox 读取）

        outstanding = 0          # 未配对的函数调用数：call +1，response -1
        pending: list[str] = []  # 已收到、待在安全边界生效的新输入
        try:
            while True:
                done, _ = await asyncio.wait(
                    {get_event, get_input}, return_when=asyncio.FIRST_COMPLETED
                )
                # 1) 用户在执行途中又发了一句话（已从 inbox 取出，必被处理，不会丢）
                if get_input in done:
                    txt = get_input.result()
                    if txt is _CLOSE:  # 连接断开 -> 收尾退出本 turn
                        self._closing = True
                        break
                    await self._send({"type": "user_echo", "text": txt})
                    hint = "将在当前工具完成后生效" if outstanding > 0 else "立即生效"
                    await self._send({"type": "interrupt", "text": f"收到新输入（{hint}）"})
                    pending.append(txt)
                    get_input = asyncio.create_task(self.inbox.get())  # 继续监听后续输入
                # 2) ADK 事件
                if get_event in done:
                    kind, payload = get_event.result()
                    if kind == "event":
                        for ui in event_to_ui(payload):
                            await self._send(ui)
                        # 只统计非 partial 事件里的函数调用/结果：SSE 下函数调用会在
                        # partial + 最终事件里各出现一次，若都计数，outstanding 永远回不到 0，
                        # 安全边界打断就会失效。
                        if not getattr(payload, "partial", False):
                            outstanding += len(payload.get_function_calls())
                            outstanding -= len(payload.get_function_responses())
                        get_event = asyncio.create_task(merged.get())
                    elif kind == "error":
                        await self._send({"type": "error", "text": payload})
                        break
                    else:  # done：本 turn 事件流结束
                        break
                # 安全边界：有待处理输入 且 没有悬空的函数调用 -> 去重规划。
                if pending and outstanding <= 0:
                    break
        finally:
            # 收尾 ADK 侧
            ev_task.cancel()
            await asyncio.gather(ev_task, return_exceptions=True)
            try:
                await agen.aclose()  # 没人再迭代它了，安全关闭，让 ADK 清理资源
            except Exception:  # noqa: BLE001
                pass
            if not get_event.done():
                get_event.cancel()
            # 关键：回收唯一的 inbox 读取任务，绝不泄漏，也绝不丢消息。
            if get_input.done() and not get_input.cancelled() and get_input.exception() is None:
                # 极少数：和 break 同时完成、循环没来得及处理的那条输入
                leftover = get_input.result()
                if leftover is _CLOSE:
                    self._closing = True
                else:
                    await self._send({"type": "user_echo", "text": leftover})
                    pending.append(leftover)
            elif not get_input.done():
                get_input.cancel()
                try:
                    late = await get_input  # 取消竞态里仍可能恰好拿到一条
                except asyncio.CancelledError:
                    late = None
                if late is _CLOSE:
                    self._closing = True
                elif late:
                    await self._send({"type": "user_echo", "text": late})
                    pending.append(late)

        # 有待处理输入就作为下一个 turn 的输入返回（打断纠正 / 排队的下一条），否则结束。
        return "\n".join(pending) if pending else None


def main() -> None:
    import logging
    import uvicorn

    # 配置日志：让 log_callbacks 里打印的「LLM 入参/返回/耗时」可见（带时间戳）。
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    mode = "mock（离线假模型）" if USE_MOCK else f"real（{MODEL}）"
    print(f"运行模式：{mode}")
    if not USE_MOCK:
        print("已检测到凭证，将调用真实模型（.env 来自本包或上一级 agent-google-adk 目录）")
    # 打印「走不走代理」
    from .log_callbacks import network_status_lines
    for line in network_status_lines(USE_MOCK, MODEL):
        print(line)
    print("打开浏览器访问 http://127.0.0.1:8000  （Ctrl+C 退出）")
    print("（LLM 入参/返回/耗时会打印在本控制台；设 INTERRUPT_DEMO_LOG_LLM=0 可关闭）")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
