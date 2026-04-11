"""
RAG 评测 Demo

运行方式:
    python scripts/run_rag_eval.py

说明:
    - rag_metrics 评估器始终可用（不需要 API key）
    - llm_judge 评估器需要 API key
    - 评测数据中已预填 retrieved_contexts 和 prediction
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import EvalConfig
from app.data_loader import load_eval_set, validate_eval_set
from app.evaluators import LLMJudgeEvaluator, RAGMetricsEvaluator
from app.llm_client import LLMClient
from app.report import print_report, save_report
from app.runner import EvalRunner


def main():
    print("=" * 60)
    print("          RAG 评测 Demo")
    print("=" * 60)

    config = EvalConfig(project_root=project_root)

    # 加载评测集
    eval_path = config.data_dir / "rag_eval_set.json"
    eval_set = load_eval_set(eval_path)
    print(f"\n已加载 {len(eval_set)} 条评测数据")

    # 校验
    errors = validate_eval_set(
        eval_set, ["id", "query", "ground_truth_contexts", "retrieved_contexts"]
    )
    if errors:
        print(f"评测集校验失败: {errors}")
        return

    # 构建评估器
    evaluators = []

    # RAG 指标始终可用
    rag_evaluator = RAGMetricsEvaluator(k=config.recall_k)
    evaluators.append(rag_evaluator)

    # LLM Judge
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

    # 运行评测
    runner = EvalRunner()
    summaries = runner.run(eval_set, evaluators)

    # 打印报告
    print_report(summaries)

    # 保存报告
    report_path = save_report(summaries, config.output_path, eval_name="rag_eval")
    print(f"详细报告已保存: {report_path}")

    # 额外打印 RAG 指标细节
    if "rag_metrics" in summaries:
        print("\n--- RAG 指标详情 ---")
        for i, result in enumerate(summaries["rag_metrics"].results):
            item_id = eval_set[i].get("id", f"#{i+1}")
            d = result.details
            print(
                f"  {item_id}: Recall@{d.get('k', '?')}={d.get('recall_at_k', 0):.2f}  "
                f"MRR={d.get('mrr', 0):.2f}  Precision={d.get('context_precision', 0):.2f}  "
                f"命中={d.get('hits', [])}"
            )


if __name__ == "__main__":
    main()
