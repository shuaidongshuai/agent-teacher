# 进阶 06：评测闭环（adk eval + 评测集 + CI 回归闸门）

把"能跑"升级成"**能评、能回归**"：定义评测集 → `adk eval` 打分 → 做成 CI 闸门，改坏了自动红灯。

## 目录

1. [评测集(evalset)长什么样](#1-评测集evalset长什么样)
2. [两类指标 + test_config.json](#2-两类指标--test_configjson)
3. [怎么跑 adk eval + 看报告](#3-怎么跑-adk-eval--看报告)
4. [做成 CI 回归闸门](#4-做成-ci-回归闸门)
5. [常见坑](#5-常见坑)

## 1. 评测集(evalset)长什么样

[adv_06_eval.evalset.json](adv_06_eval.evalset.json) 有 3 个用例，每个用例核心是三部分：

```jsonc
{
  "eval_set_id": "adv_06_eval",
  "eval_cases": [{
    "eval_id": "weather_beijing",
    "conversation": [{
      "user_content":   { "parts": [{ "text": "北京天气怎么样？" }], "role": "user" },   // 输入
      "final_response": { "parts": [{ "text": "北京当前天气：晴，18℃" }], "role": "model" }, // 期望回复
      "intermediate_data": {                                                            // 期望"工具轨迹"
        "tool_uses": [{ "name": "get_weather", "args": { "city": "北京" } }]
      }
    }]
  }]
}
```

要点：`intermediate_data.tool_uses` 是**期望的工具调用轨迹**——评测会检查 agent 是否按预期调用了 `get_weather(city=北京)`，这比只看最终文字更能抓住"行为对不对"。

> 评测集不建议手搓 JSON：可以用 `adk web` 跑一遍、把满意的会话另存为 eval case，或像本仓库那样用 `EvalSet` 的 pydantic 模型生成（保证 schema 合法）。

## 2. 两类指标 + test_config.json

`adk eval` 会**自动读取评测集同目录的 [test_config.json](test_config.json)** 作为指标与阈值：

```json
{ "criteria": {
    "tool_trajectory_avg_score": 1.0,
    "response_match_score": 0.3
} }
```

| 指标 | 判什么 | 特点 |
|---|---|---|
| `tool_trajectory_avg_score` | 实际工具调用序列 vs 期望 `tool_uses` | 看**行为**不看文字；1.0 = 必须完全一致 |
| `response_match_score` | 最终回复 vs `final_response` 的字面接近度(ROUGE-1) | 看**文字**；中文偏严，阈值别设太高 |
| `final_response_match_v2` *(可选)* | LLM 裁判判语义是否匹配 | 对中文/换句话说友好，但要额外调模型、更慢更贵 |

本关卡用前两个（都能从一次运行里直接算出，不需额外裁判模型）。想要语义评分就把 `response_match_score` 换成 `final_response_match_v2`（见 adv_04 的用法）。

## 3. 怎么跑 adk eval + 看报告

```bash
cd agent-google-adk
# AGENT 传目录（不是 __init__.py）；评测集可跟在后面，可指定只跑某几个用例
adk eval adv_06_eval adv_06_eval/adv_06_eval.evalset.json
# 只跑其中两个用例：
adk eval adv_06_eval adv_06_eval/adv_06_eval.evalset.json:weather_beijing,time_shanghai
```

报告会按用例列出每个指标的得分与是否 PASS/FAIL：某条 FAIL，就看是**轨迹**错了（调错/漏调工具）还是**回复**没达标（文字差太远）——两类指标正是为了让你一眼定位到底哪儿坏了。

> 需要真实模型凭证：`adk eval` 会**实际把 agent 跑一遍**再和评测集对比。Vertex 模式记得开代理。

## 4. 做成 CI 回归闸门

评测的真正价值是**回归**：每次改 prompt / 换模型 / 动工具前，先跑一遍评测，掉分就拦住。[ci_gate.py](ci_gate.py) 用 `AgentEvaluator.evaluate` 做这件事——达不到 test_config.json 的阈值就抛 `AssertionError` → 进程**非零退出**：

```bash
python adv_06_eval/ci_gate.py        # 退出码 0=通过，1=未达标，2=跑不起来(没凭证等)
```

放进 CI（示意，GitHub Actions）：

```yaml
- name: Agent 评测回归闸门
  run: python adv_06_eval/ci_gate.py   # 掉分这步就 fail，PR 红灯
```

关键就一行：`AgentEvaluator.evaluate(agent_module="adv_06_eval", eval_dataset_file_path_or_dir=..., num_runs=1)`——它内部会读同目录的 test_config.json 做判定。`num_runs` 调大可对非确定性取多次平均、更稳。

## 5. 常见坑

- **AGENT 参数是目录不是文件**：`adk eval adv_06_eval ...`，别写成 `adv_06_eval/__init__.py`（和 `adk optimize` 一样的坑）。
- **ROUGE 对中文偏严**：`response_match_score` 阈值别设高（这里用 0.3）；要语义评分改用 `final_response_match_v2`（LLM 裁判，更贵）。
- **LLM 非确定性**：同一用例多跑结果会抖，用 `num_runs`>1 取平均；轨迹类指标比文字类稳。
- **评测要花钱/要联网**：它会真跑 agent（和裁判模型）。CI 里注意配额与凭证。
- **评测集要和能力一起演进**：加了新工具/新场景，记得补用例，否则回归覆盖不到。


