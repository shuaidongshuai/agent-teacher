# Prompt 工程

## 学习目标

这部分适合已经了解 LLM 基本原理，并希望真正把模型“用顺手”的学习者。

学完这一章后，你应该能够：

1. 理解 Prompt 工程不是“咒语学”，而是任务表达与上下文设计
2. 学会把模糊需求改写成模型更容易执行的指令
3. 学会通过角色、目标、约束和输出格式降低跑偏
4. 学会用 few-shot 示例提升一致性
5. 学会定位失败原因，并持续迭代 Prompt

## 目录

1. [这部分学什么](#1-这部分学什么)
2. [为什么 Prompt 工程重要](#2-为什么-prompt-工程重要)
3. [推荐学习顺序](#3-推荐学习顺序)
4. [文档列表](#4-文档列表)
5. [常见学习误区](#5-常见学习误区)
6. [总结与下一步](#6-总结与下一步)

---

## 1. 这部分学什么

如果说 `01-LLM基础` 解决的是“模型为什么会这样工作”，那 `02-Prompt工程` 解决的是：

**面对一个真实任务，怎样把话说清楚，才能让模型更稳定、更可控地完成它。**

这一章不会把 Prompt 写成玄学技巧，而是把它拆成几个可学习、可复用的部分：

- 任务表达
- 约束设计
- 示例设计
- 输出结构设计
- 调试与迭代

---

## 2. 为什么 Prompt 工程重要

很多初学者会觉得：

“只要模型足够强，Prompt 就不重要了。”

这其实不对。

模型再强，也仍然要面对这些问题：

- 任务目标不清
- 背景上下文不足
- 输出格式不明确
- 多个要求互相冲突
- 用户真实需求没有被拆解

Prompt 工程的价值，不在于“骗模型”，而在于：

**把任务条件组织得更适合模型理解和执行。**

所以它更像：

- 面向模型的任务说明书
- 面向应用的输入接口设计
- 面向失败案例的持续优化过程

---

## 3. 推荐学习顺序

建议按下面顺序阅读：

1. [Prompt基础模式](/Users/chenmingdong01/Documents/AI/agent/02-Prompt工程/Prompt基础模式.md)
2. [角色-目标-约束-输出格式](/Users/chenmingdong01/Documents/AI/agent/02-Prompt工程/角色-目标-约束-输出格式.md)
3. [Few-shot示例设计](/Users/chenmingdong01/Documents/AI/agent/02-Prompt工程/Few-shot示例设计.md)
4. [结构化输出](/Users/chenmingdong01/Documents/AI/agent/02-Prompt工程/结构化输出.md)
5. [Prompt调试记录](/Users/chenmingdong01/Documents/AI/agent/02-Prompt工程/Prompt调试记录.md)

这个顺序背后的逻辑是：

- 先理解 Prompt 的基本作用方式
- 再学习怎样把任务说清楚
- 然后学习怎样用示例稳定行为
- 接着学习怎样让输出更可解析
- 最后学习怎样面对失败并迭代

---

## 4. 文档列表

### 4.1 [Prompt基础模式](/Users/chenmingdong01/Documents/AI/agent/02-Prompt工程/Prompt基础模式.md)

帮助你建立最核心的直觉：

- Prompt 到底在改变什么
- 为什么同一个任务换个说法结果会变
- 常见基础模式有哪些

### 4.2 [角色-目标-约束-输出格式](/Users/chenmingdong01/Documents/AI/agent/02-Prompt工程/角色-目标-约束-输出格式.md)

这是最实用的一篇，重点讲怎样把任务写得更完整。

### 4.3 [Few-shot示例设计](/Users/chenmingdong01/Documents/AI/agent/02-Prompt工程/Few-shot示例设计.md)

重点讲什么时候该给例子、给什么例子、例子为什么会影响结果。

### 4.4 [结构化输出](/Users/chenmingdong01/Documents/AI/agent/02-Prompt工程/结构化输出.md)

重点讲如何让模型输出更适合程序处理、评测和自动化。

### 4.5 [Prompt调试记录](/Users/chenmingdong01/Documents/AI/agent/02-Prompt工程/Prompt调试记录.md)

重点讲遇到失败时不要乱改，而是学会系统定位问题。

---

## 5. 常见学习误区

### 5.1 误区一：Prompt 工程就是会写几句漂亮的话

不是。真正重要的是任务拆解、约束表达、上下文设计和失败排查。

### 5.2 误区二：Prompt 越长越好

不一定。长 Prompt 可能更完整，也可能更啰嗦、更冲突、更稀释重点。

### 5.3 误区三：只要多试几次，总能试出一个好 Prompt

短期可能有用，但不可复用、不可解释，也不利于工程化。

### 5.4 误区四：Prompt 问题和模型问题是同一件事

不是。效果差可能来自：

- Prompt 不清
- 示例不对
- 参数不稳
- 上下文不够
- 任务本身超出模型能力

---

## 6. 总结与下一步

这部分最值得记住的一句话是：

**Prompt 工程的本质，不是写神秘指令，而是把任务、上下文和输出要求组织成模型更容易正确执行的形式。**

建议你先从 [Prompt基础模式](/Users/chenmingdong01/Documents/AI/agent/02-Prompt工程/Prompt基础模式.md) 开始，再一路读到 [结构化输出](/Users/chenmingdong01/Documents/AI/agent/02-Prompt工程/结构化输出.md) 和 [Prompt调试记录](/Users/chenmingdong01/Documents/AI/agent/02-Prompt工程/Prompt调试记录.md)。

读完后，下一步建议进入 [工具调用与函数调用](/Users/chenmingdong01/Documents/AI/agent/04-工具调用与函数调用/README.md)，因为很多真实应用已经不只是“把 Prompt 写好”，而是要让模型稳定地产生可执行动作。
