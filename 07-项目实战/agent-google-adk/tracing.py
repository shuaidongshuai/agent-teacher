"""全局追踪 Plugin：在【任意】Agent 执行前后打印，一处生效、看清调用顺序。

为什么用 Plugin 而不是给每个关卡逐个加 callback？
  - callback 是"单个 Agent 级"的钩子（见关卡 10 / adv_01）；
  - Plugin 是"全局级"钩子：定义一次，对项目里所有 Agent 都生效，
    不用去十几个关卡文件里挨个改。这是 callback 的"全局版"。

两种启用方式：
  1) adk web：   adk web --extra_plugins tracing.TracePlugin
  2) 编程式：    Runner(..., plugins=[TracePlugin()])   （run_demo.py 已内置）

注意：adk run 目前不支持 --extra_plugins，想看调用顺序请用 adk web 或 run_demo.py。
"""

from typing import Optional

from google.adk.agents import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.plugins import BasePlugin
from google.genai import types


class TracePlugin(BasePlugin):
    """打印每个 Agent 的进入/离开，用来观察多智能体/工作流的执行顺序。"""

    def __init__(self, name: str = "trace"):
        super().__init__(name=name)

    async def before_agent_callback(
        self, *, agent: BaseAgent, callback_context: CallbackContext
    ) -> Optional[types.Content]:
        print(f"▶ 进入 Agent: {agent.name}")
        return None  # 返回 None = 不拦截，正常执行

    async def after_agent_callback(
        self, *, agent: BaseAgent, callback_context: CallbackContext
    ) -> Optional[types.Content]:
        print(f"✔ 离开 Agent: {agent.name}")
        return None
