# 记忆增强 Agent

## 项目定位

这是一个基于 LangGraph 构建的**记忆增强对话 Agent**，实现了三层记忆架构：

| 记忆层 | 机制 | 作用 |
|--------|------|------|
| 短期记忆 | LLM 摘要压缩 | 控制 context window，保留对话连续性 |
| 长期记忆 | FAISS 语义检索 + JSON 持久化 | 跨会话记住用户信息和偏好 |
| 工作记忆 | 结构化 scratch pad | 跟踪当前任务状态 |

## 图拓扑

```
START → load_memory → chat → extract_and_store → compress_if_needed → END
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 API key
export OPENAI_API_KEY=your-key

# 交互式对话
python scripts/run_chat.py

# 自动演示（运行预设测试对话）
python scripts/run_memory_demo.py
```

## 项目结构

```
agent-memory-enhanced/
├── README.md
├── requirements.txt
├── .env.example
├── data/
│   ├── sample_conversations.json   # 测试对话
│   └── memory_store/               # 长期记忆持久化目录（自动创建）
├── app/
│   ├── config.py                   # 配置
│   ├── llm_client.py               # OpenAI 兼容 API 客户端
│   ├── prompts.py                  # 所有 prompt 集中管理
│   ├── state.py                    # LangGraph 状态定义
│   ├── memory/
│   │   ├── short_term.py           # 短期记忆（LLM 压缩）
│   │   ├── long_term.py            # 长期记忆（FAISS + JSON）
│   │   └── working.py              # 工作记忆（scratch pad）
│   ├── nodes.py                    # 4 个 LangGraph 节点
│   └── graph.py                    # 图构建与执行
└── scripts/
    ├── run_chat.py                 # 交互式对话入口
    └── run_memory_demo.py          # 自动演示
```

## 交互命令

在 `run_chat.py` 中：
- `/quit` — 退出
- `/memory` — 查看当前记忆状态
- `/clear` — 清空所有记忆

## 配套学习

- 理论基础：`05-Agent/7.Agent记忆系统.md`
- 实战教学：`07-项目实战/8.记忆增强Agent实战.md`
