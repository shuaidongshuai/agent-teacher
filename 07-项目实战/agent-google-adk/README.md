# Google ADK 智能体框架实战

用 **Google ADK（Agent Development Kit）** 从零搭一套"由浅入深"的智能体教学项目：
11 个单点关卡逐个吃透核心能力，最后用一个 **AI 深度研究助手** 把它们全部串起来。

> 配套讲义见上级目录：[11.Google-ADK智能体框架实战.md](../11.Google-ADK智能体框架实战.md)

## 覆盖的核心能力

| 关卡 | 目录 | 学到的 ADK 能力 |
|---|---|---|
| 01 | `s01_llm_agent` | LlmAgent 基础（name / model / instruction / description） |
| 02 | `s02_function_tools` | 函数工具：普通 Python 函数当工具 |
| 03 | `s03_builtin_search` | 内置工具 `google_search` 及其独占约束 |
| 04 | `s04_sub_agents` | 多智能体委派（sub_agents / transfer） |
| 05 | `s05_agent_as_tool` | 把 Agent 当工具用（AgentTool） |
| 06 | `s06_sequential` | SequentialAgent 顺序流 + `output_key`/state 传递 |
| 07 | `s07_parallel` | ParallelAgent 并行流 |
| 08 | `s08_loop` | LoopAgent 循环 + `escalate` 退出 |
| 09 | `s09_structured_output` | 结构化输出 `output_schema`（Pydantic） |
| 10 | `s10_callbacks` | 回调：输入护栏 + 工具日志 |
| 11 | `s11_memory` | 记忆：state 短期 + 本地文件长期 |
| ★ | `research_assistant` | **综合 capstone**：规划→并行研究→撰写→评审循环→定稿 |

## 环境准备

```bash
# 需要 Python 3.10+
pip install -r requirements.txt

# 配置模型 Key：把「环境变量配置示例.txt」复制成 .env 并填入
#   GOOGLE_API_KEY（AI Studio 免费获取：https://aistudio.google.com/apikey）
```
## 三种运行方式

### 1) Web 调试台（推荐初学）

```bash
adk web            # 在 agent-google-adk 目录执行
```

浏览器打开后，从左上角下拉框选择任意关卡（如 `s01_llm_agent`、`research_assistant`），
即可对话，并在右侧看到工具调用、state 变化、事件轨迹——这是理解 Agent 行为的最佳视图。

### 2) 命令行单跑某个关卡

```bash
adk run s02_function_tools
adk run research_assistant
```

### 3) 编程式运行 capstone（不依赖 adk web）

```bash
python run_demo.py                 # 用默认主题
python run_demo.py "多智能体系统"   # 自定义主题
```

`run_demo.py` 用 `Runner + InMemorySessionService` 驱动研究助手，并打印每个子 Agent
的产出与工具调用，最后把报告落盘到 `research_assistant/output/`。

## 评测（Evaluation）

关卡 02 附带一个评测集，演示 `adk eval` 如何检查"该调工具时有没有调对"：

```bash
adk eval s02_function_tools s02_function_tools/s02_function_tools.evalset.json
```

> 评测需要真实模型 Key（会实际调用模型跑一遍再对比）。

## 进阶关卡（选学，4 个更强的能力）

学完 11 关 + capstone 后，这 4 关带你进入 ADK 的生产级/前沿能力。每关仍是标准 ADK 目录结构。

| 关卡 | 目录 | 能力 | 额外依赖 |
|---|---|---|---|
| 进阶01 | `adv_01_custom_agent` | 自定义 `BaseAgent`，实现条件分支等动态控制流 | 无 |
| 进阶02 | `adv_02_mcp_tools` | 用 `MCPToolset` 接入 MCP 文件系统服务器 | Node.js（`npx`） |
| 进阶03 | `adv_03_a2a` | A2A 协议：跨进程调用远程 Agent | `pip install a2a-sdk` |
| 进阶04 | `adv_04_optimize` | GEPA 提示词自动优化（`adk optimize`） | `pip install "google-adk[eval]"` |

运行要点：

```bash
# 进阶01：直接可跑
adk run adv_01_custom_agent

# 进阶02：需要 Node/npx，首次会自动拉起 MCP 文件系统服务器
adk run adv_02_mcp_tools

# 进阶03：A2A 需要两个终端
#   终端 A（服务端）:
uvicorn adv_03_a2a.remote_server:a2a_app --host localhost --port 8001
#   终端 B（消费端）:
adk run adv_03_a2a

# 进阶04：GEPA 自动优化 instruction（真实多轮调用，耗配额，实验特性）
adk optimize adv_04_optimize/__init__.py \
    --sampler_config_file_path adv_04_optimize/sampler_config.json \
    --print_detailed_results
```

## 目录结构

```
agent-google-adk/
├── requirements.txt
├── 环境变量配置示例.txt        # 复制成 .env 使用
├── run_demo.py                 # 编程式运行 capstone
├── s01_llm_agent/ ... s11_memory/   # 11 个单点关卡（各含 __init__.py + agent.py）
└── research_assistant/         # capstone：schemas / tools / callbacks / agent
```

每个关卡文件夹都是**自包含**的：一个 `__init__.py`（`from . import agent`）+ 一个
`agent.py`（定义 `root_agent`）。这正是 ADK 约定的 Agent 目录结构，可直接被 `adk web`/`adk run` 识别。

## 建议学习顺序

1. 按 `s01 → s11` 逐关卡看代码 + 跑 `adk web`，每关只盯住"这一关新增的那个概念"。
2. 看懂后再读 `research_assistant/agent.py`，观察这些能力如何组合成一条流水线。
3. 跑 `python run_demo.py`，对照打印出的执行轨迹理解"规划→并行研究→撰写→评审→定稿"。
4. 做讲义结尾的练习题（改造 capstone）。

## 换成非 Gemini 模型（可选）

```python
# pip install litellm 后：
from google.adk.models.lite_llm import LiteLlm
model = LiteLlm(model="openai/gpt-4o")   # 或 anthropic/claude-... 、本地 ollama 等
```

把关卡里的 `model=MODEL` 换成上面的 `model` 即可。

## 部署（了解即可）

```bash
adk deploy cloud_run --with_ui research_assistant   # 部署到 GCP Cloud Run
adk deploy agent_engine research_assistant          # 部署到 Vertex AI Agent Engine
```

## 安全提示

- 关卡 03 的 `google_search`、capstone 的 `web_search` 都会（在真实实现下）发起外部请求；
  教学示例里 `web_search` 是**模拟实现**，不会真的联网。
- 护栏（关卡 10 / capstone）只是最小演示，生产环境需要更完整的安全策略。
- `.env` 已被仓库 `.gitignore` 忽略，不要把 Key 提交到 git。

