# 03. RAG

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

`03-RAG` 解决的是：

**当答案依赖外部资料时，怎样把正确的信息在正确的时候送到模型面前。**

它不是单纯的“接一个向量库”，而是一整套信息供给系统。

## 2. 适用人群

适合：

- 已完成 LLM 和 Prompt 基础，准备做知识问答和企业检索的人
- 做过简单 RAG Demo，但还不会拆解效果问题的人

## 3. 学习目标

学完这一章后，你应该能够：

1. 理解 RAG 为什么能降低幻觉，以及边界在哪里
2. 理解离线数据处理、Embedding、召回、重排、查询理解的关系
3. 区分数据问题、检索问题、排序问题、生成问题
4. 初步具备设计企业知识库问答链路的能力
5. 用工程视角看 RAG 的优化方向

## 4. 推荐阅读顺序

1. [1.RAG系统学习讲义.md](/Users/chenmingdong01/Documents/AI/agent/03-RAG/1.RAG系统学习讲义.md)
2. [2.企业RAG中的离线数据清洗与Embedding实践.md](/Users/chenmingdong01/Documents/AI/agent/03-RAG/2.企业RAG中的离线数据清洗与Embedding实践.md)
3. [3.Embedding模型怎么选：从效果、成本到部署约束.md](/Users/chenmingdong01/Documents/AI/agent/03-RAG/3.Embedding模型怎么选：从效果、成本到部署约束.md)
4. [4.为什么RAG需要重排序：Rerank原理、价值与选型.md](/Users/chenmingdong01/Documents/AI/agent/03-RAG/4.为什么RAG需要重排序：Rerank原理、价值与选型.md)
5. [5.RAG查询理解：实体提取、Query改写与检索路由.md](/Users/chenmingdong01/Documents/AI/agent/03-RAG/5.RAG查询理解：实体提取、Query改写与检索路由.md)

## 5. 本章核心问题

建议始终带着下面几个判断框架阅读：

1. 这是数据问题，还是检索问题
2. 这是召回不够，还是排序不对
3. 这是切分问题，还是查询理解问题
4. 这是模型不行，还是给模型的证据不对

## 6. 学完后的产出

建议至少完成下面 3 个产出：

1. 一个最小 RAG 系统
2. 一张 RAG 链路问题排查图
3. 一次失败案例复盘

## 7. 常见误区

- 误以为 RAG 只是“加一个向量库”
- 误以为检索差一定是 Embedding 模型不够强
- 误以为模型回答差就一定是生成层问题
- 误以为企业 RAG 的关键在框架，而不是数据治理

## 8. 总结与下一步

这一章的目标，是把你从“能搭一个问答 Demo”推进到“能按链路定位问题”。

学完后，建议继续进入 [05-Agent/README.md](/Users/chenmingdong01/Documents/AI/agent/05-Agent/README.md) 和 [06-评测与优化/README.md](/Users/chenmingdong01/Documents/AI/agent/06-评测与优化/README.md)，把信息供给和系统决策、评测闭环串起来。
