"""
07_memory_management.py —— 记忆管理策略（LangChain v1）

本节目标：对话越来越长会撑爆上下文窗口、变慢变贵。三种常用「瘦身」策略：

  1. 裁剪 Trim    —— 只保留最近 N 条/N tokens，丢掉更早的
  2. 摘要 Summarize —— 把早期对话压成一段摘要，保留信息密度
  3. 删除 Delete   —— 按条删除指定消息（如撤回敏感内容）

三者都通过 create_agent 的 middleware= 挂上；持久化靠 checkpointer。
对应 README「记忆管理策略」一节。

运行：python 07_memory_management.py
"""

from __future__ import annotations

from typing import Any

from common import get_model, require_key
from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import SummarizationMiddleware, before_model
from langchain.messages import RemoveMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.message import REMOVE_ALL_MESSAGES


# ---- 策略 1：裁剪（只留最近若干条）----
@before_model
def keep_last_messages(state: AgentState, runtime) -> dict[str, Any] | None:
    """每次调用模型前，只保留最近 2 条消息。

    用「清空 + 重放保留部分」的方式更新历史：
    RemoveMessage(REMOVE_ALL_MESSAGES) 先清空，再把要保留的放回去。
    （也可用 langchain.messages.trim_messages 做基于 token 数的裁剪。）
    """
    messages = state["messages"]
    if len(messages) <= 2:
        return None
    recent = messages[-2:]
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *recent]}


def build_trim_agent():
    return create_agent(
        model=get_model(),
        tools=[],
        middleware=[keep_last_messages],
        checkpointer=InMemorySaver(),
    )


def build_summary_agent():
    """策略 2：摘要。超过阈值就把旧消息压成摘要，只保留最近若干条原文。"""
    return create_agent(
        model=get_model(),
        tools=[],
        middleware=[
            # trigger：什么时候触发摘要（阈值条件）。比如 ("tokens", 4000) = 历史超过 4000 token 就压缩。
            # keep：触发之后，保留最近多少条原文（其余的才被压成摘要）。默认 ("messages", 20) = 留最近 20 条原样，更早的压成一段 summary（不包含最近20条）
            #   简单的对话，用户一问 模型一答，就是2条原文，所以2是记录了一轮对话。但如果有工具调用，那调用一次可能就是一条新的记录
            SummarizationMiddleware(
                model=get_model(),            # 用来写摘要的模型（可换更便宜的小模型）
                trigger=("tokens", 60),      # 累计 token 超过 50 触发摘要
                keep=("messages", 2),         # 摘要后保留最近 2 条消息
            )
        ],
        checkpointer=InMemorySaver(),
    )


def chat(agent, text: str, thread_id: str = "demo") -> str:
    config = {"configurable": {"thread_id": thread_id}}
    out = agent.invoke({"messages": [{"role": "user", "content": text}]}, config)
    return out["messages"][-1].text


def demo_trim() -> None:
    agent = build_trim_agent()
    for i in range(1, 3):
        chat(agent, f"这是第 {i} 条消息，请只回复「收到{i}」。")
    # 由于只保留最近 4 条，模型已经看不到最早的内容了。
    print("[trim]", chat(agent, "我发的第 1 条消息内容是什么？（预期：已被裁掉记不得）"))


def demo_summarize() -> None:
    agent = build_summary_agent()
    # 制造足够长的对话以触发摘要
    for topic in ["我叫阿强", "我是程序员", "我养了只猫叫咪咪", "我喜欢爬山"]:
        chat(agent, f"记住：{topic}。回复「好」。")
    print("[summarize]", chat(agent, "总结一下你记得我的哪些信息？"))


def explain_delete() -> None:
    """策略 3：删除（说明 + 代码片段，不单独跑）。

    用 RemoveMessage(id=消息id) 在 @after_model 里按条删除，典型用于：
    撤回敏感信息、剔除失败的工具调用。注意删完后要保证历史对该 provider 仍合法。
    """
    print(
        "[delete] 用法：在 @after_model 里 return "
        "{'messages': [RemoveMessage(id=某条消息的id)]}；"
        "REMOVE_ALL_MESSAGES 则清空全部。"
    )


if __name__ == "__main__":
    explain_delete()  # 不需要 Key
    if not require_key():
        raise SystemExit(0)
    # demo_trim()
    demo_summarize()

