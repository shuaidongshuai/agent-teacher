"""进阶 04：用 GEPA 自动优化提示词（adk optimize）

学习目标：
  - 认识 ADK 的提示词自动优化：给一批"输入→期望输出"的评测样本，
    GEPA 优化器会自动改写 root_agent 的 instruction，让它在评测上得分更高
  - 理解它和人工调 prompt 的区别：把"调提示词"变成一个可度量、可迭代的优化过程

本关刻意给一个【很含糊】的 instruction（见下），留出被优化的空间。

配套文件：
  - sampler_config.json          采样器配置（评测指标 + 用哪个评测集训练）
  - adv_04_train.evalset.json     训练用评测集（问题 + 期望答案）

运行（会真实调用模型、做多轮优化，耗费配额，属实验特性）：
  cd agent-google-adk
  adk optimize adv_04_optimize/__init__.py \
      --sampler_config_file_path adv_04_optimize/sampler_config.json \
      --print_detailed_results

优化完成后，对比它给出的新 instruction 和下面这版旧的，体会差别。
"""

import os

from google.adk.agents import LlmAgent

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")

root_agent = LlmAgent(
    name="faq_agent",
    model=MODEL,
    description="回答关于 ADK 的常见问题。",
    # 故意写得很含糊：没有规定语言、长度、风格 —— 交给 GEPA 去优化
    instruction="回答用户的问题。",
)
