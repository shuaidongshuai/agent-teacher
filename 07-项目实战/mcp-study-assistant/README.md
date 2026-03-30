# MCP 学习资料助手

## 目录

1. [项目解决什么问题](#1-项目解决什么问题)
2. [为什么这个项目适合当前学习阶段](#2-为什么这个项目适合当前学习阶段)
3. [前置知识](#3-前置知识)
4. [学习目标](#4-学习目标)
5. [核心架构与流程](#5-核心架构与流程)
6. [运行方式](#6-运行方式)
7. [推荐观察点](#7-推荐观察点)
8. [常见失败原因](#8-常见失败原因)
9. [练习任务](#9-练习任务)
10. [下一步延伸](#10-下一步延伸)

## 1. 项目解决什么问题

这是一个适合教学演示的最小 MCP 项目。

它把当前仓库里的 Markdown 学习资料暴露成一个本地 MCP 服务，并提供一个最小客户端演示完整链路：

1. 初始化连接
2. 发现 Tools / Resources / Prompts
3. 调用搜索工具
4. 读取文档资源
5. 获取讲解 Prompt

## 2. 为什么这个项目适合当前学习阶段

这个项目特别适合用来理解 MCP 三类能力的分工：

- Tool：主动执行动作
- Resource：读取资料
- Prompt：提供可复用的提示模板

相比天气项目，它更接近“知识型 MCP 服务”。

## 3. 前置知识

建议先完成：

1. [04-工具调用与函数调用/README.md](/Users/chenmingdong01/Documents/AI/agent/04-工具调用与函数调用/README.md)
2. [07-项目实战/2.MCP学习资料助手实战.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/2.MCP学习资料助手实战.md)

## 4. 学习目标

完成这个项目后，你应该能够：

1. 理解 Tool、Resource、Prompt 在 MCP 里的分工
2. 理解客户端为什么先 discover 再 call/read
3. 理解文档资料为什么更适合暴露成 Resource

## 5. 核心架构与流程

目录结构：

```text
07-项目实战/mcp-study-assistant/
├── README.md
├── mcp_server.py
└── demo_client.py
```

当前项目提供：

### Tools

- `search_docs`
- `build_study_plan`

### Resources

- `course://<相对路径>`

### Prompts

- `explain_topic`

## 6. 运行方式

在仓库根目录运行：

```bash
python 07-项目实战/mcp-study-assistant/demo_client.py --topic MCP --days 7
python 07-项目实战/mcp-study-assistant/demo_client.py --query Agent --topic LangGraph --days 5
python 07-项目实战/mcp-study-assistant/demo_client.py --query RAG --verbose
```

也可以在项目目录运行：

```bash
python demo_client.py --topic MCP --days 7
python demo_client.py --query Agent --topic LangGraph --days 5
python demo_client.py --query RAG --verbose
```

## 7. 推荐观察点

建议重点观察：

1. 服务端如何分别暴露 Tool、Resource、Prompt
2. 客户端为什么先 `list`，再 `call/read`
3. 哪些能力更适合 Resource，而不是 Tool
4. Prompt 单独暴露后，对宿主应用意味着什么

## 8. 常见失败原因

常见问题包括：

1. 当前目录和相对路径重复，导致找不到脚本
2. Tool、Resource、Prompt 的职责边界写混
3. 资源路径设计不统一，导致读取不稳定
4. 搜索结果排序过粗，影响后续学习计划质量

## 9. 练习任务

建议做下面 3 个练习：

1. 增加 `list_topics` Tool
2. 增加 `generate_quiz` Prompt
3. 给 `search_docs` 增加更好的排序逻辑

## 10. 下一步延伸

如果你已经理解了 MCP 的三类能力，可以继续做两件事：

1. 把客户端接到真实 LLM，让模型自动决定调用哪个能力
2. 把 MCP 能力接到 Agent 项目里，让它成为更大的任务系统组件