# [llm] 入参={"model": "gemini-2.5-flash", "messages": [{"role": "human", "content": "记住：我叫阿强。回复「好」。"}]}
#   | 返回={"generations": [{"text": "好。", "finish_reason": "STOP"}]} | 耗时=1.85s
# [llm] 入参={"model": "gemini-2.5-flash", "messages": [{"role": "human", "content": "记住：我叫阿强。回复「好」。"}, {"role": "ai", "content": "好。"}, {"role": "human", "content": "记住：我是程序员。回复「好」。"}]}
#   | 返回={"generations": [{"text": "好。", "finish_reason": "STOP"}]} | 耗时=0.90s
# [llm] 入参={"model": "gemini-2.5-flash", "messages": [{"role": "human", "content": "记住：我叫阿强。回复「好」。"}, {"role": "ai", "content": "好。"}, {"role": "human", "content": "记住：我是程序员。回复「好」。"}, {"role": "ai", "content": "好。"}, {"role": "human", "content": "记住：我养了只猫叫咪咪。回复「好」。"}]}
#   | 返回={"generations": [{"text": "好。", "finish_reason": "STOP"}]} | 耗时=0.66s
# [llm] 入参={"model": "gemini-2.5-flash", "messages": [{"role": "human", "content": "<role>\nContext Extraction Assistant\n</role>\n\n<primary_objective>\nYour sole objective in this task is to extract the highest quality/most relevant context from the conversation history below.\n</primary_objective>\n\n<objective_information>\nYou're nearing the total number of input tokens you can accept, so you must extract the highest quality/most relevant pieces of information from your conversation history.\nThis context will then overwrite the conversation history presented below. Because of this, ensure the context you extract is only the most important information to continue working toward your overall goal.\n</objective_information>\n\n<instructions>\nThe conversation history below will be replaced with the context you extract in this step.\nYou want to ensure that you don't repeat any actions you've already completed, so the context you extract from the conversation history should be focused on the most important information to your overall goal.\n\nYou should structure your summary using the following sections. Each section acts as a checklist - you must populate it with relevant information or explicitly state \"None\" if there is nothing to report for that section:\n\n## SESSION INTENT\n\nWhat is the user's primary goal or request? What overall task are you trying to accomplish? This should be concise but complete enough to understand the purpose of the entire session.\n\n## SUMMARY\n\nExtract and record all of the most important context from the conversation history. Include important choices, conclusions, or strategies determined during this conversation. Include the reasoning behind key decisions. Document any rejected options and why they were not pursued.\n\n## ARTIFACTS\n\nWhat artifacts, files, or resources were created, modified, or accessed during this conversation? For file modifications, list specific file paths and briefly describe the changes made to each. This section prevents silent loss of artifact information.\n\n## NEXT STEPS\n\nWhat specific tasks remain to be completed to achieve the session intent? What should you do next?\n\n</instructions>\n\nThe user will message you with the full message history from which you'll extract context to create a replacement. Carefully read through it all and think deeply about what information is most important to your overall goal and should be saved:\n\nWith all of this in mind, please carefully read over the entire conversation history, and extract the most important and relevant context to replace it so that you can free up space in the conversation history.\nRespond ONLY with the extracted context. Do not include any additional information, or text before or after the extracted context.\n\n<messages>\nMessages to summarize:\n<message type=\"human\">记住：我叫阿强。回复「好」。</message>\n<message type=\"ai\">好。</message>\n<message type=\"human\">记住：我是程序员。回复「好」。</message>\n<message type=\"ai\">好。</message>\n<message type=\"human\">记住：我养了只猫叫咪咪。回复「好」。</message>\n</messages>"}]}
#   | 返回={"generations": [{"text": "## SESSION INTENT\n\nThe user's primary goal is for me to remember specific personal details about them for future interactions.\n\n## SUMMARY\n\nThe user has provided the following personal information:\n*   Their name is 阿强 (Aqiang).\n*   They are a 程序员 (programmer).\n*   They have a cat named 咪咪 (Mimi).\n\nNo key decisions, strategies, or rejected options have been discussed.\n\n## ARTIFACTS\n\nNone\n\n## NEXT STEPS\n\nContinue to remember the provided personal information (name, profession, pet's name). The immediate next step based on the conversation history is to acknowledge the last piece of information regarding their cat, Mimi.", "finish_reason": "STOP"}]} | 耗时=3.92s
# [llm] 入参={"model": "gemini-2.5-flash", "messages": [{"role": "human", "content": "Here is a summary of the conversation to date:\n\n## SESSION INTENT\n\nThe user's primary goal is for me to remember specific personal details about them for future interactions.\n\n## SUMMARY\n\nThe user has provided the following personal information:\n*   Their name is 阿强 (Aqiang).\n*   They are a 程序员 (programmer).\n*   They have a cat named 咪咪 (Mimi).\n\nNo key decisions, strategies, or rejected options have been discussed.\n\n## ARTIFACTS\n\nNone\n\n## NEXT STEPS\n\nContinue to remember the provided personal information (name, profession, pet's name). The immediate next step based on the conversation history is to acknowledge the last piece of information regarding their cat, Mimi."}, {"role": "ai", "content": "好。"}, {"role": "human", "content": "记住：我喜欢爬山。回复「好」。"}]}
#   | 返回={"generations": [{"text": "好。", "finish_reason": "STOP"}]} | 耗时=1.50s
# [llm] 入参={"model": "gemini-2.5-flash", "messages": [{"role": "human", "content": "<role>\nContext Extraction Assistant\n</role>\n\n<primary_objective>\nYour sole objective in this task is to extract the highest quality/most relevant context from the conversation history below.\n</primary_objective>\n\n<objective_information>\nYou're nearing the total number of input tokens you can accept, so you must extract the highest quality/most relevant pieces of information from your conversation history.\nThis context will then overwrite the conversation history presented below. Because of this, ensure the context you extract is only the most important information to continue working toward your overall goal.\n</objective_information>\n\n<instructions>\nThe conversation history below will be replaced with the context you extract in this step.\nYou want to ensure that you don't repeat any actions you've already completed, so the context you extract from the conversation history should be focused on the most important information to your overall goal.\n\nYou should structure your summary using the following sections. Each section acts as a checklist - you must populate it with relevant information or explicitly state \"None\" if there is nothing to report for that section:\n\n## SESSION INTENT\n\nWhat is the user's primary goal or request? What overall task are you trying to accomplish? This should be concise but complete enough to understand the purpose of the entire session.\n\n## SUMMARY\n\nExtract and record all of the most important context from the conversation history. Include important choices, conclusions, or strategies determined during this conversation. Include the reasoning behind key decisions. Document any rejected options and why they were not pursued.\n\n## ARTIFACTS\n\nWhat artifacts, files, or resources were created, modified, or accessed during this conversation? For file modifications, list specific file paths and briefly describe the changes made to each. This section prevents silent loss of artifact information.\n\n## NEXT STEPS\n\nWhat specific tasks remain to be completed to achieve the session intent? What should you do next?\n\n</instructions>\n\nThe user will message you with the full message history from which you'll extract context to create a replacement. Carefully read through it all and think deeply about what information is most important to your overall goal and should be saved:\n\nWith all of this in mind, please carefully read over the entire conversation history, and extract the most important and relevant context to replace it so that you can free up space in the conversation history.\nRespond ONLY with the extracted context. Do not include any additional information, or text before or after the extracted context.\n\n<messages>\nMessages to summarize:\n<message type=\"human\">Here is a summary of the conversation to date:\n\n## SESSION INTENT\n\nThe user's primary goal is for me to remember specific personal details about them for future interactions.\n\n## SUMMARY\n\nThe user has provided the following personal information:\n*   Their name is 阿强 (Aqiang).\n*   They are a 程序员 (programmer).\n*   They have a cat named 咪咪 (Mimi).\n\nNo key decisions, strategies, or rejected options have been discussed.\n\n## ARTIFACTS\n\nNone\n\n## NEXT STEPS\n\nContinue to remember the provided personal information (name, profession, pet's name). The immediate next step based on the conversation history is to acknowledge the last piece of information regarding their cat, Mimi.</message>\n<message type=\"ai\">好。</message>\n<message type=\"human\">记住：我喜欢爬山。回复「好」。</message>\n</messages>"}]}
#   | 返回={"generations": [{"text": "## SESSION INTENT\n\nThe user's primary goal is for me to remember specific personal details about them for future interactions.\n\n## SUMMARY\n\nThe user has provided the following personal information:\n*   Their name is 阿强 (Aqiang).\n*   They are a 程序员 (programmer).\n*   They have a cat named 咪咪 (Mimi).\n*   They like mountain climbing (爬山).\n\nNo key decisions, strategies, or rejected options have been discussed.\n\n## ARTIFACTS\n\nNone\n\n## NEXT STEPS\n\nThe immediate next step is to acknowledge the last piece of information provided by the user, specifically that they like mountain climbing, as explicitly requested.", "finish_reason": "STOP"}]} | 耗时=4.01s
# [llm] 入参={"model": "gemini-2.5-flash", "messages": [{"role": "human", "content": "Here is a summary of the conversation to date:\n\n## SESSION INTENT\n\nThe user's primary goal is for me to remember specific personal details about them for future interactions.\n\n## SUMMARY\n\nThe user has provided the following personal information:\n*   Their name is 阿强 (Aqiang).\n*   They are a 程序员 (programmer).\n*   They have a cat named 咪咪 (Mimi).\n*   They like mountain climbing (爬山).\n\nNo key decisions, strategies, or rejected options have been discussed.\n\n## ARTIFACTS\n\nNone\n\n## NEXT STEPS\n\nThe immediate next step is to acknowledge the last piece of information provided by the user, specifically that they like mountain climbing, as explicitly requested."}, {"role": "ai", "content": "好。"}, {"role": "human", "content": "总结一下你记得我的哪些信息？"}]}
#   | 返回={"generations": [{"text": "好的，阿强。我记得你的信息如下：\n\n*   你的名字是 **阿强**。\n*   你是一名 **程序员**。\n*   你有一只猫，名叫 **咪咪**。\n*   你喜欢 **爬山**。", "finish_reason": "STOP"}]} | 耗时=1.54s
# [summarize] 好的，阿强。我记得你的信息如下：
#
# *   你的名字是 **阿强**。
# *   你是一名 **程序员**。
# *   你有一只猫，名叫 **咪咪**。
# *   你喜欢 **爬山**。


