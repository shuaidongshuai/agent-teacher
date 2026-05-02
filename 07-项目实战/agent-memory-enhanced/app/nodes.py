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
    """创建 LangGraph 节点。"""

    def load_memory(state: MemoryState) -> Dict[str, Any]:
        user_input = state.get("current_input", "")
        log = list(state.get("execution_log", []))

        memories = long_term.recall(user_input, top_k=5)
        memory_texts = [memory.content for memory in memories]
        log.append(f"[load_memory] 检索到 {len(memories)} 条相关记忆")

        return {
            "relevant_memories": memory_texts,
            "conversation_summary": short_term.summary,
            "working_memory": working.to_dict(),
            "execution_log": log,
        }

    def chat(state: MemoryState) -> Dict[str, Any]:
        user_input = state.get("current_input", "")
        relevant_memories = state.get("relevant_memories", [])
        summary = state.get("conversation_summary", "")
        working_mem = state.get("working_memory", {})
        log = list(state.get("execution_log", []))
        call_count = state.get("llm_call_count", 0)

        long_term_text = (
            "\n".join(f"- {memory}" for memory in relevant_memories)
            if relevant_memories
            else "（无相关记忆）"
        )

        if working_mem:
            temp_working = WorkingMemory()
            temp_working.update(working_mem)
            working_text = temp_working.to_text()
        else:
            working_text = "（无）"

        system = SYSTEM_PROMPT.format(
            long_term_memories=long_term_text,
            conversation_summary=summary or "（无）",
            working_memory=working_text,
        )

        messages = [{"role": "system", "content": system}]
        for message in short_term.messages:
            messages.append({"role": message["role"], "content": message["content"]})
        messages.append({"role": "user", "content": user_input})

        response = llm.generate(messages, temperature=0.7, max_tokens=2048)
        call_count += 1
        log.append(f"[chat] 生成回复（{len(response)} 字符）")

        return {
            "assistant_response": response,
            "llm_call_count": call_count,
            "execution_log": log,
        }

    def extract_and_store(state: MemoryState) -> Dict[str, Any]:
        user_input = state.get("current_input", "")
        response = state.get("assistant_response", "")
        log = list(state.get("execution_log", []))
        call_count = state.get("llm_call_count", 0)

        short_term.add_message("user", user_input)
        short_term.add_message("assistant", response)

        msg_text = f"用户: {user_input}\n助手: {response}"
        existing_memories = "\n".join(
            f"- [{entry.category}] {entry.content}" for entry in long_term.entries[-20:]
        ) or "（无）"
        prompt = EXTRACT_MEMORIES_PROMPT.format(
            existing_memories=existing_memories,
            messages=msg_text,
        )

        try:
            result = llm.generate_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            call_count += 1

            memories = result.get("memories", [])
            stored_count = 0
            skipped_count = 0

            for memory in memories:
                content = memory.get("content", "").strip()
                category = memory.get("category", "other").strip() or "other"
                if not content:
                    continue
                if long_term.store(content, category):
                    stored_count += 1
                else:
                    skipped_count += 1

            log.append(
                f"[extract_and_store] 提取 {len(memories)} 条，新增 {stored_count} 条，跳过重复 {skipped_count} 条"
            )

        except Exception as exc:
            logger.warning("记忆提取失败: %s", exc)
            log.append(f"[extract_and_store] 提取失败: {exc}")

        return {
            "llm_call_count": call_count,
            "execution_log": log,
        }

    def compress_if_needed(state: MemoryState) -> Dict[str, Any]:
        log = list(state.get("execution_log", []))
        call_count = state.get("llm_call_count", 0)

        if short_term.needs_compression():
            short_term.compress()
            call_count += 1
            log.append(
                f"[compress] 已压缩短期记忆，当前摘要 {len(short_term.summary)} 字符"
            )
        else:
            log.append(f"[compress] 无需压缩（{len(short_term.messages)} 条消息）")

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
            log.append(
                f"[compress] 工作记忆已更新：goal={working.current_goal} | facts={len(working.key_facts)} | pending={len(working.pending_questions)}"
            )
        except Exception as exc:
            logger.warning("工作记忆更新失败: %s", exc)
            log.append(f"[compress] 工作记忆更新失败: {exc}")

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
