# 评测 Pipeline

## 项目定位

这是一个**可运行的评测工程化项目**，将 `06-评测与优化` 中的评测理论落地为代码。支持 Prompt、RAG、Agent 三类评测场景。

## 架构

```
评测集 JSON → DataLoader → EvalRunner → Evaluators → Report（终端 + JSON）
```

## 4 个评估器

| 评估器 | 说明 | 是否需要 LLM |
|--------|------|-------------|
| `ExactMatchEvaluator` | 精确匹配 / 包含匹配 / 关键词匹配 | 否 |
| `LLMJudgeEvaluator` | LLM-as-Judge 5 分制打分 | 是 |
| `RAGMetricsEvaluator` | Recall@K, MRR, Context Precision | 否 |
| `AgentMetricsEvaluator` | 任务完成率, 工具调用匹配度, 步数效率 | 部分（任务完成度） |

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行 Prompt 评测（无需 API key）
python scripts/run_prompt_eval.py

# 运行 RAG 评测
python scripts/run_rag_eval.py

# 运行 Agent 评测
python scripts/run_agent_eval.py

# 启用 LLM Judge（可选）
export OPENAI_API_KEY=your-key
export OPENAI_BASE_URL=https://api.openai.com/v1  # 可选，默认 OpenAI
python scripts/run_prompt_eval.py
```

## 项目结构

```
eval-pipeline/
├── README.md
├── requirements.txt
├── .env.example
├── data/
│   ├── prompt_eval_set.json        # Prompt 评测集（15 条）
│   ├── rag_eval_set.json           # RAG 评测集（10 条）
│   └── agent_eval_set.json         # Agent 评测集（8 条）
├── app/
│   ├── config.py                   # 配置中心
│   ├── llm_client.py               # OpenAI 兼容 API 客户端
│   ├── data_loader.py              # 评测集加载与校验
│   ├── evaluators/
│   │   ├── base.py                 # BaseEvaluator 协议 + EvalResult
│   │   ├── exact_match.py          # 精确匹配评估器
│   │   ├── llm_judge.py            # LLM-as-Judge 评估器
│   │   ├── rag_metrics.py          # RAG 检索质量评估器
│   │   └── agent_metrics.py        # Agent 行为质量评估器
│   ├── runner.py                   # 评测运行器
│   └── report.py                   # 报告生成（终端 + JSON）
├── scripts/
│   ├── run_prompt_eval.py          # Prompt 评测入口
│   ├── run_rag_eval.py             # RAG 评测入口
│   └── run_agent_eval.py           # Agent 评测入口
└── output/                         # 评测报告输出目录
```

## 评测集格式

评测集使用 JSON 格式，每种评测场景的数据结构略有不同：

### Prompt 评测集

```json
{
  "id": "prompt_001",
  "input": "请用一句话总结...",
  "reference": "参考答案",
  "prediction": "模型输出",
  "evaluators": ["exact_match", "llm_judge"],
  "metadata": {"category": "summarization", "difficulty": "easy"}
}
```

### RAG 评测集

```json
{
  "id": "rag_001",
  "query": "检索查询",
  "reference_answer": "参考答案",
  "ground_truth_contexts": ["正确文档ID列表"],
  "retrieved_contexts": ["实际检索到的文档ID列表"],
  "prediction": "RAG 生成的回答"
}
```

### Agent 评测集

```json
{
  "id": "agent_001",
  "task_description": "任务描述",
  "expected_tool_calls": ["期望的工具调用"],
  "actual_tool_calls": ["实际的工具调用"],
  "expected_steps": 3,
  "actual_steps": 4,
  "prediction": "Agent 输出"
}
```

## 自定义评估器

实现 `BaseEvaluator` 协议即可：

```python
from app.evaluators.base import EvalResult

class MyEvaluator:
    name = "my_evaluator"

    def evaluate(self, prediction: str, reference: str, **kwargs) -> EvalResult:
        # 你的评估逻辑
        score = ...
        return EvalResult(score=score, passed=score > 0.5, details={...})
```

## 配套学习

- 理论基础：`06-评测与优化/` 目录下的 6 篇讲义
- 实战教学：`07-项目实战/10.评测Pipeline实战.md`
