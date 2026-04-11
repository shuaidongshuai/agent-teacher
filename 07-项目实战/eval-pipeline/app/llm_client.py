from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class LLMClient:
    """
    OpenAI 兼容 API 客户端。

    使用 urllib.request 直接调用，不依赖 openai SDK。
    与项目中其他 Agent 项目保持一致的实现方式。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0,
        max_tokens: int = 2048,
    ) -> str:
        """生成文本回复。"""
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        logger.debug("LLM 请求: model=%s, messages=%d 条", self.model, len(messages))

        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        self._call_count += 1
        content = result["choices"][0]["message"]["content"].strip()
        logger.debug("LLM 响应 (%d 字符): %s...", len(content), content[:100])
        return content

    def generate_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0,
    ) -> Dict[str, Any]:
        """生成 JSON 格式回复，自动解析。"""
        content = self.generate(messages, temperature=temperature)

        # 尝试提取 JSON（处理 markdown code block 包裹的情况）
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        return json.loads(content)
