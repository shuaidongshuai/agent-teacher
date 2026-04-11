from __future__ import annotations

import logging
from typing import Any, Callable, Dict

from .llm_client import LLMClient
from .memory.long_term import LongTermMemory
from .memory.short_term import ShortTermMemory
from .memory.working import WorkingMemory
from .prompts import (
    EXTRACT_MEMORIES_PROMPT,
    SYSTEM_PROMPT,
    UPDATE_WORKING_MEMORY_PROMPT,
)
from .state import MemoryState

logger = logging.getLogger(__name__)


def make_nodes(
    llm: LLMClient,
    short_term: ShortTermMemory,
    long_term: LongTermMemory,
    working: WorkingMemory,
) -> Dict[str, Callable[[MemoryState], Dict[str, Any]]]:
    """
    工厂函数：创建 LangGraph 节点。

    通过闭包注入依赖，保持 state 干净。
    """

    def load_memory(state: MemoryState) -> Dict[str, Any]:
        """从长期记忆中检索与当前输入相关的记忆。"""
        user_input = state.get("current_input", "")
        log = list(state.get("execution_log", []))

        # 语义检索
        memories = long_term.recall(user_input, top_k=5)
        memory_texts = [m.content for m in memories]

        log.append(f"[load_memory] 检索到 {len(memories)} 条相关记忆")

        return {
            "relevant_memories": memory_texts,
            "conversation_summary": short_term.summary,
            "working_memory": working.to_dict(),
            "execution_log": log,
        }

    def chat(state: MemoryState) -> Dict[str, Any]:
        """LLM 对话节点。"""
        user_input = state.get("current_input", "")
        relevant_memories = state.get("relevant_memories", [])
        summary = state.get("conversation_summary", "")
        working_mem = state.get("working_memory", {})
        log = list(state.get("execution_log", []))
        call_count = state.get("llm_call_count", 0)

        # 构建 system prompt
        long_term_text = "\n".join(
            f"- {m}" for m in relevant_memories
        ) if relevant_memories else "（无相关记忆）"

        working_text = ""
        if working_mem:
            w = WorkingMemory()
            w.update(working_mem)
            working_text = w.to_text()
        else:
            working_text = "（无）"

        system = SYSTEM_PROMPT.format(
            long_term_memories=long_term_text,
            conversation_summary=summary or "（无）",
            working_memory=working_text,
        )

        # 构建消息列表（最近消息 + 当前输入）
        messages = [{"role": "system", "content": system}]
        for m in short_term.messages:
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": user_input})

        # 调用 LLM
        response = llm.generate(messages, temperature=0.7, max_tokens=2048)
        call_count += 1

        log.append(f"[chat] 生成回复 ({len(response)} 字符)")

        return {
            "assistant_response": response,
            "llm_call_count": call_count,
            "execution_log": log,
        }

    def extract_and_store(state: MemoryState) -> Dict[str, Any]:
        """从本轮对话中提取值得记忆的信息，存入长期记忆。"""
        user_input = state.get("current_input", "")
        response = state.get("assistant_response", "")
        log = list(state.get("execution_log", []))
        call_count = state.get("llm_call_count", 0)

        # 记录到短期记忆
        short_term.add_message("user", user_input)
        short_term.add_message("assistant", response)

        # 提取记忆
        msg_text = f"用户: {user_input}\n助手: {response}"
        prompt = EXTRACT_MEMORIES_PROMPT.format(messages=msg_text)

        try:
            result = llm.generate_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            call_count += 1

            memories = result.get("memories", [])
            for mem in memories:
                content = mem.get("content", "")
                category = mem.get("category", "other")
                if content:
                    long_term.store(content, category)

            log.append(f"[extract_and_store] 提取 {len(memories)} 条新记忆")

        except Exception as e:
            logger.warning("记忆提取失败: %s", e)
            log.append(f"[extract_and_store] 提取失败: {e}")

        return {
            "llm_call_count": call_count,
            "execution_log": log,
        }

    def compress_if_needed(state: MemoryState) -> Dict[str, Any]:
        """如果短期记忆消息过多，触发压缩。"""
        log = list(state.get("execution_log", []))
        call_count = state.get("llm_call_count", 0)

        if short_term.needs_compression():
            short_term.compress()
            call_count += 1
            log.append(
                f"[compress] 已压缩短期记忆，当前摘要 {len(short_term.summary)} 字符"
            )
        else:
            log.append(
                f"[compress] 无需压缩 ({len(short_term.messages)} 条消息)"
            )

        # 更新工作记忆
        user_input = state.get("current_input", "")
        response = state.get("assistant_response", "")

        prompt = UPDATE_WORKING_MEMORY_PROMPT.format(
            current_working_memory=working.to_text(),
            user_message=user_input,
            assistant_message=response,
        )

        try:
            result = llm.generate_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            call_count += 1
            working.update(result)
            log.append("[compress] 工作记忆已更新")
        except Exception as e:
            logger.warning("工作记忆更新失败: %s", e)

        return {
            "conversation_summary": short_term.summary,
            "working_memory": working.to_dict(),
            "llm_call_count": call_count,
            "execution_log": log,
        }

    return {
        "load_memory": load_memory,
        "chat": chat,
        "extract_and_store": extract_and_store,
        "compress_if_needed": compress_if_needed,
    }
