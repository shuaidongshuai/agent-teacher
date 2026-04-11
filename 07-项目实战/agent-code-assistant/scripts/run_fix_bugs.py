"""
自动修 Bug Demo

运行方式:
    python scripts/run_fix_bugs.py

说明:
    - 需要 OPENAI_API_KEY
    - 需要安装 langgraph
    - Agent 会自动读取代码、定位 bug、修复并验证
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import CodeAgentConfig
from app.graph import build_graph
from app.llm_client import LLMClient
from app.sandbox import Sandbox
from app.state import CodeAgentState


def main():
    print("=" * 60)
    print("       Code Agent — 自动修 Bug Demo")
    print("=" * 60)

    config = CodeAgentConfig(project_root=project_root)

    if not config.openai_api_key:
        print("\n错误: 请先设置 OPENAI_API_KEY")
        print("  export OPENAI_API_KEY=your-key")
        return

    # 初始化
    llm = LLMClient(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        model=config.openai_model,
    )

    sandbox = Sandbox(
        root_dir=config.sandbox_path,
        allowed_commands=config.allowed_commands,
        timeout=config.command_timeout,
        max_output_chars=config.max_output_chars,
    )

    graph = build_graph(llm, sandbox, config)

    # 定义任务
    task = (
        "请分析 calculator.py 中的所有 bug 并修复。"
        "已知 test_calculator.py 中有多个测试会失败。"
        "请先运行测试查看哪些失败，然后逐一修复，最终让所有测试通过。"
    )

    print(f"\n任务: {task}\n")
    print("Agent 开始工作...\n")

    # 运行
    initial_state: CodeAgentState = {
        "task_description": task,
        "llm_call_count": 0,
        "execution_log": [],
    }

    result = graph.invoke(initial_state)

    # 输出结果
    print("\n" + "=" * 60)
    print("                执行结果")
    print("=" * 60)

    # 推理轨迹
    log = result.get("execution_log", [])
    if log:
        print("\n--- 推理轨迹 ---")
        for entry in log:
            print(f"  {entry}")

    # 修复总结
    summary = result.get("final_summary", "")
    if summary:
        print(f"\n--- 修复总结 ---\n{summary}")

    # 统计
    print(f"\n--- 统计 ---")
    print(f"  LLM 调用: {result.get('llm_call_count', 0)} 次")
    print(f"  工具调用: {result.get('tool_call_count', 0)} 次")
    print(f"  修复轮数: {result.get('fix_round', 0)} 轮")
    print(f"  修改文件: {result.get('changes_made', [])}")
    print(f"  测试全部通过: {result.get('all_tests_passed', False)}")


if __name__ == "__main__":
    main()
