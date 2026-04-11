from __future__ import annotations

ANALYZE_TASK_PROMPT = """你是一个专业的代码分析 Agent。请分析以下任务并制定策略。

## 任务描述
{task_description}

## 项目文件列表
{file_list}

## 输出要求

请严格按以下 JSON 格式输出：

```json
{{
    "task_type": "fix_bug 或 explain_code 或 add_feature",
    "relevant_files": ["需要查看的文件路径列表"],
    "analysis": "任务分析（一句话）"
}}
```"""


PLAN_APPROACH_PROMPT = """你是一个代码修复专家。基于以下信息，制定修复计划。

## 任务
{task_description}

## 相关代码
{code_contents}

## 测试结果（如有）
{test_results}

## 输出要求

请严格按以下 JSON 格式输出：

```json
{{
    "diagnosis": "问题诊断",
    "plan": [
        {{"step": 1, "action": "read_file/write_file/run_command/search_code", "target": "文件路径或命令", "description": "做什么"}},
        ...
    ]
}}
```"""


EXECUTE_STEP_PROMPT = """你是一个代码修复 Agent。请执行当前计划步骤。

## 当前任务
{task_description}

## 当前计划步骤
{current_step}

## 已读取的代码
{code_context}

## 已执行的操作和结果
{execution_history}

## 可用工具

1. read_file(path) — 读取文件内容
2. write_file(path, content) — 写入完整文件内容
3. run_command(cmd) — 执行命令（如 pytest, python）
4. search_code(pattern, path) — 搜索代码
5. list_dir(path) — 列出目录

## 输出要求

请严格按以下 JSON 格式输出：

```json
{{
    "tool": "工具名称",
    "args": {{"参数名": "参数值"}},
    "reasoning": "为什么执行这个操作"
}}
```

如果需要写入文件，args 应包含 "path" 和 "content"（完整文件内容）。"""


VERIFY_RESULT_PROMPT = """请分析测试结果，判断修复是否成功。

## 测试输出
{test_output}

## 修改内容摘要
{changes_summary}

## 输出要求

```json
{{
    "all_passed": true或false,
    "summary": "测试结果摘要",
    "remaining_issues": ["剩余问题列表，如果全部通过则为空列表"]
}}
```"""


SUMMARIZE_PROMPT = """请总结本次代码修复的完整过程。

## 任务
{task_description}

## 执行历史
{execution_history}

## 最终测试结果
{final_test_result}

请用以下格式输出总结：

1. **问题诊断**：发现了什么问题
2. **修复方案**：做了哪些修改
3. **验证结果**：测试是否通过
4. **修改文件**：列出修改的文件"""


EXPLAIN_CODE_PROMPT = """你是一个代码解释专家。请详细解释以下代码。

## 代码文件
{file_path}

## 代码内容
```python
{code_content}
```

请从以下几个方面解释：
1. **整体功能**：这段代码做什么
2. **核心逻辑**：关键算法或流程
3. **函数/类说明**：每个函数/类的职责
4. **潜在问题**：可能存在的 bug 或改进空间"""
