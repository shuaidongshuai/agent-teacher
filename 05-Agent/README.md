# 05. Agent

## 目录

1. [本章定位](#1-本章定位)
2. [适用人群](#2-适用人群)
3. [学习目标](#3-学习目标)
4. [推荐阅读顺序](#4-推荐阅读顺序)
5. [本章核心问题](#5-本章核心问题)
6. [学完后的产出](#6-学完后的产出)
7. [常见误区](#7-常见误区)
8. [总结与下一步](#8-总结与下一步)

## 1. 本章定位

`05-Agent` 解决的是：

**当任务不再是单步回答，而是需要持续判断、调用工具、读取状态、处理失败时，系统该怎么设计。**

这一章的重点不是“让 Agent 看起来更聪明”，而是理解它为什么容易失控，以及怎样做出工程上可用的 Agent。

## 2. 适用人群

适合：

- 已经理解 LLM、Prompt、工具调用、RAG，准备进入多步决策系统的人
- 做过 Agent Demo，但还没建立架构选型和稳定性意识的人

## 3. 学习目标

学完这一章后，你应该能够：

1. 理解 Agent 的闭环、边界和适用场景
2. 区分 Workflow、Router、ReAct、Multi-Agent 的差异
3. 理解状态管理、记忆、重试、人工兜底的重要性
4. 知道从 Demo 到上线为什么会变难
5. 具备观察、评测和持续优化 Agent 的基本意识

## 4. 推荐阅读顺序

1. [1.Agent深入学习讲义.md](/Users/chenmingdong01/Documents/AI/agent/05-Agent/1.Agent深入学习讲义.md)
2. [2.生产级Agent有哪些难点：从Demo到上线.md](/Users/chenmingdong01/Documents/AI/agent/05-Agent/2.生产级Agent有哪些难点：从Demo到上线.md)
3. [3.Agent系统怎么选型：Workflow、Router、ReAct与Multi-Agent.md](/Users/chenmingdong01/Documents/AI/agent/05-Agent/3.Agent系统怎么选型：Workflow、Router、ReAct与Multi-Agent.md)
4. [4.Agent稳定性设计：工具调用、状态管理、重试与人工兜底.md](/Users/chenmingdong01/Documents/AI/agent/05-Agent/4.Agent稳定性设计：工具调用、状态管理、重试与人工兜底.md)
5. [5.Agent观测与评测：如何定位问题并持续优化.md](/Users/chenmingdong01/Documents/AI/agent/05-Agent/5.Agent观测与评测：如何定位问题并持续优化.md)

## 5. 本章核心问题

建议始终围绕下面 4 个问题：

1. 这个任务真的需要 Agent 吗
2. 该用什么架构，复杂度值不值得
3. 怎么让它稳定工作，而不是一碰就碎
4. 怎么知道它错在哪一层

## 6. 学完后的产出

建议产出：

1. 一个最小单 Agent Demo
2. 一份 Agent 架构选型说明
3. 一份失败案例复盘

## 7. 常见误区

- 误以为多 Agent 一定比单 Agent 更高级
- 误以为 Agent 只是多轮对话
- 误以为模型够强就不需要状态和兜底设计
- 误以为 Agent 效果差只能继续调 Prompt

## 8. 总结与下一步

这一章的核心不是“让系统更炫”，而是建立“多步任务系统设计”的工程视角。

学完后，建议进入 [06-评测与优化/README.md](/Users/chenmingdong01/Documents/AI/agent/06-评测与优化/README.md) 和 [07-项目实战/README.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/README.md)，把 Agent 架构和真实项目实践串起来。
