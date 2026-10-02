"""CI 回归闸门：用 AgentEvaluator 跑评测，达不到阈值就非零退出。

大白话——和 `adk eval` 的区别只在"结果给谁看"（底层都是把评测集问一遍 agent 再打分）：
  - `adk eval ...`        给**人看报告**：打印每条用例每个指标 PASS/FAIL + 分数，开发时手动看；
  - `python ci_gate.py`   给**机器看红绿灯**：过了退出码 0、没过退出码 1，挂 CI 里自动拦住变坏的改动。

把它放进 CI（如 GitHub Actions 的一个 step），改坏了 prompt/工具就会红灯拦截。
阈值取自同目录 test_config.json（adk eval 与这里都读它；字段含义见 agent.py 顶部说明）。

运行：
  python adv_06_eval/ci_gate.py        # 退出码 0=通过，1=未达标
需要真实模型凭证（会实际把 agent 跑一遍再对比）。
"""

import asyncio
import sys
from pathlib import Path

# 让脚本无论从哪运行都能把 adv_06_eval 当模块导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.adk.evaluation.agent_evaluator import AgentEvaluator

AGENT_MODULE = "adv_06_eval"
EVALSET = str(Path(__file__).parent / "adv_06_eval.evalset.json")


async def _run() -> None:
    # 低于 test_config.json 里的阈值时，evaluate 会抛 AssertionError
    await AgentEvaluator.evaluate(
        agent_module=AGENT_MODULE,
        eval_dataset_file_path_or_dir=EVALSET,
        num_runs=1,  # CI 里跑 1 遍快；想更稳可调大(会按多次取平均)
    )


def main() -> None:
    try:
        asyncio.run(_run())
    except AssertionError as e:
        print("❌ 评测未达标，CI 拦截：\n", str(e)[:800])
        sys.exit(1)
    except Exception as e:
        print(f"⚠️ 评测无法运行（多半是没配模型凭证/代理）：{type(e).__name__}: {str(e)[:200]}")
        sys.exit(2)
    print("✅ 评测通过，CI 放行")


if __name__ == "__main__":
    main()
