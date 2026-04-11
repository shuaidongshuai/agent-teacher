from __future__ import annotations

import logging
from typing import Any, Callable, Dict

from .llm_client import LLMClient
from .prompts import (
    ANALYZE_TASK_PROMPT,
    EXECUTE_STEP_PROMPT,
    PLAN_APPROACH_PROMPT,
    SUMMARIZE_PROMPT,
    VERIFY_RESULT_PROMPT,
)
from .sandbox import Sandbox
from .state import CodeAgentState
from .tools import list_dir, read_file, run_command, search_code, write_file

logger = logging.getLogger(__name__)


def make_nodes(
    llm: LLMClient,
    sandbox: Sandbox,
    max_fix_rounds: int = 3,
    max_tool_calls: int = 10,
    max_llm_calls: int = 8,
) -> Dict[str, Callable[[CodeAgentState], Dict[str, Any]]]:
    """工厂函数：创建 LangGraph 节点。"""

    # 工具分发器
    tool_dispatch = {
        "read_file": lambda args: read_file(sandbox, args.get("path", "")),
        "write_file": lambda args: write_file(sandbox, args.get("path", ""), args.get("content", "")),
        "list_dir": lambda args: list_dir(sandbox, args.get("path", ".")),
        "search_code": lambda args: search_code(sandbox, args.get("pattern", ""), args.get("path", ".")),
        "run_command": lambda args: run_command(sandbox, args.get("cmd", "")),
    }

    def analyze_task(state: CodeAgentState) -> Dict[str, Any]:
        """分析任务，识别相关文件。"""
        task = state.get("task_description", "")
        log = list(state.get("execution_log", []))
        call_count = state.get("llm_call_count", 0)

        # 列出项目文件
        dir_result = list_dir(sandbox, ".")
        file_list = dir_result.get("entries", "")

        prompt = ANALYZE_TASK_PROMPT.format(
            task_description=task,
            file_list=file_list,
        )

        result = llm.generate_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        call_count += 1

        task_type = result.get("task_type", "fix_bug")
        relevant_files = result.get("relevant_files", [])
        analysis = result.get("analysis", "")

        # 读取相关文件
        code_contents = {}
        for fpath in relevant_files:
            r = read_file(sandbox, fpath)
            if r.get("success") == "true":
                code_contents[fpath] = r["content"]

        log.append(f"[analyze_task] 类型={task_type}, 相关文件={relevant_files}")
        log.append(f"[analyze_task] 分析: {analysis}")

        return {
            "task_type": task_type,
            "relevant_files": relevant_files,
            "code_contents": code_contents,
            "llm_call_count": call_count,
            "execution_log": log,
            "execution_history": [],
            "changes_made": [],
            "tool_call_count": 0,
            "fix_round": 0,
            "current_step_index": 0,
        }

    def plan_approach(state: CodeAgentState) -> Dict[str, Any]:
        """制定修复/执行计划。"""
        task = state.get("task_description", "")
        code_contents = state.get("code_contents", {})
        test_results = state.get("test_results", "（尚未运行测试）")
        log = list(state.get("execution_log", []))
        call_count = state.get("llm_call_count", 0)

        # 格式化代码内容
        code_text = ""
        for path, content in code_contents.items():
            code_text += f"\n--- {path} ---\n```python\n{content}\n```\n"

        prompt = PLAN_APPROACH_PROMPT.format(
            task_description=task,
            code_contents=code_text,
            test_results=test_results,
        )

        result = llm.generate_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        call_count += 1

        diagnosis = result.get("diagnosis", "")
        plan = result.get("plan", [])

        log.append(f"[plan_approach] 诊断: {diagnosis}")
        log.append(f"[plan_approach] 计划步数: {len(plan)}")

        return {
            "diagnosis": diagnosis,
            "plan": plan,
            "current_step_index": 0,
            "llm_call_count": call_count,
            "execution_log": log,
        }

    def execute_step(state: CodeAgentState) -> Dict[str, Any]:
        """执行计划中的当前步骤。"""
        task = state.get("task_description", "")
        plan = state.get("plan", [])
        step_idx = state.get("current_step_index", 0)
        code_contents = state.get("code_contents", {})
        history = list(state.get("execution_history", []))
        changes = list(state.get("changes_made", []))
        tool_count = state.get("tool_call_count", 0)
        log = list(state.get("execution_log", []))
        call_count = state.get("llm_call_count", 0)

        if step_idx >= len(plan):
            log.append("[execute_step] 所有计划步骤已完成")
            return {"execution_log": log}

        current_step = plan[step_idx]

        # 格式化代码上下文
        code_text = ""
        for path, content in list(code_contents.items())[:3]:
            code_text += f"\n--- {path} ---\n{content[:1000]}\n"

        # 格式化历史
        history_text = ""
        for h in history[-5:]:
            history_text += f"\n操作: {h.get('tool')}({h.get('args', {})})\n结果: {h.get('result', '')[:300]}\n"

        prompt = EXECUTE_STEP_PROMPT.format(
            task_description=task,
            current_step=str(current_step),
            code_context=code_text or "（未读取代码）",
            execution_history=history_text or "（无）",
        )

        result = llm.generate_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        call_count += 1

        tool_name = result.get("tool", "")
        tool_args = result.get("args", {})
        reasoning = result.get("reasoning", "")

        # 执行工具
        if tool_name in tool_dispatch and tool_count < max_tool_calls:
            tool_result = tool_dispatch[tool_name](tool_args)
            tool_count += 1

            # 如果是 write_file，记录修改
            if tool_name == "write_file" and tool_result.get("success") == "true":
                changes.append(tool_args.get("path", ""))
                # 更新 code_contents
                code_contents = dict(state.get("code_contents", {}))
                code_contents[tool_args.get("path", "")] = tool_args.get("content", "")

            # 如果是 read_file，更新 code_contents
            if tool_name == "read_file" and tool_result.get("success") == "true":
                code_contents = dict(state.get("code_contents", {}))
                code_contents[tool_args.get("path", "")] = tool_result.get("content", "")

            log.append(f"[execute_step] {tool_name}({tool_args}) → {tool_result.get('success', '?')}")

            history.append({
                "step": step_idx,
                "tool": tool_name,
                "args": tool_args,
                "reasoning": reasoning,
                "result": str(tool_result)[:500],
            })
        else:
            if tool_count >= max_tool_calls:
                log.append(f"[execute_step] 达到工具调用上限 ({max_tool_calls})")
            else:
                log.append(f"[execute_step] 未知工具: {tool_name}")

        return {
            "current_step_index": step_idx + 1,
            "execution_history": history,
            "changes_made": changes,
            "code_contents": code_contents,
            "tool_call_count": tool_count,
            "llm_call_count": call_count,
            "execution_log": log,
        }

    def verify_result(state: CodeAgentState) -> Dict[str, Any]:
        """运行测试验证修复结果。"""
        changes = state.get("changes_made", [])
        log = list(state.get("execution_log", []))
        call_count = state.get("llm_call_count", 0)
        fix_round = state.get("fix_round", 0)
        tool_count = state.get("tool_call_count", 0)

        # 运行 pytest
        test_result = run_command(sandbox, "pytest -v")
        tool_count += 1
        test_output = test_result.get("output", "")

        log.append(f"[verify] 测试结果: returncode={test_result.get('return_code', '?')}")

        # LLM 分析测试结果
        changes_summary = "\n".join(f"- 修改了 {f}" for f in changes) if changes else "无修改"

        prompt = VERIFY_RESULT_PROMPT.format(
            test_output=test_output[:1500],
            changes_summary=changes_summary,
        )

        result = llm.generate_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        call_count += 1

        all_passed = result.get("all_passed", False)
        summary = result.get("summary", "")
        remaining = result.get("remaining_issues", [])

        fix_round += 1
        log.append(f"[verify] 轮次={fix_round}, 全部通过={all_passed}, 剩余问题={len(remaining)}")

        return {
            "all_tests_passed": all_passed,
            "test_results": test_output,
            "fix_round": fix_round,
            "tool_call_count": tool_count,
            "llm_call_count": call_count,
            "execution_log": log,
        }

    def summarize(state: CodeAgentState) -> Dict[str, Any]:
        """生成修复总结。"""
        task = state.get("task_description", "")
        history = state.get("execution_history", [])
        test_results = state.get("test_results", "")
        log = list(state.get("execution_log", []))
        call_count = state.get("llm_call_count", 0)

        history_text = ""
        for h in history:
            history_text += f"\n步骤 {h.get('step', '?')}: {h.get('tool', '')}({h.get('args', {})})\n"
            history_text += f"原因: {h.get('reasoning', '')}\n"
            history_text += f"结果: {h.get('result', '')[:200]}\n"

        prompt = SUMMARIZE_PROMPT.format(
            task_description=task,
            execution_history=history_text or "（无操作记录）",
            final_test_result=test_results[:500] if test_results else "未运行测试",
        )

        summary = llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=1024,
        )
        call_count += 1

        log.append("[summarize] 已生成总结")

        return {
            "final_summary": summary,
            "llm_call_count": call_count,
            "execution_log": log,
        }

    return {
        "analyze_task": analyze_task,
        "plan_approach": plan_approach,
        "execute_step": execute_step,
        "verify_result": verify_result,
        "summarize": summarize,
    }
