# Code Agent

## 项目定位

这是一个基于 LangGraph 构建的 **Code Agent**，能够自动读取代码、定位 bug、修复并通过测试验证。

## 核心能力

1. **代码读取与分析**：Agent 自主读取项目文件，理解代码结构
2. **Bug 定位与修复**：运行测试发现失败，分析原因并修复
3. **验证循环**：修复后自动运行测试，失败则重新规划修复
4. **沙箱安全**：所有文件操作和命令执行都在沙箱内

## 图拓扑

```
START → analyze_task → plan_approach → execute_step ──┐
                                          ↑           │
                                          └───────────┘ (循环执行计划步骤)
                                                      │
                                               verify_result
                                                  │      │
                                            [通过] │      │ [失败]
                                                  ↓      ↓
                                             summarize  plan_approach (重新规划)
                                                  │
                                                 END
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 API key
export OPENAI_API_KEY=your-key

# 自动修 Bug（核心 demo）
python scripts/run_fix_bugs.py

# 代码解释
python scripts/run_explain_code.py
```

## 项目结构

```
agent-code-assistant/
├── README.md
├── requirements.txt
├── .env.example
├── data/
│   └── sample_project/             # 有 bug 的示例项目（沙箱）
│       ├── calculator.py           # 4 个 bug
│       ├── test_calculator.py      # 对应测试
│       └── utils.py                # 工具函数
├── app/
│   ├── config.py                   # 配置（沙箱路径、超时等）
│   ├── llm_client.py               # OpenAI 兼容客户端
│   ├── prompts.py                  # 所有 prompt
│   ├── state.py                    # LangGraph 状态
│   ├── sandbox.py                  # 沙箱安全管理
│   ├── tools/
│   │   ├── file_tools.py           # read_file, write_file, list_dir
│   │   ├── search_tools.py         # search_code
│   │   └── exec_tools.py           # run_command
│   ├── nodes.py                    # 5 个 LangGraph 节点
│   └── graph.py                    # 图构建（含条件路由）
└── scripts/
    ├── run_fix_bugs.py             # 自动修 Bug 入口
    └── run_explain_code.py         # 代码解释入口
```

## 内置 Bug 说明

`data/sample_project/calculator.py` 中有 4 个典型 bug：

| # | Bug | 表现 |
|---|-----|------|
| 1 | divide() 除零未处理 | `divide(10, 0)` 抛出未处理的 ZeroDivisionError |
| 2 | add() 无类型检查 | `add("hello", 3)` 返回 "hello3" 而非报错 |
| 3 | average() 空列表 | `average([])` 抛出 ZeroDivisionError |
| 4 | percentage_change() 基数为 0 | `percentage_change(0, 100)` 除零 |

## 配套学习

- 理论基础：`05-Agent/8.Code Agent.md`
- 实战教学：`07-项目实战/9.Code-Agent实战.md`
