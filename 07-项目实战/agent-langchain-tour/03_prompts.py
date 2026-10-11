"""
03_prompts.py —— 提示词工程（LangChain v1）

本节目标：用「模板」把提示词和变量解耦，并掌握 v1 的动态系统提示。

对应 README「提示词工程」一节。涉及：
1. ChatPromptTemplate：带占位符的提示词模板 + 变量填充
2. 组成「模板 | 模型」的链（LCEL 管道写法）
3. few-shot：把示例写进模板，提升稳定性
4. @dynamic_prompt：v1 中间件，按运行时 state/context 动态生成 system prompt

运行：python 03_prompts.py
"""

from __future__ import annotations

from common import get_model, require_key
from langchain_core.prompts import ChatPromptTemplate


def demo_prompt_template() -> None:
    """最常用：带变量的模板，复用同一套提示词处理不同输入。"""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "你是{role}，用{style}的风格回答。"),
            ("human", "{question}"),
        ]
    )
    # 「模板 | 模型」用管道串成一条可调用链。
    chain = prompt | get_model()
    resp = chain.invoke(
        {"role": "资深后端工程师", "style": "简洁技术", "question": "什么是幂等？"}
    )
    print("[template]", resp.text)


def demo_few_shot() -> None:
    """few-shot：把「输入->输出」示例写进模板，约束输出格式。"""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "把用户输入改写成电报体（去掉虚词，保留关键信息）。"),
            ("human", "明天下午三点我们在会议室开个短会"),
            ("ai", "明天15:00 会议室 开会"),
            ("human", "麻烦你帮我把这封邮件在周五之前发出去"),
            ("ai", "周五前 发邮件"),
            ("human", "{text}"),
        ]
    )
    chain = prompt | get_model()
    resp = chain.invoke({"text": "我想请你帮忙预订一张下周一飞上海的机票"})
    print("[few-shot]", resp.text)


def demo_dynamic_prompt() -> None:
    """@dynamic_prompt：v1 中间件，运行时按上下文动态拼 system prompt。

    场景：根据用户等级/语言/权限实时调整系统提示，而不是写死一个。
    这里演示根据 context 里的 user_level 切换语气。
    """
    from dataclasses import dataclass

    from langchain.agents import create_agent
    from langchain.agents.middleware import dynamic_prompt

    @dataclass
    class Context:
        user_level: str  # "beginner" / "expert"

    @dynamic_prompt
    def level_aware_prompt(request) -> str:
        level = request.runtime.context.user_level
        if level == "beginner":
            return "你面向初学者，多打比方、少用术语。"
        return "你面向专家，直接给要点、可用术语。"

    agent = create_agent(
        model=get_model(),
        tools=[],
        middleware=[level_aware_prompt],
        context_schema=Context,
    )

    for level in ("beginner", "expert"):
        out = agent.invoke(
            {"messages": [{"role": "user", "content": "什么是向量？"}]},
            context=Context(user_level=level),
        )
        print(f"[dynamic:{level}]", out["messages"][-1].text)


if __name__ == "__main__":
    if not require_key():
        raise SystemExit(0)
    # demo_prompt_template()
    # demo_few_shot()
    demo_dynamic_prompt()
