# 进阶 07：可打断 / 可纠正的聊天 Agent（ADK 内核 + 自研网页）

## 这一关解决什么

一个高频但常被忽视的生产问题：

> 用户说完一句话、任务已经启动（正在思考 / 正在调工具），
> 这时用户又发来一句话 —— 纠正、修改、追加、或直接叫停。Agent 怎么优雅处理？

本关卡用 **ADK 的 LlmAgent + Runner + 工具**做执行引擎，在它之上架一套
「中断总线 + 安全检查点」，并自带一个 **WebSocket 网页**，真正演示
「流式输出 / 工具执行途中，用户插话打断」。

## 为什么不用 `adk web`

`adk web` 的标准 UI 是**回合制**：发一句、等它回完，没法在「一句话还没回完」时插话。
而本关卡的核心就是「执行中插话」，所以用 WebSocket 做**全双工**通道
（[server.py](server.py) + [web/index.html](web/index.html)）。
注意：本包仍是**合法的 ADK Agent**，`adk run adv_07_interrupt` 也能跑（只是回合制）。

## 运行

```bash
# 在 agent-google-adk 目录执行。默认 mock 离线模式，无需任何 Key。
python -m adv_07_interrupt.server
# 浏览器打开 http://127.0.0.1:8000
```

试一试：

1. 发「调研北京的天气」→ **多工具任务**，会依次调用 `web_search → calculator → write_note` 再汇总。中间任意时刻发「改成调研上海」或「停」，观察它在**安全边界**
   处响应打断：正在跑的那个工具会先跑完（不留未配对的调用），再切换/停止。
2. 发「查一下北京的天气」，趁它搜索时发「改成上海」→ 看它取消旧任务、改查上海。
3. 发「搜索 Python 教程」，中途发「算了，停」→ 看它停下不再续做。
4. 发「给老王转账 100」，中途发「停!」→ 转账是**不可中断**的，会照常完成（能看到流水号），
   之后才响应叫停。

> **mock 与 real 的区别（重要）**：mock 模式下「调研…」的 3 步流水线是**写死的**，一定按
> `搜索→计算→写笔记` 走。real 模式下**调几个工具完全由 Gemini 自己决定**——只说「调研北京
> 天气」它很可能搜一次就直接总结了。本项目已在 system instruction 里要求「调研类任务要分多步、
> 依次多调工具」来引导它，但 LLM 不保证每次都照做。想在 real 模式**稳定**看到多工具，直接下
> 一个本身就需要多个工具的指令，例如：
> 「搜一下北京天气，把结果写进 report.txt，再算一下 12*34」。

### 关于 .env 与真假模型切换

本关卡会自动加载 `.env`（优先本包目录，其次**上一级** `agent-google-adk/.env` —— 和其它关卡
共用同一个即可，`adk web`/`adk run` 本来就读它）。切换逻辑：

- **没配凭证** → 自动用离线 mock（无需 Key，开箱即跑）。
- **上一级 .env 里配了凭证**（`GOOGLE_API_KEY` 或 `GOOGLE_GENAI_USE_VERTEXAI=TRUE`）
  → 自动切换到**真实 Gemini**，还能看到 token 级流式输出（SSE）。
- 想强制某一种：`INTERRUPT_DEMO_MOCK=1`（强制 mock）/ `INTERRUPT_DEMO_MOCK=0`（强制真实）。

启动时会打印当前模式（mock / real），一眼可辨。真实 Vertex AI 需要按
`环境变量配置示例.txt` 配好凭证（必要时含 `HTTPS_PROXY`）。

### LLM 调用日志（入参 / 返回 / 耗时）

每次调用模型都会在**服务端控制台**打印**一行**，把【入参 + 返回值完整内容】拼在一起（含耗时），
真实 Gemini 和离线 mock 都生效：

