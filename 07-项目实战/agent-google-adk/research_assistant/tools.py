"""capstone 用到的工具函数。

包含：
  - web_search：为了离线可跑，这里是【模拟】搜索。真实项目里换成
    ADK 内置 google_search 或你自己的检索接口即可。
  - save_report：把最终报告写到本地文件。
  - exit_loop：给评审循环用的"达标即停"信号。
"""

from datetime import datetime
from pathlib import Path

from google.adk.tools.tool_context import ToolContext

OUTPUT_DIR = Path(__file__).parent / "output"


def web_search(query: str) -> dict:
    """联网检索资料（本示例为模拟实现，返回与查询相关的要点）。

    Args:
        query: 检索关键词或问题。

    Returns:
        dict: status 与 results（若干条要点文本）。
    """
    # —— 模拟检索：真实项目请替换为 google_search 或自建检索 ——
    canned = [
        f"关于「{query}」的背景与定义概述。",
        f"「{query}」的主要方法/技术路线与代表方案。",
        f"「{query}」当前的挑战、局限与未来趋势。",
    ]
    return {
        "status": "success",
        "query": query,
        "note": "（这是模拟检索结果，仅供教学演示）",
        "results": canned,
    }


def save_report(title: str, content: str, tool_context: ToolContext) -> dict:
    """把最终报告保存为本地 Markdown 文件。

    Args:
        title: 报告标题（用于文件名）。
        content: 报告正文（Markdown）。
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip() or "report"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"{safe}_{stamp}.md"
    path.write_text(f"# {title}\n\n{content}\n", encoding="utf-8")
    # 顺便把路径写进 state，便于后续步骤/程序读取
    tool_context.state["report_path"] = str(path)
    return {"status": "success", "saved_to": str(path)}


def exit_loop(tool_context: ToolContext) -> dict:
    """当报告质量已达标、无需再修改时调用，用于结束评审循环。"""
    tool_context.actions.escalate = True
    return {"status": "approved", "message": "报告已达标。"}
