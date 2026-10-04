# agent-from-scratch —— 从零手写一个最小 Agent 内核（L0）

> 这是 `07-项目实战` 里**最底层的一块地基**：在碰任何框架（LangGraph / ADK / Claude Agent SDK）之前，
> 先亲手把它们替你藏起来的那个“循环”写出来。看懂这里，你再回头看别的项目会豁然开朗。

## 这个项目回答一个问题：Agent 到底是什么？

一个 Agent 的本质只有三件事，`mini_agent.py` 把它们全摊开、不借任何框架：

1. **工具 tools**：一组普通函数 + 它们的 JSON Schema，告诉模型“你能做什么”。
2. **循环 loop**：模型想调工具 → 我执行 → 把结果塞回去 → 再问模型，直到它不再要工具。
3. **停止 stop**：模型这一轮只回文字、不要工具 = 本次任务结束。

```
用户输入
   │
   ▼
┌────────────────────────────────────────────┐
│  while 还没结束：                            │
│    1. 把历史 + 工具交给模型，让它产出这一步   │  ← generate()
│    2. 模型只回文字？ → 打印，结束循环          │  ← stop
│    3. 模型要调工具？ → (权限确认) 执行每个工具  │  ← approve() + dispatch()
│    4. 把工具结果塞回历史，回到第 1 步          │  ← send_tool_results()
└────────────────────────────────────────────┘
```

对照你已经做过的 ADK 项目，这个循环正是框架替你转的部分：

| 你手写的部分（本项目） | ADK 里对应的是谁 |
|---|---|
| `agent_turn()` 里的 while 循环 | `Runner.run_async()` 的事件流 |
| `TOOLS` + `FunctionDeclaration` 声明 | `LlmAgent(tools=[...])` |
| `send_tool_results()` 把结果拼回历史 | ADK 的 `session.state` / 事件回填 |
| `approve()` 权限门 | ADK 回合制 + 你在 `adv_07_interrupt` 手搓的中断总线 |
| `MockModel` | 你写过的 `mock_llm.py` |

一句话：**框架帮你转循环、管历史、拼协议；本质没变。手写一遍，框架对你就不再是黑盒。**

## 怎么跑

### 1. Mock 模式（零依赖，先看清循环）

```bash
cd 07-项目实战/agent-from-scratch
python3 mini_agent.py
# 试试：列一下目录   /   读取 mini_agent.py
```

用一个规则驱动的假模型，无需 Key、无需联网，专门用来把循环本身跑通看明白。

### 2. 真实 Gemini 模式（走你 ADK 那套 Vertex）

用装了 `google-adk` 的那个 venv（里面已带 `google-genai`）。先手动建一个 `.env`
（你的环境对 `.env` 有写保护，需你自己创建），内容与 ADK 项目同一套 Vertex 配置：

```bash
# .env —— 走 Vertex AI（与 agent-google-adk 相同）
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=xiling-453607
GOOGLE_CLOUD_LOCATION=global
GOOGLE_APPLICATION_CREDENTIALS=/Users/chenmingdong01/Documents/work/gcs_credentials.json
HTTPS_PROXY=http://127.0.0.1:7890   # 该网络需开代理才能换 token
```

```bash
python3 mini_agent.py --real
# 试试：读取 README.md 并总结 / 在 data 目录新建一个 hello.txt 写入“你好”
```

此时模型会**自己决定**调用哪个工具、调几次。遇到 `write_file`/`run_shell` 会先问你 `y/N`。

> 工作目录默认是当前目录，可用环境变量覆盖：`AGENT_WORKSPACE=./data python3 mini_agent.py --real`

## 代码地图（都在一个文件里，从上往下读）

- **规范化结构** `ToolCall` / `ModelTurn`：主循环只认这两个结构，和用哪个模型无关。
- **第 1 件事 工具**：`read_file` / `write_file` / `list_dir` / `run_shell` + `TOOLS` 注册表（含 JSON Schema 和“是否需要确认”）。
- **权限与分发** `approve()` / `dispatch()`。
- **两个后端** `MockModel` / `GeminiModel`：各自管自己的历史格式，对外是同一个接口。
- **第 2+3 件事 主循环** `agent_turn()`：**全文最该精读的 30 行**。

## 练习（从易到难，逐层逼近真实 Agent）

1. 加一个 `search_files(keyword)` 工具（递归 grep），体会“加工具 = 改两处：函数 + Schema”。
2. 给 `run_shell` 加一个命令黑名单（`rm -rf`、`sudo` 等）在 `approve()` 前就拦掉。
3. 把 `MAX_STEPS` 触发改成“让模型自己说 DONE 才停”，对比两种**停止条件**的差异。
4. 历史越来越长会超上下文：写一个 `compact()`，把早期的工具结果压成摘要——这就是 Claude Code 的上下文压缩。
5. 加一个 `spawn_subagent(task)` 工具：内部再起一个 `agent_turn`，体会 subagent / 委派。
6. 做完 1~5，再回头读 `agent-google-adk/`，列出“ADK 到底替我做了上面哪几件事”。

## 和其他项目的关系

- **L0（本项目）**：手写内核，理解“循环 + 工具 + 停止”。
- L1~L4：见 [../README.md](../README.md)（MCP → RAG → 单 Agent → 多 Agent / 框架）。
- 建议顺序：**先把这里跑通并做掉练习 1~3**，再去看 `agent-chat-langgraph`、`agent-google-adk` 的框架版本。
