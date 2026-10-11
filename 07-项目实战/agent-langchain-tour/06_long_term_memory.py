"""
06_long_term_memory.py —— 长期记忆 / 跨会话记忆（LangChain v1）

本节目标：让 Agent「跨会话、跨 thread」记住用户信息（偏好、档案等）。

核心机制：Store（存储）。
- 短期记忆（05 节）是单个 thread 内的历史；换个 thread 就没了。
- 长期记忆用 Store，把数据以 JSON 文档存起来，按 namespace(文件夹) + key(文件名) 组织，
  任何会话、任何时候都能取回。
- 把 store 传给 create_agent，工具内部通过 runtime.store 读写。
- 配 IndexConfig(embed=...) 后，store.search(query=...) 支持语义检索。

对应 README「长期记忆」一节。

运行：python 06_long_term_memory.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from common import get_model, require_key
from langchain.agents import create_agent
from langchain.tools import ToolRuntime, tool
from langgraph.store.base import IndexConfig
from langgraph.store.memory import InMemoryStore


@dataclass
class Context:
    """运行时上下文：带上 user_id，让工具知道当前是谁，并据此做 Store 隔离。

    注意：必须定义在模块顶层。因为 `from __future__ import annotations` 把工具
    函数的类型注解变成了字符串，`@tool` 解析 `ToolRuntime[Context]` 时会用
    get_type_hints() 在**模块全局**里查找 Context；若定义在函数内部则找不到会报
    NameError。
    """

    user_id: str



def demo_store_crud() -> None:
    """直接用 Store 的三个核心操作：put / get / search（不经过模型）。"""
    store = InMemoryStore()
    namespace = ("user_123", "profile")  # 命名空间常带上 user_id 做隔离
    store.put(namespace, "basic", {"name": "小明", "city": "北京"})
    store.put(namespace, "pref", {"language": "中文", "tone": "简洁"})

    print("[get]   ", store.get(namespace, "basic").value)
    # filter 按内容过滤；返回项的数据在 .value 里。
    hits = store.search(namespace, filter={"language": "中文"})
    # hits = store.search(namespace, filter={"name": "小明"})
    print("[search]", [(h.key, h.value) for h in hits])


def demo_semantic_search() -> None:
    """语义检索：配 IndexConfig 后，search(query=...) 按向量相似度排序。

    这里用一个假的 embed（演示用）；真实场景替换成 OpenAIEmbeddings 等。
    """

    # 换成了 [是否有海, 是否有山] 这样的向量格式
    def embed(texts: Sequence[str]) -> list[list[float]]:
        # 真实请替换为 embedding 模型；这里按关键词给个二维向量占位。
        return [[float("海" in t), float("山" in t)] for t in texts]

    store = InMemoryStore(index=IndexConfig(embed=embed, dims=2))
    ns = ("user_123", "memories")
    store.put(ns, "m1", {"text": "我喜欢去海边度假"})
    store.put(ns, "m2", {"text": "我周末常去爬山"})

    results = store.search(ns, query="沙滩和大海", limit=1)
    print("[semantic]1", [r.value["text"] for r in results])

    results = store.search(ns, query="黄山", limit=1)
    print("[semantic]2", [r.value["text"] for r in results])


def demo_agent_with_memory_tools() -> None:
    """把 Store 接到 Agent：用「读/写记忆工具」实现跨会话记住用户。"""

    @tool
    def save_user_info(info: str, runtime: ToolRuntime[Context]) -> str:
        """保存关于当前用户的一条长期信息。"""
        assert runtime.store is not None
        user_id = runtime.context.user_id
        runtime.store.put(("users", user_id), "info", {"info": info})
        return "已记住。"

    @tool
    def get_user_info(runtime: ToolRuntime[Context]) -> str:
        """读取当前用户的长期信息。"""
        assert runtime.store is not None
        user_id = runtime.context.user_id
        item = runtime.store.get(("users", user_id), "info")
        return item.value["info"] if item else "暂无记录"

    store = InMemoryStore()
    agent = create_agent(
        model=get_model(),
        tools=[save_user_info, get_user_info],
        system_prompt="需要记住或回忆用户信息时，调用对应工具。",
        store=store,
        context_schema=Context,
    )

    # 第 1 个会话：写入记忆
    agent.invoke(
        {"messages": [{"role": "user", "content": "记住：我对花生过敏。"}]},
        context=Context(user_id="u1"),
    )
    # 第 2 个「全新」会话（没有共享消息历史），仍能靠 Store 回忆起来
    out = agent.invoke(
        {"messages": [{"role": "user", "content": "我有什么饮食禁忌？"}]},
        context=Context(user_id="u1"),
    )
    print("[agent]", out["messages"][-1].text)


if __name__ == "__main__":
    # demo_store_crud()  # 不需要 Key
    # demo_semantic_search()  # 不需要 Key
    if not require_key():
        raise SystemExit(0)
    demo_agent_with_memory_tools()
