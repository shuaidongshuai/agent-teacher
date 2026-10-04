"""进阶 07：可打断 / 可纠正的聊天 Agent（ADK 内核 + 自研网页）

学习目标：
  - 用 ADK 的 LlmAgent + 工具（function calling）搭一个会执行工具的聊天 Agent
  - 把「中断总线 + 安全检查点」的思路，架到 ADK 的 Runner 事件流之上，
    从而实现「任务进行中，用户再发一句话来纠正 / 修改 / 打断」
  - 理解 ADK 里打断的安全边界：绝不在「函数调用已发出、函数结果还没回来」时打断
    （否则会话里会留下一个没有配对结果的 function_call，下一轮直接报错）

与本目录其它关卡的区别：
  其它关卡用 `adk web` 的标准 UI（回合制），而本关卡自带一个 WebSocket 网页
  （server.py + web/index.html），能真正演示「流式输出中插话打断」。
  当然，本包同样是合法的 ADK Agent，`adk run adv_07_interrupt` 也能跑。

运行（推荐，自研网页，默认 mock 离线、无需任何 Key）：
    cd 07-项目实战/agent-google-adk
    python -m adv_07_interrupt.server
    # 浏览器打开 http://127.0.0.1:8000

接真实 Gemini：设环境变量 INTERRUPT_DEMO_MOCK=0，并按本目录「环境变量配置示例.txt」
配置 GOOGLE_API_KEY 或 Vertex AI。
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from google.adk.agents import Agent

from .log_callbacks import after_model, before_model
from .mock_llm import MockLlm

# ---------------------------------------------------------------------------
# 加载 .env：adk web/run 会自动加载，但 `python -m adv_07_interrupt.server` 不会，
# 所以这里显式加载。顺序：先本包目录，再上一级（agent-google-adk/.env）。
# load_dotenv 默认不覆盖已存在的环境变量，所以「更具体的」本包 .env 优先。
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv

    _HERE = Path(__file__).parent
    for _env in (_HERE / ".env", _HERE.parent / ".env"):
        if _env.exists():
            load_dotenv(_env)
except ImportError:
    pass


def _has_credentials() -> bool:
    """粗略判断是否配置了可用的模型凭证（与 run_demo.py 保持一致）。"""
    if os.environ.get("GOOGLE_API_KEY"):
        return True
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE":
        return True
    return False


# 真实模式用的模型名；mock 模式下用不到。
MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")

# 是否走离线 mock：
#   - 显式设 INTERRUPT_DEMO_MOCK=1/0 时以它为准；
#   - 没设时，自动判断：上一级 .env 里配了凭证就用真实模型，否则回退 mock。
_mock_flag = os.environ.get("INTERRUPT_DEMO_MOCK")
if _mock_flag is None:
    USE_MOCK = not _has_credentials()
else:
    USE_MOCK = _mock_flag == "1"

# 工具产生副作用时写到这个沙箱目录。
_SANDBOX = Path(__file__).parent / "sandbox"


# ---------------------------------------------------------------------------
# 工具：在 ADK 里，普通 Python 函数就是工具。
#   - 函数名      -> 工具名
#   - docstring   -> 工具描述（给模型看，决定何时调用）
#   - 类型注解    -> 参数 schema
#   - 返回 dict   -> 作为 function_response 回填给模型
# 这里故意让 web_search / transfer 比较慢，好留出「执行中打断」的窗口。
# ---------------------------------------------------------------------------

async def web_search(query: str) -> dict:
    """联网搜索资料并返回摘要。耗时较长，是演示打断的主要窗口。

    Args:
        query: 搜索关键词。
    """
    # 模拟分页抓取的网络耗时（真实场景是 http 请求）。
    await asyncio.sleep(2.0)
    results = [f"{query}-资料{i}" for i in range(1, 6)]
    return {"status": "ok", "query": query, "results": results}


def calculator(expression: str) -> dict:
    """计算一个算术表达式，例如 '2+3*4'。很快，往往来不及打断。

    Args:
        expression: 合法的算术表达式。
    """
    try:
        value = eval(expression, {"__builtins__": {}}, {})  # noqa: S307 仅演示
        return {"status": "ok", "expression": expression, "value": value}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": f"表达式非法：{exc}"}


async def write_note(filename: str, content: str) -> dict:
    """把内容写入笔记文件（会覆盖同名文件）。有副作用。

    Args:
        filename: 文件名，如 note.txt。
        content: 要写入的内容。
    """
    _SANDBOX.mkdir(parents=True, exist_ok=True)
    path = _SANDBOX / filename
    await asyncio.sleep(1.0)  # 模拟写入 + 同步耗时
    path.write_text(content, encoding="utf-8")
    return {"status": "ok", "path": str(path), "bytes": len(content.encode("utf-8"))}


async def transfer(to: str, amount: float) -> dict:
    """向某账户转账（真实业务不可逆，演示「不可中断」语义）。

    Args:
        to: 收款账户。
        amount: 金额。
    """
    # 这是不可逆关键区：一旦开始就不该被打断（见 server.py 的安全边界说明）。
    await asyncio.sleep(1.5)
    txn_id = f"TXN-{abs(hash((to, amount))) % 100000:05d}"
    return {"status": "ok", "to": to, "amount": amount, "txn_id": txn_id}


INSTRUCTION = (
    "你是一个可以调用工具的中文助手。工具有：web_search（搜索）、calculator（计算）、"
    "write_note（把内容写入文件）、transfer（转账）。\n"
    "【多步任务，务必多调几个工具】当用户让你「调研 / 研究 / 整理 / 写报告」某个主题时，"
    "不要只搜一次就结束，要分多步依次用多个工具完成：\n"
    "  1) 先用 web_search 搜集资料；\n"
    "  2) 再用 write_note 把要点写进一个文件（例如 report.txt）；\n"
    "  3) 如需统计/计算，用 calculator；\n"
    "  4) 以上工具都执行完后，最后再用一段话总结。\n"
    "务必【一次只调用一个工具】，拿到该工具结果后再决定下一步，不要一次并行调用多个——"
    "这样每一步之间都留有可被用户打断的机会。\n"
    "【可被打断】用户可能在你执行过程中再发一句话来纠正、修改、追加或叫停当前任务。"
    "遇到这种情况，请结合最新的用户意图重新规划，不要机械地按旧计划往下做。"
    "如果用户说「停 / 算了 / 取消」，就停下来并简短确认，不再调用工具。"
)

# ADK 约定的入口变量名；adk run / adk web / 本项目 server.py 都会找它。
root_agent = Agent(
    name="interrupt_demo",
    # model 既可以是模型名字符串（真实），也可以是一个 BaseLlm 实例（我们的离线 mock）。
    model=MockLlm() if USE_MOCK else MODEL,
    description="一个可被用户随时纠正/打断的工具型聊天 Agent。",
    instruction=INSTRUCTION,
    tools=[web_search, calculator, write_note, transfer],
    # 模型回调：打印每次 LLM 调用的入参提示词 / 返回值 / 耗时（真实 + mock 都生效）。
    before_model_callback=before_model,
    after_model_callback=after_model,
)
