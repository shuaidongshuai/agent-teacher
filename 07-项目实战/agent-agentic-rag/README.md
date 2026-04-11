# Agentic RAG 金融投研助手

## 目录

1. [项目解决什么问题](#1-项目解决什么问题)
2. [为什么这个项目适合当前学习阶段](#2-为什么这个项目适合当前学习阶段)
3. [前置知识](#3-前置知识)
4. [学习目标](#4-学习目标)
5. [核心架构](#5-核心架构)
6. [运行方式](#6-运行方式)
7. [推荐观察点](#7-推荐观察点)
8. [常见失败原因](#8-常见失败原因)
9. [练习任务](#9-练习任务)
10. [下一步延伸](#10-下一步延伸)

## 1. 项目解决什么问题

传统 RAG 是一个固定管道：query → 检索 → 重排 → 生成。无论什么问题，都走同样的流程。

但真实的投研分析场景中，问题往往是复杂的、多维的：

- "分析公司盈利能力变化趋势，并解释原因，同时对比研发投入" — 需要跨多个章节
- "从收入结构和成本变化两个维度，评估经营风险" — 一次检索不够，需要多轮
- "毛利率最高的业务板块是哪个？" — 简单问题，一次检索就够

**Agentic RAG = Agent 自主控制 RAG 管道。** Agent 决定：

- 要不要检索？
- 用什么 query 检索？
- 检索结果够不够？不够的话换什么角度补充？
- 什么时候停下来生成答案？

## 2. 为什么这个项目适合当前学习阶段

这个项目是 Agent 和 RAG 两大方向的**融合点**：

- 用 LangGraph 构建带条件循环的图（不是简单线性流程）
- Agent 的每个决策都基于 LLM 判断（不是写死的 if-else）
- 有明确的安全控制（最大轮数、LLM 调用上限）防止 Agent 失控
- 所有推理过程可观测（execution_log 记录每一步）

## 3. 前置知识

建议先完成：

1. [03-RAG/README.md](../../03-RAG/README.md) — RAG 基础
2. [05-Agent/README.md](../../05-Agent/README.md) — Agent 架构
3. [智能金融投研助手-RAG](../智能金融投研助手-RAG/README.md) — 固定管道 RAG

## 4. 学习目标

完成这个项目后，你应该能够：

1. 理解 Agentic RAG 与固定管道 RAG 的核心区别
2. 掌握 LangGraph 中条件边和循环的使用
3. 理解 Agent 如何评估检索结果并做出路由决策
4. 能够设计和调优 Agent 的 prompt（分析、评估、改写）
5. 理解 Agent 安全控制的必要性（最大轮数、调用上限）

## 5. 核心架构

### LangGraph 拓扑

```text
START → analyze_query → retrieve → evaluate_results ─┬─→ refine_query → retrieve
                                                      ├─→ retrieve（换 query 直接重试）
                                                      └─→ generate_answer → format_output → END
```

### 节点说明


| 节点             | 是否调用 LLM | 功能                             |
| ---------------- | ------------ | -------------------------------- |
| analyze_query    | 是           | 分析问题复杂度，制定初始检索策略 |
| retrieve         | 否           | 执行混合检索 + 重排序            |
| evaluate_results | 是           | 评估信息是否充分，决定下一步     |
| refine_query     | 是           | 根据缺失信息生成新的检索 query   |
| generate_answer  | 是           | 基于累积上下文生成答案           |
| format_output    | 否           | 整理输出和执行日志               |

### 安全控制

- 最多 3 轮检索（`max_retrieval_rounds`）
- 最多 8 次 LLM 调用（`max_llm_calls`）
- 达到上限后强制用已有信息生成答案

### 项目目录

```text
agent-agentic-rag/
├── README.md
├── requirements.txt
├── .env.example
├── data/
│   ├── sample_blocks.json          # 金融年报数据
│   └── sample_queries.json         # 测试查询
├── app/
│   ├── config.py                   # 配置
│   ├── llm_client.py               # LLM API 客户端
│   ├── prompts.py                  # 集中管理的 prompt
│   ├── state.py                    # LangGraph 状态定义
│   ├── nodes.py                    # 图节点实现
│   ├── graph.py                    # LangGraph 图构建
│   ├── knowledge_base.py           # 知识库封装
│   └── rag/                        # RAG 能力模块
│       ├── bge_embedding.py
│       ├── vector_store.py
│       ├── bm25_retriever.py
│       ├── hybrid_retriever.py
│       └── reranker.py
├── scripts/
│   ├── build_index.py              # 构建索引
│   └── run_agent.py                # 主入口
└── output/
    └── last_run.json               # 最近一次运行结果
```

## 6. 运行方式

### 安装依赖

```bash
cd 07-项目实战/agent-agentic-rag
pip install -r requirements.txt
```

### 运行

```bash
# 配置 API key（必需）
export OPENAI_API_KEY=your-key

# 构建索引（首次运行）
python scripts/build_index.py

# 运行 Agent
python scripts/run_agent.py

# 或指定查询
python scripts/run_agent.py "请分析公司的盈利能力变化趋势"
```

## 7. 推荐观察点

1. **analyze_query 的输出**：LLM 判断的复杂度和初始检索策略是否合理？
2. **检索轮数**：简单问题是否一轮就结束？复杂问题是否需要多轮？
3. **evaluate_results 的决策**：LLM 判断"信息是否充分"的理由是否可信？
4. **refine_query 的改写**：新 query 是否针对缺失信息？有没有重复已经搜过的？
5. **query_history**：所有使用过的 query 是否在不断聚焦？
6. **accumulated_contexts**：多轮检索后累积的上下文是否覆盖了问题的各个维度？
7. **安全控制**：达到最大轮数后 Agent 是否优雅地生成了答案？

## 8. 常见失败原因

1. **evaluate_results 判断不准**：LLM 认为"信息足够"但其实缺关键数据，或反之
2. **refine_query 与原 query 雷同**：改写后的 query 没有真正换角度，检索到重复内容
3. **过度检索**：3 轮检索都检索了相似内容，没有补充新信息
4. **上下文过长**：累积太多上下文，影响答案生成质量
5. **prompt 设计不当**：评估 prompt 没有给出清晰的决策标准

## 9. 练习任务

1. **对比实验**：用同样的问题分别运行固定管道 RAG 和 Agentic RAG，对比答案质量和检索轨迹
2. **调整 prompt**：修改 `evaluate_results` 的 prompt，观察 Agent 的决策敏感度变化
3. **增加检索策略**：让 Agent 能选择"只用 BM25"或"只用向量"而不是始终用混合检索
4. **添加多知识库支持**：扩展 Agent，让它能选择从不同的知识库检索（如年报 vs 研报）

## [](https://)10. 下一步延伸

1. 添加 Self-RAG 机制：Agent 对自己生成的答案做自检（是否有幻觉、是否遗漏）
2. 接入 Web 搜索：当本地知识库不够时，Agent 决定去搜索外部信息
3. 多 Agent 协作：一个 Agent 负责检索策略，一个负责答案生成，一个负责质量审核
4. 接入评估框架：用 RAGAS 或 LLM-as-Judge 自动评测 Agent 的检索和回答质量

一句话总结：

**Agentic RAG 的核心不是"更多轮检索"，而是"Agent 自主判断何时检索、检索什么、何时停止"。**
