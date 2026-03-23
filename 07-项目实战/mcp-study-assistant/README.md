# MCP 学习资料助手

这是一个适合教学演示的最小 MCP 项目。

它把当前仓库里的 Markdown 学习资料暴露成一个本地 MCP 服务，并提供一个最小客户端演示完整链路：

1. 初始化连接
2. 发现 Tools / Resources / Prompts
3. 调用搜索工具
4. 读取文档资源
5. 获取讲解 Prompt

## 项目目标

这个项目重点不是“做一个大而全的 AI 应用”，而是让你清楚看到：

- MCP 服务端怎么暴露能力
- MCP 客户端怎么发现能力
- Tool、Resource、Prompt 三者到底怎么分工

## 目录结构

```text
07-项目实战/mcp-study-assistant/
├── README.md
├── mcp_server.py
└── demo_client.py
```

## 运行方式

### 方式一：在仓库根目录运行

当前目录应为：

```text
F:\github\agent-teacher
```

运行：

```bash
python 07-项目实战/mcp-study-assistant/demo_client.py --topic MCP --days 7
```

带查询词：

```bash
python 07-项目实战/mcp-study-assistant/demo_client.py --query Agent --topic LangGraph --days 5
```

显示更详细的交互日志：

```bash
python 07-项目实战/mcp-study-assistant/demo_client.py --query RAG --verbose
```

### 方式二：在项目目录运行

当前目录应为：

```text
F:\github\agent-teacher\07-项目实战\mcp-study-assistant
```

运行：

```bash
python demo_client.py --topic MCP --days 7
```

带查询词：

```bash
python demo_client.py --query Agent --topic LangGraph --days 5
```

显示更详细的交互日志：

```bash
python demo_client.py --query RAG --verbose
```

### 常见报错

如果你已经在 `07-项目实战/mcp-study-assistant/` 目录里，却仍然执行：

```bash
python 07-项目实战/mcp-study-assistant/demo_client.py --topic MCP --days 7
```

就会把路径重复拼接，出现类似报错：

```text
...mcp-study-assistant\07-项目实战\mcp-study-assistant\demo_client.py
```

原因不是代码有问题，而是当前目录和相对路径一起重复了。

## 这个项目有哪些能力

### Tools

- `search_docs`
  按关键词搜索仓库中的 Markdown 教学资料
- `build_study_plan`
  根据主题和天数生成一个简单学习计划

### Resources

- `course://<相对路径>`
  读取仓库中的 Markdown 教学文档

### Prompts

- `explain_topic`
  生成一个“给指定人群讲解某个主题”的 Prompt 模板

## 适合你观察什么

1. 服务端如何响应 `initialize`
2. 客户端为什么先 `list`，再 `call/read`
3. 文档为什么更适合做 Resource，而不是 Tool
4. Prompt 单独暴露后，对宿主应用有什么好处

## 可继续扩展的方向

1. 增加 `list_topics` Tool
2. 增加 `generate_quiz` Prompt
3. 给 `search_docs` 增加更好的排序
4. 把客户端接到真实 LLM，让 LLM 自动决定调用哪个 Tool
