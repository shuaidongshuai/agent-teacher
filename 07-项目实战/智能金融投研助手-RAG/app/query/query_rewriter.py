from __future__ import annotations

import json
import logging
import urllib.request
from typing import List

logger = logging.getLogger(__name__)


class QueryRewriter:
    """
    基于 LLM 的查询改写器。

    为什么需要查询改写？（详见 03-RAG/5.RAG查询理解.md）
    用户原始查询往往不适合直接检索：
    - 口语化表达（"去年赚了多少钱" → "2024年营业收入/净利润"）
    - 隐含条件（"毛利率怎么样" → 需要补全时间范围和对比维度）
    - 单一角度（一个问题可能需要从多个角度检索）

    改写策略：
    1. 展开简称和别名
    2. 补全金融领域隐含实体
    3. 生成 1-3 个不同角度的检索 query

    无 API key 时直接返回原始 query（bypass 模式），
    确保检索阶段即使没有 LLM 也能运行。
    """

    REWRITE_PROMPT = """你是一个金融投研分析助手的查询改写模块。
你的任务是将用户的原始问题改写为更适合检索金融年报文档的 query。

改写要求：
1. 展开口语化表达为正式金融术语
2. 补全隐含的时间范围、对比维度等条件
3. 生成 1-3 个不同角度的检索 query，覆盖问题的不同侧面
4. 每个 query 应该简洁、具体，适合在金融年报中检索

请以 JSON 数组格式返回改写后的 query 列表，例如：
["改写query1", "改写query2", "改写query3"]

只返回 JSON 数组，不要其他内容。"""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def rewrite(self, query: str) -> List[str]:
        """
        改写用户查询。

        返回:
            改写后的 query 列表（1-3 个），如果 LLM 不可用则返回 [原始query]
        """
        if not self.api_key:
            logger.info("未配置 API key，跳过查询改写，使用原始 query")
            return [query]

        try:
            return self._call_llm(query)
        except Exception as e:
            logger.warning("查询改写失败: %s，使用原始 query", e)
            return [query]

    def _call_llm(self, query: str) -> List[str]:
        """调用 LLM API 进行查询改写。"""
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": self.REWRITE_PROMPT},
                {"role": "user", "content": f"用户问题：{query}"},
            ],
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        content = result["choices"][0]["message"]["content"].strip()

        # 解析 JSON 数组
        queries = json.loads(content)
        if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
            logger.info("查询改写: '%s' -> %s", query, queries)
            return queries

        return [query]