```
[LLM 入参/返回值] 耗时=602ms  system: 你是一个可以调用工具的中文助手…  contents[3]: user:text='算一下 2+3*4' ; model:call=calculator({'expression': '2+3*4'}) ; user:resp=calculator->{'value': 14}  工具: ['web_search', 'calculator', 'write_note', 'transfer'] / text='…结论：…value: 14'
```

实现方式见 [log_callbacks.py](log_callbacks.py)：用 ADK 的 `before_model_callback` /
`after_model_callback`（模型调用前后触发，与具体模型无关，所以 real/mock 通用）。
`before` 记开始时间并渲染入参暂存，`after` 把【入参 + 返回值】拼成一行输出并算出耗时。
设 `INTERRUPT_DEMO_LOG_LLM=0` 可关闭。

## 核心机制：把「中断」架到 ADK Runner 之上

> 这一节从零讲清「它正忙时我还能插话」是怎么做到的。会 Python 就能看懂，不懂 asyncio 也没关系。

### 先记住三个底层事实（看代码前务必理解）

**① ADK 的一轮对话 = 一串「事件」（Event），边产边收。** 调用 `runner.run_async(...)` 得到的不是「一个最终答案」，而是一个**异步生成器**：模型每产出一点东西就吐一个 Event 给你——一段文字是一个 Event、「我要调用 web_search」是一个 Event、「web_search 结果回来了」又是一个 Event。你是**一边收一边处理**，不用等它全部跑完（对应 server.py 里的 `async for ev in agen`）。

**② 一次工具调用，天生是「两个分开的事件」。** 先来 `function_call`（模型说："我要调 `web_search(北京天气)`"），工具真正跑完后才来 `function_response`（结果 `{...}`）。慢工具（搜索要 2 秒）这两个事件之间就有一段「执行中」窗口——**打断就发生在这段窗口里**。

**③ 普通回合制 UI 只有「一来一回」一条道。** `adk web` 是：你发一句 → 等它回完 → 你才能再发。想「它正忙时你还能插话」，就必须有一条**反方向、随时可用**的通道。本关用 **WebSocket**（全双工：两头都能随时主动发），所以才自己写 server.py。

### 难点：两件事要同时进行，还不能互相卡住

- A. 用户随时可能发新消息（纠正 / 追加 / 叫停）；
- B. Agent 正一个一个产出事件、调工具。

如果用一根循环「先等 Agent，再看用户」，Agent 一忙（比如卡在 2 秒的搜索里）用户消息就进不来了。所以用 asyncio 把「读输入」和「跑任务」拆成两个并发协程。

### 三步实现

**第 1 步·读输入单独一个协程，永不卡执行。** `_read_ws()` 专门循环读 WebSocket，把每句话丢进队列 `inbox`。它和执行循环是两个协程，所以 Agent 再忙，读输入也照常进行。

**第 2 步·执行循环同时盯「两个水龙头」。** `_run_single_turn()` 里用 `asyncio.wait(..., FIRST_COMPLETED)` 同时等两件事，谁先来先处理谁：`get_event`（ADK 的下一个事件，来自 `merged` 队列，由 `feed_events()` 把 `runner.run_async` 的事件搬进来）、`get_input`（用户的下一句新输入，直接来自 `inbox`）。

**第 3 步·收到新输入不立刻切，先排队、等安全边界。** 途中收到的新话先记进 `pending`，并不马上打断，等到**安全边界**（见下）才真正切换任务。

下面这张图把它画出来（概念示意；图中「用户新输入」在代码里直接从 `inbox` 读取）：

```
浏览器 ──WS──┐
            ▼
   _read_ws() ── 持续读输入 ──▶ inbox (asyncio.Queue)
                                   │
         ┌─────────────────────────┤ 合并成一路
         ▼                         ▼
   feed_events()              feed_input()
   消费 runner.run_async()     转发用户新输入
   的事件流                        │
         └──────────┬──────────────┘
                    ▼
             单点消费 merged 队列：
             · 事件 → 推给网页（文本/工具调用/工具结果）
             · 新输入 → 记为「待生效打断」
             · 到达【安全边界】→ 中止当前 turn，用新输入重开 turn
```

