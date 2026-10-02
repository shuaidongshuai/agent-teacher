"""进阶 06：评测闭环（adk eval + 评测集 + CI 回归闸门）

学习目标：
  - 读懂评测集(evalset)的结构：每个用例的输入、期望的【工具调用轨迹】、期望回复
  - 用 adk eval 跑评测，理解两类指标：
      tool_trajectory_avg_score —— 该调的工具有没有按预期调（不看文字）
      response_match_score      —— 回复和参考答案的字面接近度（ROUGE，中文偏严）
  - 把评测做成 CI 回归闸门：低于阈值就非零退出（见 ci_gate.py）

配套文件：
  - adv_06_eval.evalset.json  评测集（3 个用例，含 tool_uses 轨迹断言）
  - test_config.json          指标与阈值（adk eval 会自动读同目录这个文件）
  - ci_gate.py                编程式评测，达不到阈值就拦截

运行与日常用法（大白话）：
  1) 开发时手动看成绩单：
       adk eval adv_06_eval adv_06_eval/adv_06_eval.evalset.json
     → 把评测集里的问题真的问一遍 agent，按 test_config 打分，打印每条 PASS/FAIL 给你看。
       改完 prompt/工具后手动跑，确认没把原来对的搞坏。
  2) CI 里当回归闸门：
       python adv_06_eval/ci_gate.py
     → 同样跑评测，但只给红绿灯：过了退出码 0、没过退出码 1，让流水线拦住变坏的改动。
  （两者底层都会真跑一遍 agent，需要模型凭证；Vertex 模式记得开代理。）

test_config.json 字段说明（注意：JSON 不支持注释，字段解释只能写在这里）：
  criteria —— "指标 → 及格线"清单；指标名后的数字是【阈值/及格线】，不是权重。
              每条用例会算出一个 0~1 的实际分，实际分 ≥ 及格线 才判 PASS。
    - tool_trajectory_avg_score: 1.0
        比"该调的工具调没调对"（看行为、不看文字）；1.0 = 要求工具调用与期望完全一致。
    - response_match_score: 0.3
        比"回复与参考答案的字面接近度"（ROUGE 词重叠）；中文偏严，阈值别设高。
        想按"语义对不对"评，就换成 final_response_match_v2（用裁判模型，更准但更慢更贵）。

日常评测心法：把评测集当成 agent 的"单元测试"——
  修过的 bad case 就补一条防回归；改东西前后先 adk eval 看报告（FAIL 时看是轨迹错还是回复差）；
  再把 ci_gate.py 挂进 CI 自动卡 PR。别靠"我觉得更好"，让评测集替你把关。
"""

import os

from google.adk.agents import Agent

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")


def get_weather(city: str) -> dict:
    """查询指定城市当前的天气。

    Args:
        city: 城市名，如 "北京"。
    """
    fake = {"北京": "晴，18℃", "上海": "多云，22℃", "深圳": "阵雨，27℃"}
    if city in fake:
        return {"status": "success", "report": f"{city}当前天气：{fake[city]}"}
    return {"status": "error", "error_message": f"查不到「{city}」的天气。"}


def get_current_time(city: str) -> dict:
    """查询指定城市的当前时间（演示用，返回固定文案）。

    Args:
        city: 城市名，如 "上海"。
    """
    return {"status": "success", "report": f"{city}现在是北京时间（东八区）。"}


root_agent = Agent(
    name="eval_demo_agent",
    model=MODEL,
    description="能查天气和时间的助手，用于演示评测。",
    instruction=(
        "你是生活助手。问天气就调用 get_weather，问时间就调用 get_current_time；"
        "拿到结果后用一句话友好地转述，不要编造数据。"
    ),
    tools=[get_weather, get_current_time],
)
