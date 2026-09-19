"""关卡 04：多智能体与委派（sub_agents / delegation）

学习目标：
  - 用一个"协调者(coordinator)" + 多个"专家子 Agent"组成层级
  - 理解委派机制：LLM 根据各子 Agent 的 description 决定把任务"转交"给谁
    （ADK 底层是自动生成的 transfer_to_agent 调用）
  - 关键：子 Agent 的 description 要写清楚"我负责什么"，这是路由的依据

对比关卡 05：sub_agents 是"把控制权交出去"；AgentTool 是"叫它干活、结果拿回来自己继续"。

运行：adk run s04_sub_agents   或   adk web 后选择本关卡
"""

import os

from google.adk.agents import Agent

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")


def check_order_status(order_id: str) -> dict:
    """根据订单号查询订单状态。"""
    return {"status": "success", "order_id": order_id, "state": "已发货，预计 3 天内送达"}


def reset_password(email: str) -> dict:
    """给指定邮箱发送重置密码链接。"""
    return {"status": "success", "message": f"重置链接已发送到 {email}"}


# 专家子 Agent 1：售后/订单
order_agent = Agent(
    name="order_agent",
    model=MODEL,
    description="负责订单相关问题：查询订单状态、物流、退换货。",
    instruction="你是订单客服。用 check_order_status 查询订单，回答要具体、有礼貌。",
    tools=[check_order_status],
)

# 专家子 Agent 2：账号/技术
account_agent = Agent(
    name="account_agent",
    model=MODEL,
    description="负责账号相关问题：登录失败、重置密码、账号安全。",
    instruction="你是账号客服。涉及重置密码时用 reset_password 工具。",
    tools=[reset_password],
)

# 协调者：自己不干活，只负责把用户问题路由给合适的专家
root_agent = Agent(
    name="support_coordinator",
    model=MODEL,
    description="客服总入口，负责理解用户意图并转交给合适的专家。",
    instruction=(
        "你是客服调度中心。判断用户问题属于【订单】还是【账号】，"
        "然后把对话转交给对应的子 Agent 处理；无法归类时先追问澄清。"
        "不要自己编造订单或账号结果。"
    ),
    # 声明子 Agent，ADK 会允许在它们之间委派
    sub_agents=[order_agent, account_agent],
)
