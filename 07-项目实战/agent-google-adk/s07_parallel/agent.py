"""关卡 07：ParallelAgent 并行工作流

学习目标：
  - 用 ParallelAgent 让多个互不依赖的子任务"同时跑"，缩短总耗时
  - 每个并行分支写自己独立的 output_key，避免互相覆盖
  - 常见组合：ParallelAgent(并行收集) 后面接一个"汇总 Agent"
    → 所以外层再套一个 SequentialAgent：先并行、后汇总

运行：adk run s07_parallel   或   adk web 后选择本关卡
（给一个话题，例如："电动汽车"，它会从三个角度并行分析再汇总）
"""

import os

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")

# 三个并行分支：从不同角度分析同一个话题，各写各的 state key
pros_agent = LlmAgent(
    name="pros_agent",
    model=MODEL,
    description="分析话题的优点/好处。",
    instruction="针对用户给的话题，列出 3 条主要优点，每条一句话。",
    output_key="pros",
)

cons_agent = LlmAgent(
    name="cons_agent",
    model=MODEL,
    description="分析话题的缺点/风险。",
    instruction="针对用户给的话题，列出 3 条主要缺点或风险，每条一句话。",
    output_key="cons",
)

trend_agent = LlmAgent(
    name="trend_agent",
    model=MODEL,
    description="分析话题的发展趋势。",
    instruction="针对用户给的话题，用 2~3 句话总结它的发展趋势。",
    output_key="trend",
)

# 并行块：三个分支同时执行
parallel_block = ParallelAgent(
    name="analyze_in_parallel",
    description="从优点、缺点、趋势三个角度并行分析。",
    sub_agents=[pros_agent, cons_agent, trend_agent],
)

# 汇总 Agent：把三份并行结果拼成一份结构化报告
synthesizer = LlmAgent(
    name="synthesizer",
    model=MODEL,
    description="整合三个角度的分析，输出一份小结。",
    instruction=(
        "把下面三部分整合成一份条理清晰的中文小结（分「优点/缺点/趋势/结论」）：\n"
        "优点：\n{pros}\n\n缺点：\n{cons}\n\n趋势：\n{trend}"
    ),
    output_key="summary",
)

# 外层顺序：先并行分析，再汇总
root_agent = SequentialAgent(
    name="parallel_analyzer",
    description="三个角度并行分析一个话题，然后汇总成报告。",
    sub_agents=[parallel_block, synthesizer],
)
