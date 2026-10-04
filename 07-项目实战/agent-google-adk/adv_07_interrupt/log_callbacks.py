"""给 LLM 调用打日志：把【入参提示词 + 返回值完整内容】打成一行输出，并带耗时。

用 ADK 的「模型回调」实现，好处是**真实 Gemini 和离线 mock 都适用**
（回调在 `generate_content_async` 前后触发，与具体模型无关）：

    before_model_callback(ctx, llm_request)   # 调用前：记开始时间 + 渲染入参（发给模型的 prompt）暂存
    after_model_callback(ctx, llm_response)   # 调用后：把【入参 + 返回值】拼成一行输出，并带上耗时

输出形如（单行）：
    [LLM 入参/返回值] 耗时=602ms  system: … contents[3]: … 工具: [...] / text='…结论…'

计时说明：同一个 invocation 里若有多轮「模型→工具→模型」，每一轮都会各自计时
（before 每轮都会重置开始时间）。流式(SSE)下只在最终（非 partial）那条上打印，避免刷屏。

开关：环境变量 INTERRUPT_DEMO_LOG_LLM=0 可关闭（默认开）。
"""

from __future__ import annotations

import logging
import os
import socket
import time
from typing import Any, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger("adv_07_interrupt.llm")

_ENABLED = os.environ.get("INTERRUPT_DEMO_LOG_LLM", "1") != "0"
# 每个 invocation 的开始时间（before 写入，after 读取）。模型调用在单次 invocation 内是
# 严格顺序的（before→after→before→after），所以用 invocation_id 做键不会错配。
_START: dict[str, float] = {}
# 入参渲染结果暂存（before 写入，after 读取后与返回值一起打成一行）。
_INPUT: dict[str, str] = {}
# 代理信息只在第一次真实调用时打印一次，避免每轮刷屏。
_PROXY_LOGGED = False


def _short(s: Any, limit: Optional[int] = 500) -> str:
    s = str(s)
    if limit is None or len(s) <= limit:  # limit=None 表示不截断（打印完整内容）
        return s
    return s[:limit] + f"…(+{len(s) - limit}字)"


def _render_parts(parts: Optional[list], limit: Optional[int] = 500) -> str:
    """把一条消息的 parts 渲染成紧凑可读的一行。limit=None 则不截断（完整内容）。"""
    bits = []
    for p in parts or []:
        if getattr(p, "text", None):
            bits.append(f"text={_short(p.text, limit)!r}")
        fc = getattr(p, "function_call", None)
        if fc is not None:
            bits.append(f"call={fc.name}({dict(fc.args or {})})")
        fr = getattr(p, "function_response", None)
        if fr is not None:
            bits.append(f"resp={getattr(fr, 'name', '?')}->{_short(getattr(fr, 'response', None), limit)}")
    return " | ".join(bits) or "(空)"


def _render_system(sysi: Any) -> str:
    if sysi is None:
        return ""
    parts = getattr(sysi, "parts", None)
    if parts is not None:
        return _render_parts(parts)
    return _short(sysi)


def _effective_proxy(host: str = "googleapis.com") -> Optional[str]:
    """按 httpx/requests 的规则，解析对该 host 实际会使用的代理（简化版）。

    httpx / aiohttp / requests 默认 trust_env=True，会自动读取下面这些环境变量。
    """
    no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    for entry in (e.strip() for e in no_proxy.split(",")):
        if entry and host.endswith(entry.lstrip("*.")):
            return None  # 命中 NO_PROXY -> 直连
    return (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("ALL_PROXY")
        or os.environ.get("all_proxy")
    )


