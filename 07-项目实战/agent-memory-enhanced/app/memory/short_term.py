from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ShortTermMemory:
    """
    短期记忆：LLM 摘要压缩。

    维护当前会话的消息列表。当消息数超过阈值时，
    调用 LLM 将旧消息压缩为摘要，只保留最近 N 条完整消息。
    """

    def __init__(
        self,
        llm_client: Any,
        max_messages: int = 20,
        keep_recent: int = 6,
    ) -> None:
        self.llm = llm_client
        self.max_messages = max_messages
        self.keep_recent = keep_recent
        self.messages: List[Dict[str, str]] = []
        self.summary: str = ""

    def add_message(self, role: str, content: str) -> None:
        """添加一条消息。"""
        self.messages.append({"role": role, "content": content})

    def needs_compression(self) -> bool:
        """判断是否需要压缩。"""
        return len(self.messages) > self.max_messages

    def compress(self) -> str:
        """
        压缩旧消息为摘要。

        保留最近 keep_recent 条消息，将之前的压缩为摘要。
        """
        if len(self.messages) <= self.keep_recent:
            return self.summary

        # 需要压缩的消息
        to_compress = self.messages[: -self.keep_recent]
        # 保留的消息
        self.messages = self.messages[-self.keep_recent:]

        # 格式化待压缩的消息
        msg_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in to_compress
        )

        from .prompts import COMPRESS_PROMPT

        prompt = COMPRESS_PROMPT.format(
            previous_summary=self.summary or "（无）",
            messages=msg_text,
        )

        try:
            self.summary = self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=512,
            )
            logger.info(
                "短期记忆已压缩: %d 条消息 → 摘要 (%d 字符)",
                len(to_compress),
                len(self.summary),
            )
        except Exception as e:
            logger.warning("压缩失败: %s", e)
            # 压缩失败时，用简单拼接作为回退
            if to_compress:
                fallback = "; ".join(
                    m["content"][:50] for m in to_compress[-5:]
                )
                self.summary = f"{self.summary} ... {fallback}"

        return self.summary

    def get_context(self) -> Dict[str, Any]:
        """获取当前短期记忆的上下文。"""
        return {
            "summary": self.summary,
            "recent_messages": list(self.messages),
            "total_messages_seen": len(self.messages),
        }
