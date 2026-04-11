# 智能金融投研助手

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

这个项目面向金融 PDF 投研场景，目标是让你系统学习 RAG 在复杂文档场景里的**完整链路**与工程难点。

目标问题示例：

- 某公司去年的毛利率变化趋势及其原因？
- 过去三年研发投入变化与净利润趋势是否一致？
- 哪个业务板块增长最快？毛利率最高的是哪个？
- 公司面临哪些主要经营风险？

## 2. 为什么这个项目适合当前学习阶段

这个项目覆盖了 RAG 的**完整端到端链路**：

- 数据清洗与结构化切片
- 真实 Embedding 模型（BGE）向量化
- FAISS 向量检索 + BM25 关键词检索
- RRF 混合检索与交叉编码器重排序
- LLM 查询改写与答案生成

不是停留在"固定切片 + 向量检索"的最小 Demo，而是一个可运行的完整 RAG 系统。

## 3. 前置知识

建议先完成：

1. [03-RAG/README.md](../../03-RAG/README.md)
2. [06-评测与优化/README.md](../../06-评测与优化/README.md)

## 4. 学习目标

完成这个项目后，你应该能够：

1. 理解金融 RAG 系统从数据清洗到答案生成的完整链路
2. 理解 BM25 + 向量混合检索 + Rerank 的工程实现
3. 理解查询改写和答案生成中 prompt 设计的关键点
4. 能够独立搭建一个端到端的 RAG 系统

## 5. 核心架构

### 数据流

```text
用户 Query
    │
    ▼
QueryRewriter（LLM 查询改写）
    │ 生成 1-3 个改写 query
    ▼
HybridRetriever
    ├── BM25Retriever（jieba 分词 + BM25Okapi）
    ├── FAISSVectorStore（BGE embedding + 余弦相似度）
    └── RRF 融合
    │
    ▼
CrossEncoderReranker（交叉编码器精排）
    │
    ▼
AnswerGenerator（LLM 答案生成，带引用溯源）
    │
    ▼
结构化回答（含页码、章节引用）
```

### 项目目录结构

```text
智能金融投研助手-RAG/
├── README.md
├── requirements.txt
├── .env.example                        # API key 配置模板
├── data/
│   ├── sample_blocks.json              # 模拟金融年报数据（40+ block）
│   └── sample_queries.json             # 测试查询集
├── app/
│   ├── config.py                       # 项目配置（切片/检索/重排/LLM 参数）
│   ├── embeddings/
│   │   ├── base.py                     # EmbeddingModel 协议
│   │   ├── simple_embedding.py         # 教学占位模型
│   │   └── bge_embedding.py            # 真实 BGE embedding
│   ├── ingest/
│   │   ├── models.py                   # Block / Chunk 数据模型
│   │   ├── cleaner.py                  # 金融文本清洗器
│   │   ├── chunker.py                  # 结构优先 + 语义辅助切片器
│   │   └── parser_stub.py             # PDF 解析占位（可替换）
│   ├── retrieval/
│   │   ├── vector_store.py             # FAISS 向量存储与检索
│   │   ├── bm25_retriever.py           # BM25 关键词检索
│   │   └── hybrid_retriever.py         # RRF 混合检索
│   ├── rerank/
│   │   └── cross_encoder_reranker.py   # 交叉编码器重排序
│   ├── query/
│   │   └── query_rewriter.py           # LLM 查询改写
│   └── generation/
│       └── answer_generator.py         # LLM 答案生成
└── scripts/
    ├── run_chunking_demo.py            # 数据清洗 + 切片 Demo
    ├── run_indexing_demo.py             # 索引构建 Demo
    ├── run_retrieval_demo.py            # 检索 + 重排序 Demo
    └── run_pipeline_demo.py            # 端到端 Pipeline Demo
```

## 6. 运行方式

### 安装依赖

```bash
cd 07-项目实战/智能金融投研助手-RAG
pip install -r requirements.txt
```

### 渐进式运行（推荐）

```bash
# 步骤 1：看清洗和切片效果
python scripts/run_chunking_demo.py

# 步骤 2：构建索引（首次运行会下载 BGE 模型 ~90MB）
python scripts/run_indexing_demo.py

# 步骤 3：测试检索和重排序（首次运行会下载 reranker 模型 ~560MB）
python scripts/run_retrieval_demo.py

# 步骤 4：端到端问答（可选配置 API key 获得完整体验）
python scripts/run_pipeline_demo.py

# 或指定查询
python scripts/run_pipeline_demo.py "公司去年毛利率变化了多少？"
```

### API Key 配置（可选）

```bash
# 配置后可体验查询改写和 LLM 答案生成
export OPENAI_API_KEY=your-key
export OPENAI_BASE_URL=https://api.openai.com/v1  # 或其他兼容 API
export OPENAI_MODEL=gpt-4o-mini
```

不配置 API key 也可以运行到检索阶段，答案生成会降级为直接展示检索结果。

## 7. 推荐观察点

### 数据清洗与切片

1. 标题是不是强边界？表格是不是单独成块？
2. 相邻段落是否真的属于同一语义单元？
3. chunk 上是否保留了页码、标题层级、块类型等 metadata？

### 检索与重排序

4. 向量检索和 BM25 的结果有什么不同？各自擅长什么？
5. 混合检索（RRF）是否比单一检索更稳定？
6. 重排序前后的排名变化大吗？对最终答案影响如何？

### 查询改写与答案生成

7. 查询改写生成了哪些角度？是否补全了隐含条件？
8. 答案是否准确引用了原文数据？是否有幻觉？
9. 引用的页码和章节是否正确？

## 8. 常见失败原因

金融 RAG 最常见的失败点包括：

1. **切片粒度不当**：切太细丢失上下文，切太粗引入噪声
2. **只用向量检索**：精确数值和专有名词匹配不上，需要 BM25 配合
3. **不做重排序**：初筛结果中排名靠前的不一定是最相关的
4. **查询不改写**：用户口语化表达直接检索，召回率低
5. **答案不引用出处**：无法验证回答是否基于真实文档

## 9. 练习任务

1. **替换 PDF 解析器**：用 PyMuPDF 替换 `parser_stub.py`，解析一份真实金融年报
2. **调整检索权重**：修改 `vector_weight` 参数，观察 BM25 和向量检索的权重变化对结果的影响
3. **换一个 Embedding 模型**：尝试 `BAAI/bge-base-zh-v1.5` 或 `text2vec-large-chinese`，对比效果
4. **添加评测脚本**：基于 `sample_queries.json`，编写自动化评测脚本，检查检索是否命中预期章节

## 10. 下一步延伸

如果你已经理解了这个项目的完整链路，下一步建议：

1. 学习 Agentic RAG：让 Agent 自主决定检索策略（见 `agent-agentic-rag/` 项目）
2. 用 LangGraph 串联整个 RAG 流程，增加条件路由
3. 接入 RAGAS 等评估框架，构建自动化评测体系

一句话总结：

**RAG 系统的上限，取决于数据质量、检索精度和生成约束三者的协同——哪个环节弱，系统就弱。**
