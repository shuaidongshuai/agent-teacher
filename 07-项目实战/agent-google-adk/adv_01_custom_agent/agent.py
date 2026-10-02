"""进阶 01：自定义 BaseAgent —— 写出 Sequential/Parallel/Loop 表达不了的控制流

学习目标：
  - 继承 BaseAgent，重写 async def _run_async_impl(self, ctx)，自己掌控执行顺序
  - 在代码里读 ctx.session.state 做【条件分支】：Workflow Agent 只能"固定编排"，
    而自定义 Agent 能"看情况决定下一步跑谁"
  - 会用 `async for event in sub_agent.run_async(ctx): yield event` 驱动子 Agent

场景：一个"智能分流"Agent。先让分类器判断问题是"简单"还是"复杂"：
      简单 → 直接一句话回答；复杂 → 走"先列提纲再详细作答"的深度分支。
      这种 if/else 分流，用 SequentialAgent 是写不出来的。

运行：adk run adv_01_custom_agent   或   adk web 后选择本关卡
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")


# ---- 追踪回调：每个 Agent 进入/离开时打印，用来看清"先调谁、后调谁" ----
def on_enter(callback_context: CallbackContext):
    """Agent 执行前触发。返回 None = 不拦截，正常继续。"""
    print(f"▶ 进入 Agent: {callback_context.agent_name}")
    return None


def on_exit(callback_context: CallbackContext):
    """Agent 执行后触发。"""
    print(f"✔ 离开 Agent: {callback_context.agent_name}")
    return None


class SmartRouterAgent(BaseAgent):
    """根据分类结果动态选择"简单分支"或"复杂分支"的自定义 Agent。"""

    # 子 Agent 作为 pydantic 字段声明（BaseAgent 本身是 pydantic 模型）
    classifier: LlmAgent
    simple_branch: LlmAgent
    complex_branch: BaseAgent

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, name: str, classifier, simple_branch, complex_branch):
        super().__init__(
            name=name,
            classifier=classifier,
            simple_branch=simple_branch,
            complex_branch=complex_branch,
            # 声明进 sub_agents，ADK 才能正确管理它们的生命周期/事件
            sub_agents=[classifier, simple_branch, complex_branch],
            # 给路由器自身也挂上进入/离开日志
            before_agent_callback=on_enter,
            after_agent_callback=on_exit,
        )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # 第 1 步：分类器判断难度，结果写入 state["difficulty"]
        async for event in self.classifier.run_async(ctx):
            yield event

        difficulty = (ctx.session.state.get("difficulty") or "").strip().lower()

        # 第 2 步：这里就是 Workflow Agent 做不到的"条件分支"
        chosen = self.complex_branch if "complex" in difficulty else self.simple_branch
        # 打印分支决策，日志上就能看出为什么接着调用了哪个分支
        print(f"↳ 分类结果 = {difficulty!r}，选择分支: {chosen.name}")
        async for event in chosen.run_async(ctx):
            yield event


# --- 分类器：只输出 simple 或 complex ---
classifier = LlmAgent(
    name="difficulty_classifier",
    model=MODEL,
    description="判断用户问题是简单还是复杂。",
    instruction=(
        "判断用户的问题属于哪一类，只回答一个单词：\n"
        "- 若是常识/寒暄/一句话能答清 → 回答 simple\n"
        "- 若需要多步骤解释/对比/分析 → 回答 complex\n"
        "只输出 simple 或 complex，不要其他内容。"
    ),
    output_key="difficulty",
    before_agent_callback=on_enter,
    after_agent_callback=on_exit,
)

# --- 简单分支：一句话直接答 ---
simple_branch = LlmAgent(
    name="quick_answer",
    model=MODEL,
    description="用一句话简洁回答。",
    instruction="用一到两句话直接回答用户的问题，简洁明了。",
    before_agent_callback=on_enter,
    after_agent_callback=on_exit,
)

# --- 复杂分支：先列提纲，再详细作答（用一个顺序流当分支）---
complex_branch = SequentialAgent(
    name="deep_answer",
    description="先列要点再展开的深度回答。",
    before_agent_callback=on_enter,
    after_agent_callback=on_exit,
    sub_agents=[
        LlmAgent(
            name="deep_outliner",
            model=MODEL,
            instruction="先针对用户问题列出 3~4 个要回答的要点，每行一个。",
            output_key="deep_outline",
            before_agent_callback=on_enter,
            after_agent_callback=on_exit,
        ),
        LlmAgent(
            name="deep_writer",
            model=MODEL,
            instruction="根据这些要点，给用户一个条理清晰的详细回答：\n{deep_outline}",
            before_agent_callback=on_enter,
            after_agent_callback=on_exit,
        ),
    ],
)

root_agent = SmartRouterAgent(
    name="smart_router",
    classifier=classifier,
    simple_branch=simple_branch,
    complex_branch=complex_branch,
)
