from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict

from .evaluators.base import EvalSummary

logger = logging.getLogger(__name__)


def print_report(summaries: Dict[str, EvalSummary]) -> None:
    """在终端打印评测报告表格。"""
    print("\n")
    print("=" * 70)
    print("                        评 测 报 告")
    print("=" * 70)

    # 表头
    print(f"{'评估器':<20} {'总数':>6} {'通过':>6} {'通过率':>8} {'平均分':>8}")
    print("-" * 70)

    total_all = 0
    passed_all = 0
    score_sum = 0.0
    score_count = 0

    for name, summary in summaries.items():
        pass_rate = f"{summary.pass_rate:.1%}"
        avg = f"{summary.avg_score:.3f}"
        print(f"{name:<20} {summary.total:>6} {summary.passed:>6} {pass_rate:>8} {avg:>8}")

        total_all += summary.total
        passed_all += summary.passed
        score_sum += summary.avg_score
        score_count += 1

    print("-" * 70)

    if score_count > 0:
        overall_rate = f"{passed_all / total_all:.1%}" if total_all > 0 else "N/A"
        overall_avg = f"{score_sum / score_count:.3f}"
        print(f"{'总计':<20} {total_all:>6} {passed_all:>6} {overall_rate:>8} {overall_avg:>8}")

    print("=" * 70)
    print()


def save_report(
    summaries: Dict[str, EvalSummary],
    output_path: Path,
    eval_name: str = "eval",
) -> Path:
    """保存 JSON 格式评测报告。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{eval_name}_{timestamp}.json"
    filepath = output_path / filename

    report = {
        "eval_name": eval_name,
        "timestamp": timestamp,
        "summary": {},
        "details": {},
    }

    for name, summary in summaries.items():
        report["summary"][name] = {
            "total": summary.total,
            "passed": summary.passed,
            "pass_rate": round(summary.pass_rate, 4),
            "avg_score": round(summary.avg_score, 4),
        }
        report["details"][name] = [
            {
                "score": round(r.score, 4),
                "passed": r.passed,
                "details": r.details,
            }
            for r in summary.results
        ]

    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info("报告已保存: %s", filepath)
    print(f"报告已保存: {filepath}")
    return filepath
