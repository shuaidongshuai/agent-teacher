# 学习任务拆解 Agent

这是一个适合入门的最小 Agent 项目。

它接收一个学习目标，然后依次完成：

1. 目标分析
2. 任务规划
3. 执行建议生成
4. 计划反思与修正

## 运行方式

```bash
python3 main.py "一周内完成 Agent 基础学习，并做一个最小 Demo"
```

或者在仓库根目录运行：

```bash
python3 07-项目实战/agent-study-planner/main.py "一周内完成 Agent 基础学习，并做一个最小 Demo"
```

## 可选：接入 OpenAI API

如果你已经有 API Key，可以先设置：

```bash
export OPENAI_API_KEY=你的Key
export OPENAI_BASE_URL=https://api.chatanywhere.tech
export OPENAI_MODEL=gpt-4o
export OPENAI_API_STYLE=chat_completions
export OPENAI_SSL_VERIFY=false
```

程序支持两种接口风格：

- `responses`
- `chat_completions`

默认使用 `responses`。

调用 LLM 时，程序现在会额外打印：

- 请求地址
- 请求入参
- 接口原始返回
- 异常信息和堆栈

这样更方便你排查代理地址、模型兼容性和返回格式问题。

如果你不设置 `OPENAI_BASE_URL`，默认会使用官方地址：

```bash
https://api.openai.com
```

如果你使用代理或兼容网关，可以像这样配置：

```bash
export OPENAI_BASE_URL=https://api.chatanywhere.tech
export OPENAI_MODEL=gpt-4o-mini
export OPENAI_API_STYLE=chat_completions
```

如果你的代理证书会导致 `CERTIFICATE_VERIFY_FAILED`，可以临时关闭 SSL 校验：

```bash
export OPENAI_SSL_VERIFY=false
```

说明：

- 默认值是 `true`
- 只有在代理证书异常、并且你明确知道风险时，才建议临时设为 `false`
- 关闭后更适合本地调试，不建议长期用于生产环境

模型名也支持通过环境变量覆盖：

```bash
export OPENAI_MODEL=gpt-5-mini
```

说明：

- 默认值是 `gpt-5-mini`
- 如果你的代理或兼容网关只支持某些模型名，可以在这里切换

接口风格也支持通过环境变量覆盖：

```bash
export OPENAI_API_STYLE=responses
```

或者：

```bash
export OPENAI_API_STYLE=chat_completions
```

说明：

- 默认值是 `responses`
- 如果你的代理文档示例是 `messages` + `/v1/chat/completions`，请设置成 `chat_completions`
- 如果你的接口文档示例是 `input` + `/v1/responses`，请设置成 `responses`

如果没有设置 Key，程序会自动回退到本地教学模式，仍然可以完整跑通流程。

## 代码结构理解

### 主流程图

```mermaid
flowchart TD
    A["程序启动 main()"] --> B["读取命令行学习目标"]
    B --> C{"目标是否为空?"}
    C -- "是" --> C1["打印用法并退出"]
    C -- "否" --> D["创建 StudyPlanningAgent"]

    D --> E["初始化 OpenAIPlannerClient"]
    E --> E1["读取环境变量
OPENAI_API_KEY
OPENAI_BASE_URL
OPENAI_MODEL
OPENAI_API_STYLE
OPENAI_SSL_VERIFY"]

    E1 --> F["run(goal)"]
    F --> G["先尝试 generate_plan(goal)"]

    G --> H{"是否存在 OPENAI_API_KEY?"}
    H -- "否" --> L1["记录日志并回退本地模式"]
    L1 --> M["本地教学模式"]

    H -- "是" --> I["构造统一 prompt"]
    I --> J{"OPENAI_API_STYLE"}

    J -- "responses" --> J1["构造 payload
model + input"]
    J -- "chat_completions" --> J2["构造 payload
model + messages + temperature"]

    J1 --> K["构造请求 URL"]
    J2 --> K

    K --> N["打印调试日志
接口风格、地址、SSL、入参"]
    N --> O["按 OPENAI_SSL_VERIFY
创建 SSL context"]
    O --> P["发送 HTTP 请求"]

    P --> Q{"请求成功?"}
    Q -- "否" --> Q1["打印异常和堆栈"]
    Q1 --> M
    Q -- "是" --> R["打印接口原始返回"]

    R --> S["解析 JSON 响应"]
    S --> T{"按接口风格提取文本"}
    T -- "responses" --> T1["从 output / output_text 提取"]
    T -- "chat_completions" --> T2["从 choices[0].message.content 提取"]

    T1 --> U{"能提取文本?"}
    T2 --> U
    U -- "否" --> U1["记录日志并回退本地模式"]
    U1 --> M
    U -- "是" --> V["把文本继续解析成 JSON"]

    V --> W{"JSON 合法?"}
    W -- "否" --> W1["打印异常和堆栈"]
    W1 --> M
    W -- "是" --> X["返回 OpenAI 结果"]

    M --> M1["GoalAnalyzer
解析目标、时间、主题、产出、约束"]
    M1 --> M2["Planner
生成阶段化计划"]
    M2 --> M3["Executor
补充执行建议"]
    M3 --> M4["Reflector
检查问题和改进项"]
    M4 --> M5["返回本地结果"]

    X --> Y["render_result() 输出结果"]
    M5 --> Y
    Y --> Z["程序结束"]
```

### 模块关系图

```mermaid
flowchart LR
    A["main()"] --> B["StudyPlanningAgent"]
    B --> C["OpenAIPlannerClient"]
    B --> D["GoalAnalyzer"]
    B --> E["Planner"]
    B --> F["Executor"]
    B --> G["Reflector"]

    C --> C1["读取环境变量"]
    C --> C2["按接口风格构造请求"]
    C --> C3["发送 HTTP 请求"]
    C --> C4["解析 responses / chat_completions 返回"]

    D --> D1["输出 GoalContext"]
    E --> E1["输入 GoalContext"]
    E --> E2["输出 List[PlanStep]"]
    F --> F1["输入 GoalContext + List[PlanStep]"]
    F --> F2["输出补充后的 List[PlanStep]"]
    G --> G1["输入 GoalContext + List[PlanStep]"]
    G --> G2["输出 ReflectionResult"]

    B --> H["统一组装 result"]
    H --> I["render_result()"]
```

### 每个阶段在做什么

1. `OpenAIPlannerClient`
负责读取环境变量、选择接口风格、发请求、打印日志、解析返回。如果 LLM 调用失败，就交回本地模式。

2. `GoalAnalyzer`
把一句自然语言目标拆成结构化上下文，比如主题、时间限制、预期产出、约束条件。

3. `Planner`
根据结构化上下文生成阶段化计划，决定分几步走、每一步做什么。

4. `Executor`
把比较抽象的步骤补成更可执行的动作建议，让计划不只是标题列表。

5. `Reflector`
对计划做一次简单自检，找出时间过载、缺少复盘、产出不清晰等问题。

6. `render_result()`
把最后结果渲染成适合命令行阅读的文本输出。

## 学习重点

建议你重点阅读 `main.py` 里的这些部分：

- `GoalAnalyzer`：看输入如何被解析
- `Planner`：看任务如何被阶段化
- `Executor`：看任务如何变成执行建议
- `Reflector`：看计划如何被自检

## 建议扩展

你可以继续尝试：

1. 保存结果为 Markdown 文件
2. 增加每日可用学习时长
3. 给每个任务打优先级
4. 接入真实搜索或笔记工具
