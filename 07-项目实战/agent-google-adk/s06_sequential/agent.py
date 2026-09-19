"""关卡 06：SequentialAgent 顺序工作流 + 用 state 传数据

学习目标：
  - 用 SequentialAgent 把多个步骤按固定顺序串起来（确定性流程）
  - 用 output_key 把某一步的输出写进"会话状态 state"
  - 用 instruction 里的 {占位符} 把上一步的 state 读进下一步

思路：这类"工作流 Agent"负责编排流程本身不调用 LLM；真正干活的是里面的 LlmAgent。

运行：adk run s06_sequential   或   adk web 后选择本关卡
（直接给它一个主题，例如："写一段关于'及时复盘'的短文"）
"""

import os

from google.adk.agents import LlmAgent, SequentialAgent

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")

# 第 1 步：把用户主题拆成 3~5 个要点，结果存入 state["key_points"]
outliner = LlmAgent(
    name="outliner",
    model=MODEL,
    description="把主题拆解成写作要点。",
    instruction="根据用户给的主题，列出 3~5 个精炼的写作要点，每行一个，不要展开。",
    output_key="key_points",  # 输出写进 state
)

# 第 2 步：读 state["key_points"]，写成草稿，结果存入 state["draft"]
drafter = LlmAgent(
    name="drafter",
    model=MODEL,
    description="根据要点写初稿。",
    instruction=(
        "根据下面的要点写一段 150 字左右的中文短文，逻辑连贯：\n"
        "----\n{key_points}\n----"  # {} 会被 state 里的值替换
    ),
    output_key="draft",
)

# 第 3 步：读 state["draft"]，润色，结果存入 state["final_text"]
polisher = LlmAgent(
    name="polisher",
    model=MODEL,
    description="润色初稿，提升可读性。",
    instruction="把下面这段草稿润色得更通顺、有节奏，保持原意：\n----\n{draft}\n----",
    output_key="final_text",
)

# 顺序编排：outliner -> drafter -> polisher
root_agent = SequentialAgent(
    name="writing_pipeline",
    description="拆要点 → 写初稿 → 润色，三步顺序完成一篇短文。",
    sub_agents=[outliner, drafter, polisher],
)
