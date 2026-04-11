from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any, Dict, List, Optional

from app.ingest.models import Chunk

logger = logging.getLogger(__name__)


class AnswerGenerator:
    """
    基于 LLM 的答案生成器。

    设计要点：
    1. System prompt 强调"只基于上下文回答"，减少幻觉
    2. 每个上下文附带元数据（页码、章节），方便引用溯源
    3. 金融数据要求精确引用原文数值，不做近似
    4. 如果上下文不足以回答，明确告知用户
    """

    SYSTEM_PROMPT = """你是一个专业的金融投研分析助手。请严格基于提供的文档上下文回答用户问题。

回答要求：
1. 只基于提供的【参考文档】回答，不要编造信息
2. 引用具体出处，格式为 [页X, 章节名]
3. 金融数据（百分比、金额、增长率等）必须精确引用原文数值
4. 如果参考文档不足以完全回答问题，请明确指出哪些方面缺乏信息
5. 回答结构清晰，必要时使用列表或分点陈述
6. 最后给出一段简要总结"""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(
        self,
        query: str,
        chunks: List[Chunk],
    ) -> str:
        """
        基于检索到的 chunk 生成回答。

        参数:
            query: 用户原始问题
            chunks: 检索并重排序后的 Chunk 列表
        返回:
            LLM 生成的回答文本
        """
        if not self.api_key:
            return self._generate_fallback(query, chunks)

        try:
            return self._call_llm(query, chunks)
        except Exception as e:
            logger.warning("LLM 生成失败: %s，使用 fallback", e)
            return self._generate_fallback(query, chunks)

    def _build_context(self, chunks: List[Chunk]) -> str:
        """将 Chunk 列表格式化为带元数据的上下文文本。"""
        parts: List[str] = []
        for i, chunk in enumerate(chunks, 1):
            section = " > ".join(chunk.section_path) if chunk.section_path else "未知章节"
            pages = ", ".join(str(p) for p in chunk.page_span)
            parts.append(
                f"【参考文档 {i}】\n"
                f"  来源: 页{pages}, {section}\n"
                f"  内容: {chunk.content}\n"
            )
        return "\n".join(parts)

    def _call_llm(self, query: str, chunks: List[Chunk]) -> str:
        """调用 LLM API 生成回答。"""
        context = self._build_context(chunks)
        user_message = f"参考文档：\n{context}\n\n用户问题：{query}"

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        answer = result["choices"][0]["message"]["content"].strip()
        logger.info("答案生成完成，长度: %d 字符", len(answer))
        return answer

    def _generate_fallback(self, query: str, chunks: List[Chunk]) -> str:
        """
        无 LLM 时的 fallback：直接拼接检索结果。

        这不是真正的"答案生成"，但能让用户看到检索到了什么内容，
        方便调试检索质量。
        """
        lines = [
            f"📋 查询: {query}",
            f"📄 找到 {len(chunks)} 个相关文档片段:",
            "",
        ]
        for i, chunk in enumerate(chunks, 1):
            section = " > ".join(chunk.section_path) if chunk.section_path else "未知章节"
            pages = ", ".join(str(p) for p in chunk.page_span)
            lines.append(f"--- 片段 {i} [页{pages}, {section}] ---")
            lines.append(chunk.content)
            lines.append("")

        lines.append("⚠️ 未配置 OPENAI_API_KEY，以上为原始检索结果。")
        lines.append("   配置 API key 后可获得 LLM 生成的结构化回答。")
        return "\n".join(lines)
