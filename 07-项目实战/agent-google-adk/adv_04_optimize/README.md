# 进阶 04：GEPA 提示词自动优化（原理 + 使用 + 断点续跑）

用 `adk optimize` 让 GEPA 自动优化 `faq_agent` 的 instruction。本文讲清：**GEPA 原理、什么时候用、相比手动调 prompt 的优势、断点续跑机制、怎么停**。

## 目录

1. [GEPA 原理](#1-gepa-原理)
2. [什么情况下需要用](#2-什么情况下需要用)
3. [相比手动调 prompt 的优势](#3-相比手动调-prompt-的优势)
4. [它不是银弹](#4-它不是银弹)
5. [怎么运行](#5-怎么运行)
6. [优化结果在哪看](#6-优化结果在哪看)
7. [断点续跑机制（含源码依据）](#7-断点续跑机制含源码依据)
8. [怎么自动/优雅地停](#8-怎么自动优雅地停)

## 1. GEPA 原理

**GEPA = Genetic-Pareto**，即"反思式提示词进化"（论文《GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning》，已集成进 DSPy 与 ADK）。它把"调 prompt"变成一个**带反馈的进化搜索**循环：

```
种子 prompt
   │
① 评测：在评测集上跑，拿到分数 + 失败的具体表现（traces/哪答错）
   │
② 反思(变异)：让"反思模型"读失败反馈，推理"该怎么改" → 生成新 prompt
   │
③ Pareto 选择：保留"在不同子任务上各有所长"的一批候选（帕累托前沿），
   保持多样性、避免钻进局部最优
   │
④ 从候选池挑一个，抽一小批样本，回到 ①，循环直到预算(max_metric_calls)用完
   │
输出：验证集上最好的那版 prompt
```

**核心创新**：不是只看一个数字分数（像 RL 那样），而是**利用自然语言反馈**（"为什么错、trace 长什么样"）让 LLM 反思修改，因此**样本效率高**——用很少的评测次数就能追上甚至超过 RL 类方法。

**一句话类比**：GEPA ≈ 不知疲倦的资深工程师，反复"看失败案例 → 想为什么 → 改 prompt → 再测"，并用帕累托前沿防止钻牛角尖。

对应本关卡产物：`gepa_runs/candidates.json` 里从"回答用户的问题。"进化出的更完整版本，就是第②步反思的结果；`gepa_runs/candidate_tree.html` 是第③步的候选树。

## 2. 什么情况下需要用

**前提（缺一不可）**：

- 有**能自动测好坏的评测集 + 指标**。这是命门——指标全 0 它就抓瞎（本关卡最初用 ROUGE 评中文，分全 0，GEPA 没方向；换成 `rubric_based_final_response_quality_v1` 后才真进化）。
- 优化是**离线 / CI 的一次性动作**，产出固定 prompt 再上线；线上服务用静态 prompt，不跑 GEPA。

**适合**：prompt 质量能量化、任务边界情况多到肉眼调不过来；想要可复现、可回归的改进；系统里多个 prompt / 多智能体要一起调。

**别用 / 没必要**：没评测集或定不出指标；指标是烂代理（如中文用 ROUGE）；就一个简单 prompt 手改两下就好。

## 3. 相比手动调 prompt 的优势

| 维度 | 手动调 prompt | GEPA |
|---|---|---|
| 依据 | 凭感觉、看几个例子 | 对着指标 + 全量评测集，有客观分数 |
| 搜索广度 | 想到几种写法试几种 | 系统性探索大量候选，帕累托前沿防钻牛角尖 |
| 用失败案例 | 人工看、容易漏 | 自动读失败 trace 反思、针对性修 |
| 规模 | 案例一多人就顶不住 | 评测集越大越能覆盖，不知疲倦 |
| 可复现 | 难复盘、难回归 | 可重跑、可版本化、可回归测试 |
| 成本 | 人力时间 | 机器 API 调用（换人力） |

核心价值：**把"凭手感调措辞"变成"对着可度量目标的工程化搜索"**——你把精力花在"定义什么是好答案（评测集+指标）"上，枯燥试错交给它。

## 4. 它不是银弹

- **天花板 = 你的评测集和指标**：指标烂，产物也烂；人的判断力转移到了"设计评测"上，没消失。
- **产物要 review**：可能啰嗦，甚至塞进 `{key}` 这类占位符——ADK 默认会把 `{key}` 当 state 变量注入而报 `KeyError`。本关卡用 `NoTemplateLlmAgent`（重写 `canonical_instruction` 返回 `bypass_state_injection=True`）兜底，见 [agent.py](agent.py)。
- **快速一次性需求**：手动更快，没必要上 GEPA。
## 5. 怎么运行

```bash
cd agent-google-adk
# AGENT 参数传 agent 目录（不是 __init__.py）
adk optimize adv_04_optimize \
    --sampler_config_file_path adv_04_optimize/sampler_config.json \
    --optimizer_config_file_path adv_04_optimize/optimizer_config.json \
    --print_detailed_results
```

三份配置：

- [sampler_config.json](sampler_config.json)：评测指标 + 用哪个评测集训练。当前用 `rubric_based_final_response_quality_v1`（rubric 质量评分，对中文/自由问答友好）。
- [optimizer_config.json](optimizer_config.json)：`max_metric_calls`（预算）、`reflection_minibatch_size`、`run_dir`。
- [adv_04_train.evalset.json](adv_04_train.evalset.json)：训练用问题 + 期望答案。

> 需要真实模型凭证，且会多轮调用（含 rubric 裁判），耗配额。Vertex 模式记得开代理。

## 6. 优化结果在哪看

1. **终端末尾**（`adk optimize` 打印，源码 `cli_tools_click.py`）：
   ```
   ================================================================
   Optimized root agent instructions:
   ----------------------------------------------------------------
   <优化后的 instruction>
   ================================================================
   ```
2. **文件**：`gepa_runs/candidates.json` 里最后一个 `agent_prompt` 就是最佳候选（GEPA 始终保存"目前最优"）。

若两处都还等于原始的"回答用户的问题。"，说明这轮没进化出更好的（多半是评分没区分度），不是没打印。

## 7. 断点续跑机制（含源码依据）

GEPA 把**已经用掉的调用数**（`total_num_evals`）连同候选一起存进 `run_dir`（`gepa_state.bin` 等），**第二次启动同一个 run_dir 会自动续跑**，不会重跑前面的。

源码依据：

- `gepa/api.py`（run_dir 说明）：
  > If the directory already exists, GEPA will **read the state from this directory and resume** the optimization from the last saved state.
- `gepa/core/engine.py`：剩余预算 = 上限 − 已用
  ```python
  return max(0, max_calls - state.total_num_evals)
  ```

由此得到关键结论——假设第一次 `max_metric_calls=15` 跑满，但要到第 20 次才出更优 prompt：

| 第二次启动怎么设 | 实际会发生 |
|---|---|
| 同 run_dir，`max_metric_calls` 提到 ≥20（如 30） | 从第 16 次接着跑，**只补跑 5 次**就到 20 ✅ |
| 同 run_dir，`max_metric_calls` 仍 =15 | 剩余 = max(0, 15−15) = **0**，立刻退出、啥也不干 ⚠️ |
| 删掉 / 换新 run_dir | 从头来，**跑满 20 次** |

两个要点：

1. **能增量续跑**：先跑小预算看结果，不满意就**调高上限续跑**（从断点接着走，不重跑）。所以预算设小了不浪费——唯一注意：续跑必须把上限调高，否则剩余为 0 白启动。
2. **改了配置必须换 run_dir**：run_dir 里的状态是针对当前指标/评测集的。改了指标（如从 ROUGE 换 rubric）就要 `rm -rf gepa_runs` 或换目录，否则新旧状态不一致。

## 8. 怎么自动/优雅地停

- **自动停（内置）**：跑满 `max_metric_calls` 就自动退出——这就是"什么时候停"的答案，一次性设成一个预算数字即可，**不需要写监控脚本盯着**。收敛后会"空转"到上限，把上限设小即可减少浪费（本任务约第 4 轮就收敛，设 15 足够）。
- **优雅停（可续跑）**：不用 Ctrl+C。GEPA 在有 run_dir 时会装一个 **FileStopper**（`gepa/api.py`），只要：
  ```bash
  touch adv_04_optimize/gepa_runs/gepa.stop
  ```
  它检测到就**优雅停下并保存状态**，下次还能从这里续跑。
- **硬超时兜底**：给进程套挂钟超时防卡死（macOS 用 `gtimeout`，Linux 用 `timeout`，CI 用步骤超时）。
- **收敛即停（进阶）**：底层 `gepa.optimize()` 还支持 `stop_callbacks` / `perfect_score` / `max_reflection_cost`，但 `adk optimize` CLI 未暴露，需绕过 CLI 编程式调用才能用。

一句话策略：**小预算跑 → 看 candidates.json → 不满意就调高上限、同 run_dir 续跑**；想中途停就 `touch gepa.stop`，状态不丢、可续。

