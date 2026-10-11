"""
common.py —— 所有示例脚本共享的模型初始化。

**只依赖本项目目录下的 `.env`**（不再去复用别的项目的 .env）。两种配置格式二选一，
get_model() 会自动识别：

  方式一（Gemini 秘钥 / Google）
    · AI Studio（个人学习首选，有免费额度）：
        GOOGLE_GENAI_USE_VERTEXAI=FALSE
        GOOGLE_API_KEY=<你的 AI Studio Key>     # https://aistudio.google.com/apikey
    · Vertex AI（企业 / GCP）：
        GOOGLE_GENAI_USE_VERTEXAI=TRUE
        GOOGLE_CLOUD_PROJECT=<project>
        GOOGLE_CLOUD_LOCATION=global
        GOOGLE_APPLICATION_CREDENTIALS=<service-account.json 路径>

  方式二（api_key 方式 / OpenAI 兼容端点）
        OPENAI_API_KEY=<key>
        OPENAI_BASE_URL=<可选，代理/厂内网关地址>

  可选（两种方式通用）
        MODEL=<模型名>        # 不填则按识别到的 provider 用各自默认模型
        PROVIDER=openai|gemini|vertex  # 同时配了多种凭据、想强制某一家时用
        HTTPS_PROXY / HTTP_PROXY  # httpx 自动读取，走代理时填（见下方小写镜像说明）

识别优先级：显式 PROVIDER > 按已配凭据自动识别（Vertex > Gemini 秘钥 > OpenAI）。

关键点：LangChain 的「标准模型接口」意味着——换模型/换厂商，业务代码几乎不动，
各脚本都只调用 get_model()，由本模块决定底层接哪家。
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.callbacks import BaseCallbackHandler

# 只加载**本项目目录下**的 .env（无论你从哪个目录运行脚本都稳定）。
_HERE = Path(__file__).resolve().parent
load_dotenv(_HERE / ".env")

# 代理变量大小写镜像（走 Vertex AI 时很关键）：
#   httpx（google-genai / OpenAI 兼容端点）读 HTTPS_PROXY/HTTP_PROXY（大写即可）；
#   但 langchain-google-vertexai 底层走 gRPC，其 C-core 只认 **小写** grpc_proxy / https_proxy。
#   所以这里把你在 .env 里配的大写镜像成小写，避免 Vertex 绕过代理、卡 60s 再超时。
for _upper, _lowers in (("HTTPS_PROXY", ("https_proxy", "grpc_proxy")), ("HTTP_PROXY", ("http_proxy",))):
    if _val := os.getenv(_upper):
        for _lower in _lowers:
            os.environ.setdefault(_lower, _val)

# 每种 provider 的缺省模型名（未显式设置 MODEL 时使用）
_DEFAULT_MODELS = {
    "google_vertexai": "gemini-2.5-flash",
    "google_genai": "gemini-2.5-flash",
    "openai": "gpt-4o-mini",
}


def _detect_provider() -> str | None:
    """识别该用哪种接入方式：显式 PROVIDER 优先，否则按已配凭据自动判断；都没配返回 None。"""
    forced = (os.getenv("PROVIDER") or "").strip().lower()
    if forced:
        return {
            "openai": "openai",
            "gemini": "google_genai", "google": "google_genai", "google_genai": "google_genai",
            "vertex": "google_vertexai", "vertexai": "google_vertexai",
            "google_vertexai": "google_vertexai",
        }.get(forced, forced)
    if os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE":
        return "google_vertexai"          # Vertex AI：走 ADC / 服务账号密钥
    if os.getenv("GOOGLE_API_KEY"):
        return "google_genai"             # AI Studio：Gemini 秘钥
    if os.getenv("OPENAI_API_KEY"):
        return "openai"                   # OpenAI 兼容端点
    return None


def has_credentials() -> bool:
    """是否至少配好了一种可用凭据。"""
    return _detect_provider() is not None


def _resolve_model(model: str | None, provider: str) -> str:
    """把模型名补全成 provider:model 形式。优先级：显式入参 > MODEL > provider 默认。"""
    model = model or os.getenv("MODEL")
    if not model:
        return f"{provider}:{_DEFAULT_MODELS[provider]}"
    # 用户已写成 "provider:model" 就原样尊重；否则按识别到的 provider 补前缀。
    return model if ":" in model else f"{provider}:{model}"


class _OneLineLLMLogger(BaseCallbackHandler):
    """把每次「访问模型」打成一行日志：完整入参 + 完整返回 + 耗时。

    用 LangChain 的回调钩子实现，所以 invoke / stream / batch / 乃至 Agent 内部的每一次
    模型调用都会被打到——业务脚本一行都不用改。按 run_id 配对 start/end，既能正确计时，
    并发（batch）时也不会串台。默认开启，设环境变量 `LLM_LOG=0` 可关闭。
    """

    def __init__(self) -> None:
        self._pending: dict = {}  # run_id -> (起始计时, 已渲染入参)

    def on_chat_model_start(self, serialized, messages, *, run_id, **kw) -> None:
        self._pending[run_id] = (time.perf_counter(), self._render_input(messages, kw))

    def on_llm_end(self, response, *, run_id, **kw) -> None:
        self._flush(run_id, "返回", self._render_output(response))

    def on_llm_error(self, error, *, run_id, **kw) -> None:
        self._flush(run_id, "错误", f"{type(error).__name__}: {error}")

    def _flush(self, run_id, label: str, body: str) -> None:
        t0, rin = self._pending.pop(run_id, (time.perf_counter(), "null"))
        print(f"[llm] 入参={rin} | {label}={body} | 耗时={time.perf_counter() - t0:.2f}s")

    # ---- 渲染：把 LangChain 的对象压成可读 JSON（一行）----
    @staticmethod
    def _msg(m) -> dict:
        d = {"role": getattr(m, "type", "?"), "content": m.content}
        if getattr(m, "tool_calls", None):
            d["tool_calls"] = m.tool_calls          # AIMessage 要调的工具
        if getattr(m, "tool_call_id", None):
            d["tool_call_id"] = m.tool_call_id       # ToolMessage 回填对应哪个调用
        return d

    def _render_input(self, messages, kw) -> str:
        params = dict(kw.get("invocation_params") or {})
        tool_names = []
        for t in params.get("tools") or []:          # 工具 schema 是静态样板，只记名字免得刷屏
            fn = t.get("function") if isinstance(t, dict) else None
            tool_names.append((fn or t or {}).get("name") if isinstance(t, dict) else str(t)[:40])
        payload = {
            "model": params.get("model_name") or params.get("model"),
            "params": {k: v for k, v in params.items()
                       if k in ("temperature", "top_p", "max_tokens", "tool_choice") and v not in (None, [])},
            "tools": tool_names or None,
            "messages": [self._msg(m) for batch in messages for m in batch],
        }
        return json.dumps({k: v for k, v in payload.items() if v not in (None, {}, [])},
                          ensure_ascii=False, default=str)

    def _render_output(self, response) -> str:
        gens = []
        for batch in response.generations:
            for g in batch:
                item: dict = {"text": g.text}
                msg = getattr(g, "message", None)
                if msg is not None and getattr(msg, "tool_calls", None):
                    item["tool_calls"] = msg.tool_calls
                info = getattr(g, "generation_info", None) or {}
                if info.get("finish_reason"):
                    item["finish_reason"] = info["finish_reason"]
                gens.append(item)
        payload = {"generations": gens}
        llm_out = response.llm_output or {}
        if llm_out.get("model_name"):
            payload["model"] = llm_out["model_name"]
        if llm_out.get("token_usage"):
            payload["usage"] = llm_out["token_usage"]
        return json.dumps(payload, ensure_ascii=False, default=str)


_LLM_LOGGER = _OneLineLLMLogger()


def get_model(model: str | None = None, **kwargs):
    """返回一个配置好的 chat model（自动适配两种 .env 格式）。

    Args:
        model: 可选，provider:model 形式的模型名；为空时按 .env 识别。
        **kwargs: 透传给 init_chat_model 的其他参数（如 temperature）。
    """
    provider = _detect_provider() or "openai"  # 没凭据时也给个默认，具体由 require_key 拦截
    full_model = _resolve_model(model, provider)

    init_kwargs = dict(kwargs)
    if full_model.startswith("openai:"):
        # OpenAI 兼容端点需要显式传 base_url / api_key；
        # google_genai 自动读 GOOGLE_API_KEY，google_vertexai 自动走 ADC，无需在此传。
        if base_url := (os.getenv("OPENAI_BASE_URL") or None):
            init_kwargs["base_url"] = base_url
        if api_key := os.getenv("OPENAI_API_KEY"):
            init_kwargs["api_key"] = api_key

    # 一行日志：完整入参 + 完整返回 + 耗时（默认开，LLM_LOG=0 关）。挂在模型上，
    # 于是 invoke/stream/batch/Agent 内部每次模型调用都会被打到。
    if os.getenv("LLM_LOG", "1") != "0":
        init_kwargs["callbacks"] = list(init_kwargs.get("callbacks") or []) + [_LLM_LOGGER]

    return init_chat_model(full_model, **init_kwargs)


def require_key() -> bool:
    """脚本入口处的友好提示：两种格式都没配时给出明确说明，而不是抛一堆栈。"""
    if has_credentials():
        return True
    print("⚠️  未检测到可用凭据。请在本目录建一个 .env，二选一配置：")
    print("   方式一（Gemini 秘钥）：GOOGLE_GENAI_USE_VERTEXAI=FALSE + GOOGLE_API_KEY=...")
    print("   方式二（api_key）    ：OPENAI_API_KEY=... (+ 可选 OPENAI_BASE_URL)")
    print("   详见本项目 README「环境与运行」。")
    return False
