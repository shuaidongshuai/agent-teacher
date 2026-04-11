"""
Prompt 评测 Demo

运行方式:
    python scripts/run_prompt_eval.py

说明:
    - 无 API key 时仅运行 exact_match 评估器
    - 有 API key 时同时运行 llm_judge 评估器
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import EvalConfig
from app.data_loader import load_eval_set, validate_eval_set
from app.evaluators import ExactMatchEvaluator, LLMJudgeEvaluator
from app.llm_client import LLMClient
from app.report import print_report, save_report
from app.runner import EvalRunner


def main():
    print("=" * 60)
    print("          Prompt 评测 Demo")
    print("=" * 60)

    # 加载配置
    config = EvalConfig(project_root=project_root)

    # 加载评测集
    eval_path = config.data_dir / "prompt_eval_set.json"
    eval_set = load_eval_set(eval_path)
    print(f"\n已加载 {len(eval_set)} 条评测数据")

    # 校验
    errors = validate_eval_set(eval_set, ["id", "input", "prediction"])
    if errors:
        print(f"评测集校验失败: {errors}")
        return

    # 构建评估器列表
    evaluators = []

    # exact_match 始终可用
    exact_evaluator = ExactMatchEvaluator(mode="contains")
    evaluators.append(exact_evaluator)

    # llm_judge 需要 API key
    if config.openai_api_key:
        llm = LLMClient(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            model=config.openai_model,
        )
        llm_judge = LLMJudgeEvaluator(llm_client=llm, max_score=5)
        evaluators.append(llm_judge)
        print("已启用 LLM Judge 评估器")
    else:
        print("未配置 OPENAI_API_KEY，跳过 LLM Judge 评估器")
        print("提示: export OPENAI_API_KEY=your-key 后可启用完整评测")

    # 过滤评测集：只保留包含当前评估器的数据
    evaluator_names = {e.name for e in evaluators}

    # 运行评测
    runner = EvalRunner()
    summaries = runner.run(eval_set, evaluators)

    # 打印报告
    print_report(summaries)

    # 保存报告
    report_path = save_report(summaries, config.output_path, eval_name="prompt_eval")
    print(f"详细报告已保存: {report_path}")


if __name__ == "__main__":
    main()
