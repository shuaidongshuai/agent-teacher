#!/usr/bin/env python3
"""
一个适合教学演示的 Planner-Executor Agent 项目。

这个项目故意把角色拆清楚，让初学者能直接看到：
1. 架构师如何先生成完整计划
2. 工人如何严格按计划逐步执行
3. 某一步失败后如何只重试当前步骤
4. 最终结果如何落到文件系统

运行方式：
    python3 main.py "Planner-Executor 模式入门"
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import textwrap
import traceback
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class PlanStep:
    """表示架构师定义的一个可执行步骤。

    属性:
        step_id: 步骤的唯一标识符，从 1 开始
        title: 步骤的简短标题
        objective: 步骤要达成的目标描述
        output_file: 步骤产出物的文件名
        acceptance_criteria: 步骤完成的质量标准
    """

    step_id: int
    title: str
    objective: str
    output_file: str
    acceptance_criteria: str


@dataclass
class ExecutionRecord:
    """记录单个步骤的执行状态。

    用于追踪每个步骤的执行结果、重试次数和错误信息。

    属性:
        step_id: 对应的步骤 ID
        title: 步骤标题
        output_file: 产出文件路径
        status: 执行状态，可选值: "pending", "success", "failed"
        retries: 重试次数，0 表示一次成功
        error: 如果失败，记录错误信息
    """

    step_id: int
    title: str
    output_file: str
    status: str
    retries: int = 0
    error: str = ""


@dataclass
class TaskContext:
    """保存任务的基础上下文。

    这是一个简单的数据容器，在整个执行过程中在各个组件之间传递。

    属性:
        task: 用户输入的任务描述
        audience: 目标读者/受众群体
        output_dir: 输出文件的目录路径
    """

    task: str
    audience: str
    output_dir: str


class OpenAIPlannerExecutorClient:
    """
    一个尽量简化的 OpenAI 调用客户端。

    支持两种 API 风格:
    1. Chat Completions API (传统风格)
    2. Responses API (新一代风格)

    如果没有 API Key 或调用失败，主流程会自动退回本地教学模式。

    环境变量:
        OPENAI_API_KEY: OpenAI API 密钥
        OPENAI_BASE_URL: API 基础 URL，默认 https://api.openai.com
        OPENAI_MODEL: 使用的模型，默认 gpt-5-mini
        OPENAI_API_STYLE: API 风格，可选 "chat_completions" 或 "responses"
        OPENAI_SSL_VERIFY: 是否验证 SSL 证书，默认 true
    """

    def __init__(self) -> None:
        # 从环境变量读取配置
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/")
        self.model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
        self.api_style = self._read_api_style()
        self.ssl_verify = self._read_ssl_verify_setting()

    def available(self) -> bool:
        """检查 API 是否可用（是否配置了 API Key）。"""
        return bool(self.api_key)

    def build_plan(self, context: TaskContext) -> Optional[List[PlanStep]]:
        """
        调用 LLM 生成执行计划（作为架构师角色）。

        构建一个提示词，要求 LLM 作为架构师生成 4 个步骤的计划。
        返回 JSON 格式的步骤数组。

        参数:
            context: 任务上下文，包含任务描述和目标读者

        返回:
            PlanStep 列表，如果调用失败则返回 None
        """
        prompt = textwrap.dedent(
            f"""
            你是一个 Planner-Executor 系统里的架构师。
            你的职责不是直接完成任务，而是先产出一份详尽、稳定、可执行的步骤清单。
            请围绕下面任务，只返回 JSON 数组，不要输出解释。

            任务：{context.task}
            目标读者：{context.audience}

            每个步骤必须包含：
            - step_id
            - title
            - objective
            - output_file
            - acceptance_criteria

            要求：
            1. 输出 4 个步骤
            2. 步骤应按顺序执行
            3. 文件名使用 markdown 文件
            4. 内容面向教学材料生产
            """
        ).strip()

        result = self._generate_json(prompt)
        if not isinstance(result, list):
            return None

        try:
            return [PlanStep(**item) for item in result]
        except Exception as exc:
            self._log_exception(exc)
            return None

    def execute_step(
        self,
        context: TaskContext,
        step: PlanStep,
        previous_files: List[str],
    ) -> Optional[str]:
        """
        调用 LLM 执行单个步骤（作为工人角色）。

        构建一个提示词，要求 LLM 作为工人执行当前步骤，生成对应的 markdown 内容。

        参数:
            context: 任务上下文
            step: 要执行的步骤信息
            previous_files: 之前已完成的文件列表

        返回:
            生成的 markdown 内容，如果调用失败则返回 None
        """
        prompt = textwrap.dedent(
            f"""
            你是 Planner-Executor 系统里的工人。
            你不能改计划，只能执行当前步骤。

            总任务：{context.task}
            目标读者：{context.audience}
            当前步骤编号：{step.step_id}
            当前步骤标题：{step.title}
            当前步骤目标：{step.objective}
            当前步骤目标文件：{step.output_file}
            当前步骤完成标准：{step.acceptance_criteria}
            已完成文件：{previous_files if previous_files else "无"}

            请直接输出当前步骤对应的 markdown 正文，不要输出额外解释。
            """
        ).strip()

        result = self._generate_text(prompt)
        if not result:
            return None
        return result.strip()

    def _build_api_url(self) -> str:
        """
        根据 API 风格构建完整的 API URL。

        如果 base_url 已经包含 /v1，直接拼接；否则添加 /v1。
        """
        normalized_base_url = self.base_url
        if normalized_base_url.endswith("/v1"):
            api_base = normalized_base_url
        else:
            api_base = f"{normalized_base_url}/v1"

        if self.api_style == "chat_completions":
            return f"{api_base}/chat/completions"

        return f"{api_base}/responses"

    def _build_payload(self, prompt: str) -> dict:
        """
        根据 API 风格构建请求体。

        Chat Completions 使用 messages 格式，Responses 使用 input 格式。
        """
        if self.api_style == "chat_completions":
            return {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            }

        return {
            "model": self.model,
            "input": prompt,
        }

    def _generate_json(self, prompt: str) -> Optional[object]:
        """
        调用 LLM 生成 JSON 格式的结果。

        先调用 _generate_text 获取文本结果，然后尝试解析为 JSON。

        参数:
            prompt: 给 LLM 的提示词

        返回:
            解析后的 JSON 对象，失败返回 None
        """
        text_result = self._generate_text(prompt)
        if not text_result:
            return None

        try:
            return json.loads(text_result)
        except Exception as exc:
            self._log_exception(exc)
            return None

    def _generate_text(self, prompt: str) -> Optional[str]:
        """
        调用 LLM 生成文本结果的核心方法。

        步骤:
        1. 检查 API 是否可用
        2. 构建请求并发送
        3. 解析响应，提取文本内容

        参数:
            prompt: 给 LLM 的提示词

        返回:
            LLM 生成的文本，失败返回 None
        """
        if not self.available():
            self._log("未检测到 OPENAI_API_KEY，跳过 LLM 调用，回退到本地教学模式。")
            return None

        payload = self._build_payload(prompt)
        request = urllib.request.Request(
            self._build_api_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        self._log(f"开始调用 LLM，接口风格：{self.api_style}，模型：{self.model}")

        try:
            with urllib.request.urlopen(
                request,
                timeout=30,
                context=self._build_ssl_context(),
            ) as response:
                body = response.read().decode("utf-8")
        except Exception as exc:
            self._log_exception(exc)
            return None

        try:
            data = json.loads(body)
            text_output = self._extract_text_output(data)
            if not text_output:
                self._log("未能从返回结果中提取出文本。")
                return None
            return text_output
        except Exception as exc:
            self._log_exception(exc)
            return None

    def _extract_text_output(self, response_data: dict) -> str:
        """
        从 API 响应中提取文本内容。

        根据不同的 API 风格使用不同的提取逻辑:
        - chat_completions: 从 choices[0].message.content 提取
        - responses: 从 output_text 或 output 数组中提取

        参数:
            response_data: API 返回的 JSON 数据

        返回:
            提取出的文本内容
        """
        if self.api_style == "chat_completions":
            choices = response_data.get("choices") or []
            if not choices:
                return ""
            message = choices[0].get("message", {})
            content = message.get("content", "")
            # 处理内容为列表的情况（如多部分输出）
            if isinstance(content, list):
                parts: List[str] = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(item.get("text", ""))
                return "".join(parts).strip()
            return str(content).strip()

        # Responses API 风格
        if isinstance(response_data.get("output_text"), str):
            return response_data["output_text"].strip()

        output_items = response_data.get("output") or []
        parts: List[str] = []
        for item in output_items:
            contents = item.get("content") or []
            for content in contents:
                text_value = content.get("text")
                if isinstance(text_value, str):
                    parts.append(text_value)

        return "\n".join(part for part in parts if part).strip()

    def _build_ssl_context(self) -> ssl.SSLContext:
        """
        构建 SSL 上下文。

        根据配置决定是否验证 SSL 证书。关闭验证仅用于本地调试。
        """
        if self.ssl_verify:
            return ssl.create_default_context()
        self._log("警告：OPENAI_SSL_VERIFY=false，当前已关闭 SSL 证书校验，仅建议用于本地调试。")
        return ssl._create_unverified_context()

    def _read_api_style(self) -> str:
        """
        读取并验证 API 风格配置。

        环境变量 OPENAI_API_STYLE 可选值:
        - "responses": Responses API（新一代）
        - "chat_completions": Chat Completions API（传统风格）

        返回:
            验证后的 API 风格字符串
        """
        api_style = os.getenv("OPENAI_API_STYLE", "responses").strip().lower()
        if api_style not in {"responses", "chat_completions"}:
            self._log(f"未知 OPENAI_API_STYLE={api_style}，已回退为 responses。")
            return "responses"
        return api_style

    def _read_ssl_verify_setting(self) -> bool:
        """
        读取 SSL 证书验证设置。

        环境变量 OPENAI_SSL_VERIFY:
        - "true", "1": 验证 SSL（默认）
        - "false", "0", "no", "off": 不验证

        返回:
            是否验证 SSL 证书
        """
        value = os.getenv("OPENAI_SSL_VERIFY", "true").strip().lower()
        return value not in {"0", "false", "no", "off"}

    def _log_exception(self, exc: Exception) -> None:
        """
        记录异常信息，包括堆栈跟踪。

        对于 HTTP 错误，尝试读取并记录响应体。
        """
        self._log("LLM 调用发生异常：")
        self._log(f"{type(exc).__name__}: {exc}")

        if isinstance(exc, urllib.error.HTTPError):
            try:
                error_body = exc.read().decode("utf-8")
                self._log("HTTP 错误响应体：")
                self._log(error_body)
            except Exception as read_exc:
                self._log(f"读取 HTTP 错误响应体失败：{read_exc}")

        self._log(traceback.format_exc())

    def _log(self, message: str) -> None:
        """输出带前缀的日志信息。"""
        print(f"[OpenAIPlannerExecutorClient] {message}")


class Architect:
    """
    架构师角色：负责生成执行计划。

    这是 Planner-Executor 模式中的 "Planner" 部分。
    职责是分析任务需求，产出一份详细、可执行的步骤清单。

    设计模式:
    - 优先尝试使用 LLM 智能生成计划
    - 如果 LLM 不可用或失败，自动回退到本地模板
    """

    def __init__(self, client: OpenAIPlannerExecutorClient) -> None:
        """
        初始化架构师。

        参数:
            client: OpenAI 客户端实例，用于调用 LLM
        """
        self.client = client

    def build_plan(self, context: TaskContext) -> List[PlanStep]:
        """
        生成任务执行计划。

        优先尝试调用 LLM 生成计划，如果失败则使用本地模板。

        参数:
            context: 任务上下文

        返回:
            PlanStep 列表，包含按顺序执行的步骤
        """
        llm_plan = self.client.build_plan(context)
        if llm_plan:
            return llm_plan
        return self._build_local_plan(context)

    def _build_local_plan(self, context: TaskContext) -> List[PlanStep]:
        """
        使用本地模板生成默认计划。

        当 LLM 不可用时，提供一个通用的教学资料包生成计划。
        包含 4 个标准步骤：任务定义、学习大纲、核心概念、练习题。
        """
        task_name = context.task.strip()
        return [
            PlanStep(
                step_id=1,
                title="定义任务与学习目标",
                objective=f"明确主题《{task_name}》的学习范围、受众和预期成果。",
                output_file="01_任务定义.md",
                acceptance_criteria="文档必须包含主题说明、适用人群、学习目标。",
            ),
            PlanStep(
                step_id=2,
                title="设计学习大纲",
                objective="把主题拆成循序渐进的知识模块，形成学习顺序。",
                output_file="02_学习大纲.md",
                acceptance_criteria="文档必须包含 4 到 6 个分节，并说明每节要学什么。",
            ),
            PlanStep(
                step_id=3,
                title="整理核心概念",
                objective="提炼核心概念、流程和常见误区，形成主体讲义。",
                output_file="03_核心概念.md",
                acceptance_criteria="文档必须兼顾概念解释、流程说明和常见误区。",
            ),
            PlanStep(
                step_id=4,
                title="设计练习与总结",
                objective="补充练习题、思考方向和最终学习建议。",
                output_file="04_练习题.md",
                acceptance_criteria="文档必须包含练习题、参考思路和下一步建议。",
            ),
        ]


class Worker:
    """
    工人角色：负责执行单个步骤。

    这是 Planner-Executor 模式中的 "Executor" 部分。
    职责是严格按照计划执行当前步骤，生成对应的内容。

    设计模式:
    - 优先尝试使用 LLM 生成内容
    - 如果 LLM 不可用或失败，自动回退到本地模板
    - 不关心其他步骤，只专注当前步骤
    """

    def __init__(self, client: OpenAIPlannerExecutorClient) -> None:
        """
        初始化工人。

        参数:
            client: OpenAI 客户端实例，用于调用 LLM
        """
        self.client = client

    def execute(self, context: TaskContext, step: PlanStep, previous_files: List[str]) -> str:
        """
        执行单个步骤，生成对应的 markdown 内容。

        优先尝试调用 LLM 执行，如果失败则使用本地模板。

        参数:
            context: 任务上下文
            step: 要执行的步骤信息
            previous_files: 之前已完成的文件列表（用于上下文）

        返回:
            生成的 markdown 内容
        """
        content = self.client.execute_step(context, step, previous_files)
        if content:
            return content
        return self._build_local_content(context, step)

    def _build_local_content(self, context: TaskContext, step: PlanStep) -> str:
        """
        使用本地模板生成默认内容。

        根据步骤的 output_file 生成对应的教学资料内容。
        支持四种文件类型：01_任务定义.md、02_学习大纲.md、03_核心概念.md、04_练习题.md
        """
        title = context.task
        audience = context.audience

        if step.output_file == "01_任务定义.md":
            return textwrap.dedent(
                f"""
                # 任务定义

                ## 主题说明

                本资料包围绕“{title}”展开，目标是帮助 {audience} 用一套清晰、可执行的方式建立整体认知。

                ## 适用人群

                - 想系统理解这个主题的学习者
                - 已经看过零散资料，但缺少整体框架的人
                - 希望从概念走向实践的人

                ## 学习目标

                1. 理解这个主题为什么存在
                2. 理解核心概念和基本流程
                3. 识别常见误区和失败原因
                4. 能基于这套资料继续做练习或小项目
                """
            ).strip()

        if step.output_file == "02_学习大纲.md":
            return textwrap.dedent(
                f"""
                # 学习大纲

                ## 建议顺序

                1. 什么是 {title}
                2. 它解决什么问题
                3. 核心概念与标准流程
                4. 常见误区与失败原因
                5. 实战建议与练习方向

                ## 每部分要掌握什么

                ### 1. 什么是 {title}

                建立主题边界，避免只会背定义。

                ### 2. 它解决什么问题

                先理解“为什么需要它”，再理解“它怎么工作”。

                ### 3. 核心概念与标准流程

                关注关键术语、步骤顺序和各模块协作关系。

                ### 4. 常见误区与失败原因

                提前知道新手最容易踩的坑。

                ### 5. 实战建议与练习方向

                把知识转化成可执行动作，而不是停留在概念层面。
                """
            ).strip()

        if step.output_file == "03_核心概念.md":
            return textwrap.dedent(
                f"""
                # 核心概念

                ## 这个主题是什么

                {title} 不是一个孤立名词，而是一套帮助我们更稳定地完成任务的方法或系统设计思路。

                ## 它解决什么问题

                它主要解决“任务模糊、流程不稳定、执行结果不可控”这类问题，让复杂任务更容易被拆解、执行和复盘。

                ## 核心流程

                1. 明确目标
                2. 拆解步骤
                3. 逐步执行
                4. 检查结果
                5. 总结改进

                ## 常见误区

                - 只背定义，不理解适用场景
                - 以为流程越复杂越好
                - 没有把抽象概念转成实际动作
                - 遇到失败时无法定位是哪一步出问题
                """
            ).strip()

        return textwrap.dedent(
            f"""
            # 练习题与总结

            ## 练习题

            1. 用自己的话解释什么是 {title}。
            2. 说出它最想解决的 2 个核心问题。
            3. 画出你理解的基本流程图。
            4. 列出 3 个常见误区，并解释为什么容易踩坑。

            ## 参考思路

            - 回答时优先讲“为什么存在”，再讲“怎么工作”。
            - 不要只列术语，要结合一个具体场景解释。
            - 如果能把流程拆成步骤，说明你已经开始具备实践能力。

            ## 下一步建议

            建议把本资料包里的大纲、核心概念和练习题串起来，再做一个最小 Demo，验证自己是否真的理解了 {title}。
            """
        ).strip()


class PlannerExecutorAgent:
    """
    Planner-Executor Agent 的核心编排类。

    负责串联架构师、工人和重试逻辑，是整个系统的主控制器。

    工作流程:
    1. 调用 Architect 生成执行计划
    2. 遍历计划中的每个步骤
    3. 对每个步骤调用 Worker 执行（带重试机制）
    4. 记录每个步骤的执行状态
    5. 生成最终总结报告

    特性:
    - 支持步骤级别的重试（失败后只重试当前步骤，不是整个流程）
    - 支持内容质量验证
    - 失败时提前退出，避免无效执行
    """

    def __init__(self, max_retries: int = 2) -> None:
        """
        初始化 Agent。

        参数:
            max_retries: 每个步骤的最大重试次数，默认 2 次
        """
        self.client = OpenAIPlannerExecutorClient()
        self.architect = Architect(self.client)
        self.worker = Worker(self.client)
        self.max_retries = max_retries

    def run(self, context: TaskContext) -> dict:
        """
        运行完整的 Planner-Executor 流程。

        步骤:
        1. 创建输出目录
        2. 生成执行计划
        3. 按顺序执行每个步骤
        4. 生成最终总结

        参数:
            context: 任务上下文

        返回:
            包含执行结果的字典:
            - plan: 计划列表
            - records: 执行记录列表
            - success: 是否全部成功
            - output_dir: 输出目录
            - final_file: 最终总结文件路径
        """
        output_path = Path(context.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        plan = self.architect.build_plan(context)
        records: List[ExecutionRecord] = []
        completed_files: List[str] = []

        print("[PlannerExecutorAgent] 已生成执行计划：")
        for step in plan:
            print(
                f"  - Step {step.step_id}: {step.title} -> {step.output_file} "
                f"(完成标准：{step.acceptance_criteria})"
            )

        for step in plan:
            record = self._execute_with_retry(context, step, completed_files)
            records.append(record)

            # 如果步骤失败，提前退出并生成总结
            if record.status != "success":
                final_summary = self._build_final_summary(context, plan, records, success=False)
                self._write_text(output_path / "FINAL_总结.md", final_summary)
                return {
                    "plan": [asdict(step) for step in plan],
                    "records": [asdict(item) for item in records],
                    "success": False,
                    "output_dir": str(output_path),
                    "final_file": str(output_path / "FINAL_总结.md"),
                }

            completed_files.append(record.output_file)

        final_summary = self._build_final_summary(context, plan, records, success=True)
        self._write_text(output_path / "FINAL_总结.md", final_summary)
        return {
            "plan": [asdict(step) for step in plan],
            "records": [asdict(item) for item in records],
            "success": True,
            "output_dir": str(output_path),
            "final_file": str(output_path / "FINAL_总结.md"),
        }

    def _execute_with_retry(
        self,
        context: TaskContext,
        step: PlanStep,
        completed_files: List[str],
    ) -> ExecutionRecord:
        """
        执行单个步骤，带重试机制。

        最多重试 max_retries 次，每次失败都会记录错误信息。
        使用验证器检查产出内容质量。

        参数:
            context: 任务上下文
            step: 要执行的步骤
            completed_files: 已完成的文件列表

        返回:
            ExecutionRecord 包含执行结果
        """
        record = ExecutionRecord(
            step_id=step.step_id,
            title=step.title,
            output_file=step.output_file,
            status="pending",
        )

        output_path = Path(context.output_dir) / step.output_file

        for attempt in range(self.max_retries + 1):
            try:
                print(
                    f"[PlannerExecutorAgent] 开始执行 Step {step.step_id} "
                    f"(第 {attempt + 1} 次尝试)：{step.title}"
                )
                content = self.worker.execute(context, step, completed_files)
                self._validate_content(content, step)
                self._write_text(output_path, content)
                record.status = "success"
                record.retries = attempt
                print(f"[PlannerExecutorAgent] Step {step.step_id} 执行成功。")
                return record
            except Exception as exc:
                record.status = "failed"
                record.retries = attempt + 1
                record.error = f"{type(exc).__name__}: {exc}"
                print(
                    f"[PlannerExecutorAgent] Step {step.step_id} 执行失败："
                    f"{record.error}"
                )

        return record

    def _validate_content(self, content: str, step: PlanStep) -> None:
        """
        验证生成的内容是否满足最低质量要求。

        检查项:
        - 内容长度不少于 30 个字符
        - 包含 markdown 标题（# 符号）

        参数:
            content: 要验证的内容
            step: 对应的步骤信息

        异常:
            ValueError: 内容不满足质量要求时抛出
        """
        if not content or len(content.strip()) < 30:
            raise ValueError(f"步骤 {step.step_id} 产出内容过短，未达到最小质量要求。")
        if "#" not in content:
            raise ValueError(f"步骤 {step.step_id} 的内容缺少 markdown 标题。")

    def _write_text(self, path: Path, content: str) -> None:
        """
        将内容写入文件。

        参数:
            path: 文件路径
            content: 要写入的内容
        """
        path.write_text(content.strip() + "\n", encoding="utf-8")

    def _build_final_summary(
        self,
        context: TaskContext,
        plan: List[PlanStep],
        records: List[ExecutionRecord],
        success: bool,
    ) -> str:
        """
        生成最终执行总结报告。

        包含任务信息、执行状态、每个步骤的记录和下一步建议。

        参数:
            context: 任务上下文
            plan: 执行计划
            records: 执行记录列表
            success: 是否全部成功

        返回:
            markdown 格式的总结报告
        """
        status_text = "全部完成" if success else "中途失败"
        completed_count = sum(1 for record in records if record.status == "success")

        lines = [
            "# 最终总结",
            "",
            "## 总任务",
            "",
            context.task,
            "",
            "## 执行结果",
            "",
            f"- 总状态：{status_text}",
            f"- 完成步骤数：{completed_count}/{len(plan)}",
            f"- 输出目录：{context.output_dir}",
            "",
            "## 步骤记录",
            "",
        ]

        for record in records:
            line = (
                f"- Step {record.step_id} {record.title}：{record.status}，"
                f"重试 {record.retries} 次，文件 {record.output_file}"
            )
            lines.append(line)
            if record.error:
                lines.append(f"失败原因：{record.error}")

        lines.extend(
            [
                "",
                "## 下一步建议",
                "",
                "1. 检查每个文件是否真的满足步骤完成标准。",
                "2. 如果某一步内容过泛，可以单独重跑该步骤而不是整个流程。",
                "3. 后续可以继续加入审稿、校验、发布等下游角色。",
            ]
        )
        return "\n".join(lines)


def parse_args(argv: List[str]) -> argparse.Namespace:
    """
    解析命令行参数。

    参数:
        argv: 命令行参数列表（不包含程序名）

    返回:
        解析后的参数命名空间

    命令行参数:
        task: 要生成资料包的主题（必需）
        --audience: 目标读者，默认 "初学者"
        --output-dir: 输出目录，默认 "output"
    """
    parser = argparse.ArgumentParser(description="运行一个 Planner-Executor 教学 Agent。")
    parser.add_argument("task", help="要生成资料包的主题，例如：Planner-Executor 模式入门")
    parser.add_argument("--audience", default="初学者", help="目标读者，默认是初学者")
    parser.add_argument(
        "--output-dir",
        default="output",
        help="输出目录，默认是 output",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    context = TaskContext(
        task=args.task.strip(),
        audience=args.audience.strip(),
        output_dir=args.output_dir.strip(),
    )

    agent = PlannerExecutorAgent(max_retries=2)
    result = agent.run(context)

    print("\n=== 最终结果 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["success"]:
        print(f"\n已生成资料包，查看目录：{result['output_dir']}")
        return 0

    print("\n流程未完全成功，请查看 FINAL_总结.md 和失败步骤日志。")
    return 1


if __name__ == "__main__":
    # 从 sys.argv[1:] 获取命令行参数（跳过程序名）
    raise SystemExit(main(sys.argv[1:]))