# 压缩query
# <角色>
# 上下文提取助手
# </角色>
#
# <主要目标>
# 你在此任务中的唯一目标是从下方的对话历史中提取质量最高/最相关的上下文。
# </主要目标>
#
# <目标信息>
# 你即将达到可接受的输入 Token 总数上限，因此你必须从对话历史中提取质量最高/最相关的信息片段。
# 此上下文随后将覆盖下方展示的对话历史。因此，请确保你提取的上下文仅包含对继续实现整体目标最重要的信息。
# </目标信息>
#
# <指令>
# 下方的对话历史将被你在此步骤中提取的上下文所替换。
# 你需要确保不会重复任何已完成的动作，因此你从对话历史中提取的上下文应聚焦于对整体目标最重要的信息。
#
# 你应该使用以下部分来构建你的摘要。每个部分作为一个检查清单——你必须用相关信息填充它，如果该部分没有可报告的内容，则明确说明“无（None）”：
#
# ## 会话意图 (SESSION INTENT)
#
# 用户的主要目标或请求是什么？你试图完成的整体任务是什么？这应该简明扼要，但足以让人理解整个会话的目的。
#
# ## 摘要 (SUMMARY)
#
# 提取并记录对话历史中所有最重要的上下文。包括在此会话中确定的重要选择、结论或策略。包括关键决策背后的推理。记录任何被拒绝的选项以及未采用它们的原因。
#
# ## 产出物 (ARTIFACTS)
#
# 在此会话期间创建、修改或访问了哪些产出物、文件或资源？对于文件修改，列出具体的文件路径并简要描述对每个文件所做的更改。此部分可防止产出物信息的静默丢失。
#
# ## 下一步 (NEXT STEPS)
#
# 为了实现会话意图，还有哪些具体任务需要完成？接下来应该做什么？
#
# </指令>
#
# 用户将向你发送完整的消息历史，你将从中提取上下文以创建替换内容。请仔细阅读所有内容，并深入思考哪些信息对你的整体目标最重要且应该被保存：
#
# 考虑到以上所有因素，请仔细阅读整个对话历史，并提取最重要且相关的上下文来替换它，以便释放对话历史的空间。
# 仅回复提取的上下文。不要包含任何额外的信息，也不要在提取的上下文之前或之后添加任何文本。
#
# <消息>
# 需要总结的消息：
# <message type="human">记住：我叫阿强。回复「好」。</message>
# <message type="ai">好。</message>
# <message type="human">记住：我是程序员。回复「好」。</message>
# <message type="ai">好。</message>
# <message type="human">记住：我养了只猫叫咪咪。回复「好」。</message>
# </messages>

# 返回值
# ## 会话意图
#
# 用户的主要目标是让我记住他们的一些个人细节，以便在未来的交流中使用。
#
# ## 摘要
#
# 用户提供了以下个人信息：
# * 姓名：阿强（Aqiang）
# * 职业：程序员
# * 宠物猫的名字：咪咪（Mimi）
#
# 尚未讨论任何关键决策、策略或被拒绝的选项。
#
# ## 文档
#
# 无
#
# ## 下一步
#
# 继续记住所提供的个人信息（姓名、职业、宠物名字）。根据对话历史，下一步应确认关于他们的猫咪咪咪的最后一条信息。