def _proxy_reachable(proxy_url: str, timeout: float = 1.0) -> bool:
    """TCP 连一下代理端口，判断代理是否真的起着。"""
    u = urlparse(proxy_url)
    if not u.hostname:
        return False
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        sock.connect((u.hostname, u.port or 80))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def network_status_lines(use_mock: bool, model: str) -> List[str]:
    """给启动日志用：汇总「走不走代理」。"""
    if use_mock:
        return ["[网络] mock 模式：不发起任何外部网络请求（无需代理）"]
    proxy = _effective_proxy()
    lines = [f"[网络] real 模式（model={model}）"]
    hp, hps, nop = (
        os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"),
        os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
        os.environ.get("NO_PROXY") or os.environ.get("no_proxy"),
    )
    lines.append(f"  HTTP_PROXY={hp!r}  HTTPS_PROXY={hps!r}  NO_PROXY={nop!r}")
    if proxy:
        ok = _proxy_reachable(proxy)
        lines.append(f"  → 模型调用与鉴权将【走代理】{proxy}（可达性：{'可连接 ✓' if ok else '连不上 ✗，请确认代理已启动'}）")
        lines.append("  （httpx/aiohttp/requests 默认 trust_env=True，会自动使用上面的代理环境变量）")
    else:
        lines.append("  → 未配置代理，模型调用将【直连】。若需走代理，请在 .env 里设 HTTPS_PROXY=http://127.0.0.1:7890")
    return lines


def before_model(callback_context, llm_request):
    """模型调用前：记开始时间 + 渲染本次入参（提示词）暂存，等 after 和返回值一起打成一行。"""
    if not _ENABLED:
        return None
    _START[callback_context.invocation_id] = time.perf_counter()

    # 渲染入参，先暂存；真正输出在 after_model（入参/返回值同一行）。
    segs = []
    cfg = getattr(llm_request, "config", None)
    sysi = _render_system(getattr(cfg, "system_instruction", None)) if cfg else ""
    if sysi:
        segs.append(f"system: {sysi}")
    contents = list(getattr(llm_request, "contents", None) or [])
    conv = " ; ".join(
        f"{getattr(c, 'role', '?')}:{_render_parts(getattr(c, 'parts', None))}" for c in contents
    )
    segs.append(f"contents[{len(contents)}]: {conv or '(空)'}")
    tools = list((getattr(llm_request, "tools_dict", None) or {}).keys())
    if tools:
        segs.append(f"工具: {tools}")
    _INPUT[callback_context.invocation_id] = "  ".join(segs)

    # 第一次真实调用时，顺带打印「这次到底走不走代理」，和 LLM 日志挨在一起。
    global _PROXY_LOGGED
    if not _PROXY_LOGGED:
        _PROXY_LOGGED = True
        model_name = str(getattr(llm_request, "model", "") or "")
        if "mock" in model_name.lower():
            logger.info("[网络] mock 模式：本次调用不走网络，无代理")
        else:
            proxy = _effective_proxy()
            if proxy:
                ok = _proxy_reachable(proxy)
                logger.info(f"[网络] 本次模型调用【走代理】{proxy}（{'可连接 ✓' if ok else '连不上 ✗'}）")
            else:
                logger.info("[网络] 本次模型调用【直连】（未配置 HTTPS_PROXY）")
    return None  # 返回 None = 不改写请求，正常继续


def after_model(callback_context, llm_response):
    """模型调用后：把【入参 + 返回值完整内容】打成一行输出（含耗时）。"""
    if not _ENABLED:
        return None
    # 流式(SSE)中间块跳过，只在最终那条打印，避免刷屏。
    if getattr(llm_response, "partial", None):
        return None
    inv = callback_context.invocation_id
    t0 = _START.pop(inv, None)
    elapsed_ms = (time.perf_counter() - t0) * 1000 if t0 else -1.0
    prompt_in = _INPUT.pop(inv, "(无入参)")

    content = getattr(llm_response, "content", None)
    # 返回值打印【完整内容】（limit=None 不截断）。
    rendered = _render_parts(getattr(content, "parts", None), limit=None) if content else "(无内容)"
    err = getattr(llm_response, "error_message", None)
    if err:
        rendered = f"{rendered}  error={err}"
    line = f"[LLM] 耗时={elapsed_ms:.0f}ms  【入参】{prompt_in} 【返回值】{rendered}"
    logger.info(line.replace("\n", " "))  # 折叠换行，保证整条日志就一行
    return None
