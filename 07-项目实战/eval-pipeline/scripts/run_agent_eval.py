"""
Agent 评测 Demo

运行方式:
    python scripts/run_agent_eval.py

说明:
    - 工具调用匹配度和步数效率始终可用
    - 任务完成率的 LLM 判断需要 API key（无 key 时回退为包含匹配）
    - 评测数据中已预填 actual_tool_calls 和 prediction
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import EvalConfig
from app.data_loader import load_eval_set, validate_eval_set
from app.evaluators import AgentMetricsEvaluator
from app.llm_client import LLMClient
from app.report import print_report, save_report
from app.runner import EvalRunner


def main():
    print("=" * 60)
    print("          Agent 评测 Demo")
    print("=" * 60)

    config = EvalConfig(project_root=project_root)

    # 加载评测集
    eval_path = config.data_dir / "agent_eval_set.json"
    eval_set = load_eval_set(eval_path)
    print(f"\n已加载 {len(eval_set)} 条评测数据")

    # 校验
    errors = validate_eval_set(eval_set, ["id", "task_description", "prediction"])
    if errors:
        print(f"评测集校验失败: {errors}")
        return

    # 构建评估器
    llm_client = None
    if config.openai_api_key:
        llm_client = LLMClient(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            model=config.openai_model,
        )
        print("已启用 LLM 任务完成度判断")
    else:
        print("未配置 OPENAI_API_KEY，任务完成度将使用包含匹配作为回退")

    agent_evaluator = AgentMetricsEvaluator(llm_client=llm_client)
    evaluators = [agent_evaluator]

    # 运行评测
    runner = EvalRunner()
    summaries = runner.run(eval_set, evaluators)

    # 打印报告
    print_report(summaries)

    # 保存报告
    report_path = save_report(summaries, config.output_path, eval_name="agent_eval")
    print(f"详细报告已保存: {report_path}")

    # 额外打印 Agent 指标细节
    if "agent_metrics" in summaries:
        print("\n--- Agent 指标详情 ---")
        for i, result in enumerate(summaries["agent_metrics"].results):
            item_id = eval_set[i].get("id", f"#{i+1}")
            sub = result.details.get("sub_scores", {})
            print(
                f"  {item_id}: "
                f"任务完成={sub.get('task_completion', 0):.2f}  "
                f"工具匹配={sub.get('tool_accuracy', 0):.2f}  "
                f"步数效率={sub.get('step_efficiency', 0):.2f}  "
                f"综合={result.score:.2f}"
            )

            # 工具调用细节
            tool_detail = result.details.get("tool_accuracy", {})
            if tool_detail.get("missed"):
                print(f"         缺失工具: {tool_detail['missed']}")
            if tool_detail.get("extra"):
                print(f"         多余工具: {tool_detail['extra']}")


if __name__ == "__main__":
    main()
