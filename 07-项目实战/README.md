# 07.项目实战

## 目录

1. [适用人群](#1-适用人群)
2. [学习目标](#2-学习目标)
3. [这一章在整个学习路线里的位置](#3-这一章在整个学习路线里的位置)
4. [建议阅读与实战顺序](#4-建议阅读与实战顺序)
5. [项目能力地图](#5-项目能力地图)
6. [如何使用这一章](#6-如何使用这一章)
7. [总结与下一步建议](#7-总结与下一步建议)

## 1. 适用人群

这部分内容适合已经完成前面理论学习，准备把知识真正串成项目的人，尤其适合：

- 已经看过很多概念，但还没形成完整作品的人
- 做过单点 Demo，希望把 RAG、工具调用、Agent 组合起来的人
- 想通过项目积累可复盘、可讲述、可面试表达的实战经历的人

## 2. 学习目标

学完这一章后，你应该能够：

1. 把 LLM、Prompt、工具调用、RAG、Agent 串成完整项目
2. 理解不同项目各自训练的是哪种能力
3. 根据自己的当前阶段选择合适难度的项目
4. 在项目里补齐运行、排错、复盘和优化意识

## 3. 这一章在整个学习路线里的位置

如果说前面的章节主要在回答：

- 它是什么
- 它为什么这样设计
- 它常见会失败在哪里

那么 `07-项目实战` 解决的是：

**怎么把这些知识变成真正能运行、能观察、能复盘的项目。**

建议不要一开始就选最复杂的多 Agent 项目。  
更稳的路径是：

- 先做单能力项目
- 再做双能力组合项目
- 最后再做多步决策和多 Agent 协作

## 4. 建议阅读与实战顺序

建议按下面顺序推进。

### 第一步：先看项目总清单

1. [项目练习清单.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/项目练习清单.md)

这份清单帮助你知道有哪些项目、它们训练什么能力。

### 第二步：先做单链路项目

2. [智能金融投研助手-RAG/README.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/智能金融投研助手-RAG/README.md)
3. [MCP学习资料助手实战.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/MCP学习资料助手实战.md)
4. [mcp-city-weather/README.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/mcp-city-weather/README.md)

这一步重点训练：

- RAG 链路
- 工具接入
- MCP 服务基本思维

### 第三步：进入单 Agent 项目

5. [LangGraph聊天Agent实战.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/LangGraph聊天Agent实战.md)
6. [agent-chat-langgraph/README.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/agent-chat-langgraph/README.md)
7. [学习资料整理Agent实战.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/学习资料整理Agent实战.md)
8. [agent-study-react/README.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/agent-study-react/README.md)

这一步重点训练：

- 聊天式 Agent
- 记忆
- 工具调度
- 长文本整理和多步执行

### 第四步：进入分工协作类项目

9. [架构师与工人Agent实战.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/架构师与工人Agent实战.md)
10. [agent-planner-executor/README.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/agent-planner-executor/README.md)
11. [Multi-Agent数字员工实战.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/Multi-Agent数字员工实战.md)
12. [agent-digital-employee-multi-agent/README.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/agent-digital-employee-multi-agent/README.md)

这一步重点训练：

- 规划与执行分离
- 角色分工
- 多 Agent 协作
- 轨迹记录与复杂任务控制

## 5. 项目能力地图

你可以把这一章的项目大致分成 4 类。

### 5.1 RAG 型项目

代表项目：

- `智能金融投研助手-RAG`

适合补齐：

- 文档处理
- 切分与检索
- 知识问答链路

### 5.2 工具 / MCP 型项目

代表项目：

- `mcp-city-weather`
- `MCP学习资料助手实战`
- `mcp-study-assistant`

适合补齐：

- 外部能力接入
- MCP 协议理解
- 工具服务设计

### 5.3 单 Agent 型项目

代表项目：

- `LangGraph聊天Agent实战`
- `学习资料整理Agent实战`

适合补齐：

- 任务路由
- 状态和记忆
- 工具回注
- 节点编排

### 5.4 多 Agent / 分工协作型项目

代表项目：

- `架构师与工人Agent实战`
- `Multi-Agent数字员工实战`

适合补齐：

- 任务拆解
- 角色分工
- 协作协议
- 复杂流程控制

## 6. 如何使用这一章

建议每做一个项目，都至少做下面 4 件事：

1. 写清这个项目解决什么问题
2. 写清为什么这里需要 LLM / Agent，而不只是规则代码
3. 记录 3 个最容易失败的点
4. 做一次最小复盘，说明如果重做会优先改哪里

更推荐的做法是：

- 每完成 1 个项目，就回到 `06-评测与优化`
- 为这个项目补一份最小评测集
- 保留失败样本和修改记录

这样项目才会从“做过”升级为“真的学会了”

## 7. 总结与下一步建议

项目实战这一章的价值，不是让你把仓库里的代码都跑一遍，而是让你通过一条由简入繁的路径，真正理解：

- 什么能力适合先学
- 什么项目适合先做
- 什么复杂度应该后置
- 一个项目为什么能跑、又为什么会失败

建议你现在按下面顺序开始：

1. 先读 [项目练习清单.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/项目练习清单.md)
2. 先选 1 个 RAG 或 MCP 项目
3. 再进入 1 个单 Agent 项目
4. 最后再挑战多 Agent 项目

