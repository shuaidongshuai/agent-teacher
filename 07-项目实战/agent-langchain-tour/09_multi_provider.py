"""
09_multi_provider.py —— 多模型 / 多厂商切换（LangChain v1）

本节目标：体会 LangChain「标准模型接口」最大的红利之一——
换模型、换厂商，**业务代码一个字不改，只改一个 "provider:model" 字符串**。

涵盖两个真实用得上的场景：
  1. 一键切换 switch   —— 同一段代码在 openai / gemini(Vertex) 之间来回切（成本/能力选型、同题对比）
  2. 容灾 failover     —— 主模型挂了自动切备用（`.with_fallbacks`），生产高可用

为什么单独成一个文件：08_advanced 里的结构化输出/流式/中间件/HITL 都是围绕「Agent 怎么跑」的
**执行层**能力；而「多模型切换」是**模型层**的事，和 01_models 一脉相承——01 讲「怎么调一个模型」，
这里讲「怎么在多个模型间自由切换与兜底」。

对应 README「高级功能与适用场景」里的「多模型切换」。

运行：python 09_multi_provider.py
"""

from __future__ import annotations

from common import get_model, require_key

# 想切到哪些模型，就改这个列表——这正是「多模型切换」要演示的：业务代码不动，只改字符串。
# 注意模型名必须在你的 .env / 网关里真实存在（本仓库：openai 走厂内网关、google 走 Vertex）。
CANDIDATES = [
    "openai:gpt-6-sol",
    "google_vertexai:gemini-2.5-flash",
]


def demo_switch_same_code() -> None:
    """同一段业务代码，在不同厂商/模型间切换——只有 spec 字符串变了。

    场景：按成本/能力选型（贵的做难活、便宜的做简单活）、同题多模型对比、灰度切换。
    """
    prompt = "用一句话介绍你自己是哪家公司的什么模型。"
    print("[switch] 同一行 get_model(spec).invoke(prompt)，只改 spec：")
    for spec in CANDIDATES:
        try:
            answer = get_model(spec).invoke(prompt).text
            print(f"  {spec:38} -> {answer}")
        except Exception as e:  # 某个 provider 没配凭据/模型名不对就跳过，不影响演示其它的
            print(f"  {spec:38} -> (跳过) {type(e).__name__}: {str(e)[:60]}")


def demo_failover() -> None:
    """容灾：主模型失败自动切备用——用 LangChain 内置的 `.with_fallbacks()`。

    场景：主力模型限流/宕机/网络抖动时，自动降级到备用模型，保证服务不中断。
    这里故意把主模型设成一个不存在的名字来触发失败，看它自动切到备用。
    """
    if len(CANDIDATES) < 2:
        print("[failover] 需要至少两个候选模型，跳过。")
        return
    primary_spec, backup_spec = CANDIDATES[0], CANDIDATES[1]
    primary_provider = primary_spec.split(":", 1)[0]
    broken = get_model(f"{primary_provider}:__no_such_model__")  # 故意坏的主模型
    backup = get_model(backup_spec)
    robust = broken.with_fallbacks([backup])  # 主失败 → 自动改用备用
    print(f"[failover] 主模型(故意坏) 失败后自动切备用 {backup_spec}：")
    try:
        print("  结果 ->", robust.invoke("用一个词打个招呼").text)
    except Exception as e:
        print("  主备都失败：", type(e).__name__, str(e)[:80])


if __name__ == "__main__":
    if not require_key():
        raise SystemExit(0)
    demo_switch_same_code()
    demo_failover()
