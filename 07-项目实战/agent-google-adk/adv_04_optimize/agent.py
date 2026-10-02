"""进阶 04：用 GEPA 自动优化提示词（adk optimize）

学习目标：
  - 认识 ADK 的提示词自动优化：给一批"输入→期望输出"的评测样本，
    GEPA 优化器会自动改写 root_agent 的 instruction，让它在评测上得分更高
  - 理解它和人工调 prompt 的区别：把"调提示词"变成一个可度量、可迭代的优化过程

本关刻意给一个【很含糊】的 instruction（见下），留出被优化的空间。

配套文件：
  - sampler_config.json          采样器配置（评测指标 + 用哪个评测集训练）
  - optimizer_config.json        GEPA 优化器配置（轮数上限 + run_dir 存进化日志）
  - adv_04_train.evalset.json     训练用评测集（问题 + 期望答案）

运行（会真实调用模型、做多轮优化，耗费配额，属实验特性）：
  cd agent-google-adk
  # 注意：AGENT 参数传的是 agent 目录 adv_04_optimize，不是 __init__.py 文件
  adk optimize adv_04_optimize \
      --sampler_config_file_path adv_04_optimize/sampler_config.json \
      --optimizer_config_file_path adv_04_optimize/optimizer_config.json \
      --print_detailed_results

想看进化过程有三层信息：
  1) 本文件给 faq_agent 挂了 before/after_model_callback，会【每次调用】打印
     "本轮 instruction / 输入 / 返回"——直接看到每次训练的入参和返回值；
  2) --print_detailed_results 打印 GEPA 的候选得分等汇总；
  3) optimizer_config.json 里的 run_dir=adv_04_optimize/gepa_runs 会落盘完整的
     候选 instruction 与评分演进，跑完可进去翻看。
  （还想更详细可加 --log_level debug）

优化完成后，对比它给出的新 instruction 和下面这版旧的，体会差别。

原理、何时用、相比手动调 prompt 的优势、断点续跑与停止方式，详见本目录 README.md。
"""

import os
from typing import Optional

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")

# 记录第几次调用模型：GEPA 每试一版候选 instruction，就会用它把评测集跑一遍
_calls = {"n": 0}


def _instruction_text(system_instruction) -> str:
    """从 llm_request.config.system_instruction 取文本（可能是 str / Content / list）。"""
    si = system_instruction
    if not si:
        return ""
    if isinstance(si, str):
        return si
    parts = getattr(si, "parts", None) or (si if isinstance(si, list) else [])
    texts = [getattr(p, "text", "") or "" for p in parts]
    return "".join(texts) or str(si)


def show_input(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """每次调用模型【前】打印：这一轮用的 instruction + 输入问题。"""
    _calls["n"] += 1
    cfg = llm_request.config
    instr = _instruction_text(cfg.system_instruction if cfg else None)
    user_msg = ""
    for content in reversed(llm_request.contents or []):
        if content.role == "user" and content.parts:
            user_msg = "".join(p.text or "" for p in content.parts)
            break
    print("\n" + "=" * 64)
    print(f"🧬 第 {_calls['n']} 次模型调用")
    print(f"   本轮 instruction: {instr!r}")
    print(f"   输入: {user_msg!r}")
    return None  # 返回 None = 不拦截，正常调用模型


def show_output(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> Optional[LlmResponse]:
    """每次模型返回【后】打印：模型输出。"""
    text = ""
    if llm_response.content and llm_response.content.parts:
        text = "".join(p.text or "" for p in llm_response.content.parts)
    print(f"   返回: {text!r}")
    return None


class NoTemplateLlmAgent(LlmAgent):
    """instruction 不做 {} 变量注入的 LlmAgent（专为 GEPA 优化用）。

    为什么需要它：GEPA 会用"候选 instruction"clone 出新 agent
    （clone(update={"instruction": 候选})）。而反思模型有时会在候选里写入
    形如 {key} 的占位符——ADK 默认把 {key} 当 session state 变量注入，
    找不到就抛 KeyError（Context variable not found: `key`），优化直接中断。
    这里重写 canonical_instruction 返回 bypass_state_injection=True，
    让 instruction 原样使用、不做 {} 注入，从而对含花括号的候选也稳。
    """

    async def canonical_instruction(self, ctx):
        if isinstance(self.instruction, str):
            return self.instruction, True  # True = 跳过 {} state 注入
        return await super().canonical_instruction(ctx)


root_agent = NoTemplateLlmAgent(
    name="faq_agent",
    model=MODEL,
    description="回答关于 ADK 的常见问题。",
    # 故意写得很含糊：没有规定语言、长度、风格 —— 交给 GEPA 去优化
    instruction="回答用户的问题。",
    # 打印每次模型调用的 instruction / 输入 / 输出，直观看到 GEPA 的进化过程
    before_model_callback=show_input,
    after_model_callback=show_output,
)
