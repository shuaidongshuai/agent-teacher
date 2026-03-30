# LLM 与 Agent 工程化学习资料库

这是一个面向工程转型学习者的 AI 教学项目。  
目标不是堆资料，而是把 `LLM -> Prompt -> 工具调用 -> RAG -> Agent -> 评测 -> 项目实战 -> 面试表达` 串成一条可执行的学习主线。

## 适合谁

这套内容尤其适合下面三类学习者：

1. 已经会写一些业务代码，想系统进入 AI 应用工程的人
2. 做过 Demo，但还没形成完整架构判断和优化方法的人
3. 想把知识学习、项目实战、复盘表达串成一套对外课程的人

## 阅读分层

为了避免“看了很多，但不知道先学什么”，整个仓库按 4 层使用。

### 必修主线

建议严格按下面顺序推进：

1. [00-总览](/Users/chenmingdong01/Documents/AI/agent/00-总览/README.md)
2. [01-LLM基础](/Users/chenmingdong01/Documents/AI/agent/01-LLM基础/README.md)
3. [02-Prompt工程](/Users/chenmingdong01/Documents/AI/agent/02-Prompt工程/README.md)
4. [04-工具调用与函数调用](/Users/chenmingdong01/Documents/AI/agent/04-工具调用与函数调用/README.md)
5. [03-RAG](/Users/chenmingdong01/Documents/AI/agent/03-RAG/README.md)
6. [05-Agent](/Users/chenmingdong01/Documents/AI/agent/05-Agent/README.md)
7. [06-评测与优化](/Users/chenmingdong01/Documents/AI/agent/06-评测与优化/README.md)
8. [07-项目实战](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/README.md)
9. [11-模拟面试](/Users/chenmingdong01/Documents/AI/agent/11-模拟面试/README.md)

这条顺序保持当前仓库的工程路线，不把 `03-RAG` 提前到 `04-工具调用与函数调用` 前面。原因是：

- 工具调用是 Agent 的基础能力之一
- RAG 本质上也是外部信息接入机制
- 先掌握“让模型安全连接外部能力”，再学“让模型稳定获得外部知识”，工程上更稳

### 可选辅助模块

下面 3 个目录默认视为辅助模块，不替代主线章节：

- [08-资料收集](/Users/chenmingdong01/Documents/AI/agent/08-资料收集/README.md)：先收集、再筛选、再转写
- [09-术语表](/Users/chenmingdong01/Documents/AI/agent/09-术语表/README.md)：把概念翻译成自己的语言
- [10-每周计划](/Users/chenmingdong01/Documents/AI/agent/10-每周计划/README.md)：把学习变成持续推进的节奏

### 项目穿插节点

建议不要等理论全部看完才做项目，而是在 3 个节点穿插：

1. 学完 `02 + 04` 后，先做一个最小工具调用或 MCP 项目
2. 学完 `03` 后，做一个 RAG 项目并尝试写出失败复盘
3. 学完 `05 + 06` 后，再进入单 Agent 和多 Agent 项目

对应入口：

- [07-项目实战/README.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/README.md)

### 面试回看节点

`11-模拟面试` 不建议最后才看。更有效的方式是：

1. 学完 `01-02` 后做一次基础口头复述
2. 学完 `03-05` 后做一次模块化自测
3. 项目完成后再做一轮项目与评测问答

## 推荐学习路径

如果你是工程背景转型到 AI，推荐按下面节奏推进：

### 第一阶段：建立底层认知

对应目录：

- [00-总览](/Users/chenmingdong01/Documents/AI/agent/00-总览/README.md)
- [01-LLM基础](/Users/chenmingdong01/Documents/AI/agent/01-LLM基础/README.md)
- [02-Prompt工程](/Users/chenmingdong01/Documents/AI/agent/02-Prompt工程/README.md)

建议产出：

- 一份自己的 LLM 原理解释稿
- 一套 Prompt 模板
- 一个结构化输出小 Demo

### 第二阶段：进入能力接入

对应目录：

- [04-工具调用与函数调用](/Users/chenmingdong01/Documents/AI/agent/04-工具调用与函数调用/README.md)
- [03-RAG](/Users/chenmingdong01/Documents/AI/agent/03-RAG/README.md)

建议产出：

- 一个工具调用 Demo
- 一个最小 RAG 系统
- 一张“效果差时怎么定位”的链路图

### 第三阶段：进入 Agent 设计

对应目录：

- [05-Agent](/Users/chenmingdong01/Documents/AI/agent/05-Agent/README.md)
- [07-项目实战](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/README.md)

建议产出：

- 一个单 Agent 项目
- 一份架构选型说明
- 一次失败案例复盘

### 第四阶段：进入评测与表达

对应目录：

- [06-评测与优化](/Users/chenmingdong01/Documents/AI/agent/06-评测与优化/README.md)
- [11-模拟面试](/Users/chenmingdong01/Documents/AI/agent/11-模拟面试/README.md)

建议产出：

- 一套最小评测集
- 一份回归验证记录
- 一轮面试问答整理

## 你会在仓库里看到什么

- `00-总览`：整套课的导航页、路线图和知识地图
- `01-LLM基础`：模型原理、Transformer、Token、训练与采样
- `02-Prompt工程`：任务表达、约束设计、few-shot、结构化输出、调试
- `03-RAG`：数据清洗、Embedding、召回、重排、查询理解
- `04-工具调用与函数调用`：函数调用、参数设计、错误处理、MCP
- `05-Agent`：架构选型、稳定性、观测与生产难点
- `06-评测与优化`：Prompt、RAG、Agent 的评测与优化闭环
- `07-项目实战`：从 MCP、RAG 到单 Agent、多 Agent 的实战项目
- `08-资料收集`：外部资料的收集与筛选入口
- `09-术语表`：概念内化区
- `10-每周计划`：节奏控制与复盘入口
- `11-模拟面试`：表达训练与查漏补缺
- `99-内容维护`：后续新增教学内容的模板和质检规范

## 使用建议

建议把整个仓库当成一门“可交付课程”来维护，而不是私人笔记：

1. 新资料先进入 [08-资料收集](/Users/chenmingdong01/Documents/AI/agent/08-资料收集/README.md)
2. 消化后再转成正式章节文档
3. 重要术语同步写进 [09-术语表](/Users/chenmingdong01/Documents/AI/agent/09-术语表/README.md)
4. 每周用 [10-每周计划](/Users/chenmingdong01/Documents/AI/agent/10-每周计划/README.md) 做推进和复盘
5. 新增文档前先看 [99-内容维护/README.md](/Users/chenmingdong01/Documents/AI/agent/99-内容维护/README.md)

## 总结与下一步

如果你是第一次进入这个仓库，建议现在按下面顺序开始：

1. 先读 [00-总览/README.md](/Users/chenmingdong01/Documents/AI/agent/00-总览/README.md)
2. 再进入 [01-LLM基础/README.md](/Users/chenmingdong01/Documents/AI/agent/01-LLM基础/README.md)
3. 学完基础后进入 [02-Prompt工程/README.md](/Users/chenmingdong01/Documents/AI/agent/02-Prompt工程/README.md)
4. 然后进入 [04-工具调用与函数调用/README.md](/Users/chenmingdong01/Documents/AI/agent/04-工具调用与函数调用/README.md)
5. 再根据目标推进到 [03-RAG/README.md](/Users/chenmingdong01/Documents/AI/agent/03-RAG/README.md)、[05-Agent/README.md](/Users/chenmingdong01/Documents/AI/agent/05-Agent/README.md) 和 [07-项目实战/README.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/README.md)