### 安全边界：本关最重要的一点

全关的灵魂。我们用一个计数器，跟踪「有没有发出去却还没拿到结果的工具调用」：

`outstanding = 已发出的 function_call 数 − 已收到的 function_response 数`

规则只有一条：**只有当 `outstanding == 0`（所有工具调用都已拿到结果）时，才允许切换到新任务。**

为什么？如果在「工具调用已发出、结果还没回来」时就硬切，会话历史里会留下一个**没有配对结果的 `function_call`**，下一轮再请求模型时 Gemini 会直接报错（它要求每个 call 必须有对应的 response）。这和手写 Agent 时「每个 tool_call 必须配一个 tool_result」是同一条铁律，只是换成了 ADK 的术语。

**顺带白送一个正确行为——不可中断工具。** 转账（`transfer`）途中你喊「停」，此刻 `outstanding` 还是 1（转账的 call 发了、response 没回），系统**不会**切，会等转账跑完、结果回来、`outstanding` 归 0 之后才处理你的「停」。于是转账天然不会被停在半截——不用写任何特判，安全边界自动保证。

### 完整走一遍（建议对照这段读代码）

用户发「调研北京天气」，1 秒后趁它在搜索又发「改成上海」：

1. `_read_ws` 把「调研北京天气」放进 `inbox`；主循环取出，开一个 turn。
2. 模型产出 `function_call: web_search(北京天气)` → `outstanding = 1`，网页显示「调用 web_search」。
3. 搜索要 2 秒。第 1 秒用户发「改成上海」→ `_read_ws` 丢进 `inbox` → `get_input` 立刻就绪 → 记进 `pending`，网页提示「收到新输入（将在当前工具完成后生效）」。此刻 `outstanding==1`，**不切**。
4. 第 2 秒 `web_search` 结果回来 → `function_response` 事件 → `outstanding = 0`。
5. 循环检查到「`pending` 非空 且 `outstanding==0`」→ 命中安全边界 → 中止当前 turn，用「改成上海」重开下一个 turn（ADK 带着已有历史重新规划，于是改查上海）。

把第 4 步换成「转账」而非搜索，模型就会先把转账跑完才响应打断——这正是「不可中断」的来历。

## 文件结构

```
adv_07_interrupt/
├── __init__.py      # from . import agent（ADK 约定）
├── agent.py         # root_agent（LlmAgent）+ 四个工具（搜索/计算/写笔记/转账）
├── mock_llm.py      # 离线假模型（实现 ADK BaseLlm 接口），让无 Key 也能跑
├── server.py        # FastAPI + WebSocket：中断总线 + 安全检查点 ★核心
└── web/
    └── index.html   # 聊天网页，输入框【始终可用】，执行中也能插话
```

## 常见误区

- **直接 `cancel()` 当前 turn 来打断**：可能停在「函数调用没配对结果」的中间态，
  下一轮直接报错。应改为「只在 `outstanding==0` 的安全边界切换」。
- **把所有工具都当成可随时打断**：转账、下单这类不可逆操作必须跑完。本关靠「安全边界」
  天然保证了这一点 —— 工具执行期间不会切换。
- **读输入时阻塞了执行**：必须让「读 WebSocket」在独立协程里跑，否则 Agent 一忙，
  新输入就进不来，也就无从打断。

## 依赖说明

`fastapi` / `uvicorn` 是 `google-adk` 的传递依赖，装了 ADK 就有，无需额外安装。

## 配套

- 概念讲解见上级目录讲义：[11.Google-ADK智能体框架实战.md](../../11.Google-ADK智能体框架实战.md)
- 本关与 `adv_01_custom_agent`（自定义控制流）互补：一个讲「怎么编排」，一个讲「怎么被打断」。
