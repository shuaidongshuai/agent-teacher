#!/usr/bin/env python3
"""
一个适合教学演示的最小 Agent 项目。

这个项目故意把结构拆得比较清楚，让初学者能直接看到：
1. 用户目标如何被解析
2. 计划如何生成
3. 执行建议如何补充
4. 反思器如何检查计划质量

运行方式：
    python3 main.py "一周内完成 Agent 基础学习，并做一个最小 Demo"
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import textwrap
import traceback
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import List, Optional


@dataclass
class GoalContext:
    """保存对用户目标的结构化理解。"""

    raw_goal: str
    topic: str
    deadline_text: str
    deliverable: str
    estimated_days: int
    constraints: List[str]


@dataclass
class PlanStep:
    """表示计划中的一个步骤。"""

    step_id: int
    title: str
    objective: str
    action: str
    output: str
    time_hint: str


@dataclass
class ReflectionResult:
    """表示反思器的检查结果。"""

    issues: List[str]
    improvements: List[str]
    overall_assessment: str


class OpenAIPlannerClient:
    """
    一个尽量简化的 OpenAI 调用客户端。

    这里不依赖第三方库，而是使用标准库发送 HTTP 请求，方便在教学仓库中直接阅读。
    如果调用失败，主流程会自动退回本地教学模式。
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        # 允许通过环境变量覆盖 API 地址，方便接代理或兼容网关。
        # 例如：
        #   https://api.openai.com
        #   https://api.chatanywhere.tech
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/")
        self.model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
        self.api_style = self._read_api_style()
        self.ssl_verify = self._read_ssl_verify_setting()

    def available(self) -> bool:
        return bool(self.api_key)

    def generate_plan(self, goal: str) -> Optional[dict]:
        if not self.available():
            self._log("未检测到 OPENAI_API_KEY，跳过 LLM 调用，回退到本地教学模式。")
            return None

        prompt = textwrap.dedent(
            f"""
            你是一个学习任务规划 Agent。
            请把下面的学习目标拆解为结构化计划，并只返回 JSON。

            用户目标：{goal}

            返回格式：
            {{
              "topic": "主题",
              "deadline_text": "时间限制",
              "deliverable": "预期产出",
              "estimated_days": 7,
              "constraints": ["约束1", "约束2"],
              "steps": [
                {{
                  "step_id": 1,
                  "title": "步骤标题",
                  "objective": "步骤目的",
                  "action": "具体动作",
                  "output": "产出物",
                  "time_hint": "时间建议"
                }}
              ],
              "reflection": {{
                "issues": ["问题1"],
                "improvements": ["改进1"],
                "overall_assessment": "整体评价"
              }}
            }}
            """
        ).strip()

        payload = self._build_payload(prompt)

        self._log_request(payload)

        request = urllib.request.Request(
            self._build_api_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=30,
                context=self._build_ssl_context(),
            ) as response:
                body = response.read().decode("utf-8")
                self._log_response(body)
        except Exception as exc:
            self._log_exception(exc)
            return None

        try:
            data = json.loads(body)
            text_output = self._extract_text_output(data)
            if not text_output:
                self._log("未能从返回结果中提取出可解析文本，回退到本地教学模式。")
                return None
            self._log("提取到的文本结果：")
            self._log(text_output)
            return json.loads(text_output)
        except Exception as exc:
            self._log_exception(exc)
            return None

    def _build_api_url(self) -> str:
        """
        根据接口风格拼接目标地址。

        支持两种风格：
        - responses
        - chat_completions
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
        按接口风格构造请求体。
        """

        if self.api_style == "chat_completions":
            return {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                "temperature": 0.2,
            }

        return {
            "model": self.model,
            "input": prompt,
        }

    def _build_ssl_context(self) -> ssl.SSLContext:
        """
        根据环境变量决定是否校验证书。

        默认开启校验；
        当 OPENAI_SSL_VERIFY=false 时，创建一个不校验证书的上下文。
        """

        if self.ssl_verify:
            return ssl.create_default_context()

        self._log("警告：OPENAI_SSL_VERIFY=false，当前已关闭 SSL 证书校验，仅建议用于本地调试。")
        unverified_context = ssl._create_unverified_context()
        return unverified_context

    def _log_request(self, payload: dict) -> None:
        """
        打印请求日志，方便排查代理地址、模型名、入参格式等问题。
        """

        self._log("开始调用 LLM。")
        self._log(f"接口风格：{self.api_style}")
        self._log(f"请求地址：{self._build_api_url()}")
        self._log(f"SSL 校验：{self.ssl_verify}")
        self._log(f"Authorization：Bearer {self._masked_api_key()}")
        self._log("请求入参：")
        self._log(json.dumps(payload, ensure_ascii=False, indent=2))

    def _log_response(self, body: str) -> None:
        """打印接口原始返回值。"""

        self._log("接口原始返回：")
        self._log(body)

    def _log_exception(self, exc: Exception) -> None:
        """打印异常类型、异常信息和堆栈。"""

        self._log("LLM 调用发生异常：")
        self._log(f"{type(exc).__name__}: {exc}")

        if isinstance(exc, urllib.error.HTTPError):
            try:
                error_body = exc.read().decode("utf-8")
                self._log("HTTP 错误响应体：")
                self._log(error_body)
            except Exception as read_exc:
                self._log(f"读取 HTTP 错误响应体失败：{read_exc}")

        self._log("异常堆栈：")
        self._log(traceback.format_exc())

    def _masked_api_key(self) -> str:
        """避免把完整 Key 直接打印到终端。"""

        if not self.api_key:
            return "<empty>"
        if len(self.api_key) <= 8:
            return "***"
        return f"{self.api_key[:4]}...{self.api_key[-4:]}"

    @staticmethod
    def _read_ssl_verify_setting() -> bool:
        """
        读取 SSL 校验开关。

        约定：
        - 未设置时，默认 True
        - false / 0 / no / off 都视为关闭
        """

        raw_value = os.getenv("OPENAI_SSL_VERIFY", "true").strip().lower()
        return raw_value not in {"false", "0", "no", "off"}

    @staticmethod
    def _read_api_style() -> str:
        """
        读取接口风格。

        支持：
        - responses
        - chat_completions
        """

        raw_value = os.getenv("OPENAI_API_STYLE", "responses").strip().lower()
        if raw_value in {"chat", "chat_completions", "chat-completions"}:
            return "chat_completions"
        return "responses"

    @staticmethod
    def _log(message: str) -> None:
        print(f"[OpenAIPlannerClient] {message}", file=sys.stderr)

    def _extract_text_output(self, response_json: dict) -> Optional[str]:
        """根据接口风格提取文本结果。"""

        if self.api_style == "chat_completions":
            return self._extract_chat_completions_text(response_json)
        return self._extract_responses_text(response_json)

    @staticmethod
    def _extract_responses_text(response_json: dict) -> Optional[str]:
        """兼容 Responses API 常见输出结构，尽量提取文本内容。"""

        output = response_json.get("output", [])
        collected_text: List[str] = []

        for item in output:
            content_items = item.get("content", [])
            for content in content_items:
                text_value = content.get("text")
                if text_value:
                    collected_text.append(text_value)

        if collected_text:
            return "\n".join(collected_text).strip()

        fallback_text = response_json.get("output_text")
        if isinstance(fallback_text, str) and fallback_text.strip():
            return fallback_text.strip()

        return None

    @staticmethod
    def _extract_chat_completions_text(response_json: dict) -> Optional[str]:
        """从 Chat Completions 返回结构中提取文本。"""

        choices = response_json.get("choices", [])
        if not choices:
            return None

        first_choice = choices[0]
        message = first_choice.get("message", {})
        content = message.get("content")

        if isinstance(content, str) and content.strip():
            return content.strip()

        if isinstance(content, list):
            collected_text: List[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_value = item.get("text", "")
                    if text_value:
                        collected_text.append(text_value)
            if collected_text:
                return "\n".join(collected_text).strip()

        return None


class GoalAnalyzer:
    """负责把自然语言目标转成结构化上下文。"""

    def analyze(self, goal: str) -> GoalContext:
        estimated_days = self._extract_days(goal)
        deadline_text = self._extract_deadline_text(goal)
        topic = self._extract_topic(goal)
        deliverable = self._extract_deliverable(goal)
        constraints = self._extract_constraints(goal, estimated_days)

        return GoalContext(
            raw_goal=goal,
            topic=topic,
            deadline_text=deadline_text,
            deliverable=deliverable,
            estimated_days=estimated_days,
            constraints=constraints,
        )

    def _extract_days(self, goal: str) -> int:
        """
        用非常直观的规则提取天数。

        教学重点不是中文时间解析本身，所以这里只保留最容易理解的规则。
        """

        if "一天" in goal or "1天" in goal:
            return 1
        if "两天" in goal or "2天" in goal:
            return 2
        if "三天" in goal or "3天" in goal:
            return 3
        if "一周" in goal or "7天" in goal:
            return 7
        if "两周" in goal or "14天" in goal:
            return 14

        match = re.search(r"(\d+)\s*天", goal)
        if match:
            return int(match.group(1))

        return 7

    def _extract_deadline_text(self, goal: str) -> str:
        match = re.search(r"(.*?(?:天内|周内|本周|今天|今晚))", goal)
        if match:
            return match.group(1).strip()
        return "未明确说明，按 7 天估算"

    def _extract_topic(self, goal: str) -> str:
        cleaned = goal
        cleaned = re.sub(r".*?(?:天内|周内)", "", cleaned)
        cleaned = cleaned.replace("完成", "").replace("准备", "")
        cleaned = re.sub(r"^\s*一次\s*", "", cleaned)
        cleaned = cleaned.replace("并做一个最小 Demo", "")
        cleaned = cleaned.replace("并做一个demo", "")
        cleaned = cleaned.strip(" ，,。")
        return cleaned or "通用学习主题"

    def _extract_deliverable(self, goal: str) -> str:
        if "分享" in goal:
            return "一份可讲解的分享提纲或讲稿"
        if "Demo" in goal or "demo" in goal:
            return "一个最小可运行 Demo"
        if "复盘" in goal:
            return "一份复盘总结"
        return "一份阶段化学习成果记录"

    def _extract_constraints(self, goal: str, estimated_days: int) -> List[str]:
        constraints = [f"总时长约 {estimated_days} 天"]

        if "最小 Demo" in goal or "Demo" in goal or "demo" in goal:
            constraints.append("最终必须有可运行成果，而不仅是阅读笔记")
        if "分享" in goal:
            constraints.append("输出需要适合讲解，结构要清晰")
        if estimated_days <= 3:
            constraints.append("计划必须足够轻量，避免任务过载")

        return constraints


class Planner:
    """负责生成计划步骤。"""

    def build_plan(self, context: GoalContext) -> List[PlanStep]:
        step_count = 4 if context.estimated_days >= 5 else 3
        time_slices = self._build_time_slices(context.estimated_days, step_count)

        steps = [
            PlanStep(
                step_id=1,
                title="理解主题与搭建框架",
                objective=f"快速建立对“{context.topic}”的整体认识",
                action="阅读核心概念资料，整理关键词，明确这次学习的范围和目标。",
                output="一页主题笔记或思维导图",
                time_hint=time_slices[0],
            ),
            PlanStep(
                step_id=2,
                title="拆解关键知识点",
                objective="找出必须掌握的核心模块，而不是平均用力。",
                action="把主题拆成 3 到 5 个重点知识块，并为每个知识块安排学习顺序。",
                output="结构化学习清单",
                time_hint=time_slices[1],
            ),
            PlanStep(
                step_id=3,
                title="动手产出最小成果",
                objective="把知识转成看得见的结果，避免停留在理解层。",
                action=f"围绕“{context.deliverable}”完成最小版本，优先保证能运行、能展示或能讲清楚。",
                output=context.deliverable,
                time_hint=time_slices[2],
            ),
        ]

        if step_count == 4:
            steps.append(
                PlanStep(
                    step_id=4,
                    title="复盘与补缺",
                    objective="检查计划执行结果，修正遗漏，形成闭环。",
                    action="回看前面产出，补齐薄弱点，记录仍然不清楚的概念和下一步行动。",
                    output="一份复盘记录和后续待办",
                    time_hint=time_slices[3],
                )
            )

        return steps

    def _build_time_slices(self, estimated_days: int, step_count: int) -> List[str]:
        if step_count == 3:
            return [
                "第 1 天",
                f"第 2 天到第 {max(2, estimated_days - 1)} 天",
                f"第 {estimated_days} 天",
            ]

        return [
            "第 1 天",
            f"第 2 天到第 {max(2, estimated_days - 2)} 天",
            f"第 {max(3, estimated_days - 1)} 天",
            f"第 {estimated_days} 天",
        ]


class Executor:
    """负责给计划补充更细的执行建议。"""

    def enrich(self, context: GoalContext, steps: List[PlanStep]) -> List[PlanStep]:
        enriched_steps: List[PlanStep] = []

        for step in steps:
            action = step.action

            if step.step_id == 1:
                action += " 建议先写下：这个主题是什么、解决什么问题、有哪些核心组件。"
            elif step.step_id == 2:
                action += " 每个知识块最好配一个例子，避免只有抽象概念。"
            elif step.step_id == 3:
                action += " 最小成果要优先追求完成闭环，不要过早追求复杂功能。"
            elif step.step_id == 4:
                action += " 复盘时重点记录：哪里卡住了、原因是什么、下次怎么改。"

            # 这里重新构造对象，而不是原地修改，能让数据流更清楚。
            enriched_steps.append(
                PlanStep(
                    step_id=step.step_id,
                    title=step.title,
                    objective=step.objective,
                    action=action,
                    output=step.output,
                    time_hint=step.time_hint,
                )
            )

        return enriched_steps


class Reflector:
    """负责对计划做一次简单而明确的自检。"""

    def review(self, context: GoalContext, steps: List[PlanStep]) -> ReflectionResult:
        issues: List[str] = []
        improvements: List[str] = []

        if context.estimated_days <= 3 and len(steps) > 3:
            issues.append("时间窗口较短，但计划步骤偏多，可能导致执行压力过大。")
            improvements.append("把阅读目标压缩到最核心的 2 到 3 个知识点。")

        if not any("复盘" in step.title for step in steps):
            issues.append("当前计划缺少明确复盘环节，学习闭环不完整。")
            improvements.append("在最后增加一个复盘步骤，记录薄弱点和后续行动。")

        if not any("Demo" in step.output or "成果" in step.output or "讲稿" in step.output for step in steps):
            issues.append("计划的最终产出不够明确，可能导致学完后没有可展示结果。")
            improvements.append("明确最终产出，比如 Demo、讲稿、总结文档或学习笔记。")

        if not issues:
            overall_assessment = "计划结构完整，已经覆盖理解、拆解、产出和复盘，适合作为第一版执行方案。"
            improvements.append("执行时继续记录真实耗时，后续可以把计划调整得更精细。")
        else:
            overall_assessment = "计划基本可用，但仍有可执行性风险，建议先按改进项修正后再开始。"

        return ReflectionResult(
            issues=issues,
            improvements=improvements,
            overall_assessment=overall_assessment,
        )


class StudyPlanningAgent:
    """把分析、规划、执行、反思四个模块串起来。"""

    def __init__(self) -> None:
        self.goal_analyzer = GoalAnalyzer()
        self.planner = Planner()
        self.executor = Executor()
        self.reflector = Reflector()
        self.openai_client = OpenAIPlannerClient()

    def run(self, goal: str) -> dict:
        """
        主入口。

        如果可用，会优先尝试真实模型生成；
        如果失败，则自动回退到本地教学模式。
        """

        llm_result = self.openai_client.generate_plan(goal)
        if llm_result:
            return {
                "mode": "openai",
                "result": llm_result,
            }

        context = self.goal_analyzer.analyze(goal)
        steps = self.planner.build_plan(context)
        enriched_steps = self.executor.enrich(context, steps)
        reflection = self.reflector.review(context, enriched_steps)

        return {
            "mode": "local",
            "result": {
                "goal_context": asdict(context),
                "steps": [asdict(step) for step in enriched_steps],
                "reflection": asdict(reflection),
            },
        }


def render_result(data: dict) -> str:
    """把结构化结果渲染成适合命令行阅读的文本。"""

    mode = data["mode"]
    result = data["result"]

    if mode == "openai":
        lines = [
            "=== Study Planning Agent ===",
            "模式：OpenAI API",
            "",
            json.dumps(result, ensure_ascii=False, indent=2),
        ]
        return "\n".join(lines)

    goal_context = result["goal_context"]
    steps = result["steps"]
    reflection = result["reflection"]

    lines = [
        "=== Study Planning Agent ===",
        "模式：本地教学模式",
        "",
        "[1] 目标分析",
        f"- 原始目标：{goal_context['raw_goal']}",
        f"- 学习主题：{goal_context['topic']}",
        f"- 时间限制：{goal_context['deadline_text']}",
        f"- 预期产出：{goal_context['deliverable']}",
        f"- 预计天数：{goal_context['estimated_days']}",
        f"- 约束条件：{'；'.join(goal_context['constraints'])}",
        "",
        "[2] 任务计划",
    ]

    for step in steps:
        lines.extend(
            [
                f"{step['step_id']}. {step['title']}（{step['time_hint']}）",
                f"   目标：{step['objective']}",
                f"   动作：{step['action']}",
                f"   产出：{step['output']}",
            ]
        )

    lines.extend(["", "[3] 反思结果"])

    if reflection["issues"]:
        lines.append("- 发现问题：")
        for issue in reflection["issues"]:
            lines.append(f"  - {issue}")
    else:
        lines.append("- 发现问题：暂无明显问题")

    lines.append("- 改进建议：")
    for improvement in reflection["improvements"]:
        lines.append(f"  - {improvement}")

    lines.extend(
        [
            f"- 整体判断：{reflection['overall_assessment']}",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) < 2:
        print('用法：python3 main.py "你的学习目标"')
        return 1

    goal = sys.argv[1].strip()
    if not goal:
        print("学习目标不能为空。")
        return 1

    agent = StudyPlanningAgent()
    result = agent.run(goal)
    print(render_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
