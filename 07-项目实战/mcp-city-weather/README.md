# 城市天气 MCP 实战项目

## 目录

1. [项目解决什么问题](#1-项目解决什么问题)
2. [为什么这个项目适合当前学习阶段](#2-为什么这个项目适合当前学习阶段)
3. [前置知识](#3-前置知识)
4. [学习目标](#4-学习目标)
5. [核心架构与流程](#5-核心架构与流程)
6. [运行方式](#6-运行方式)
7. [推荐观察点](#7-推荐观察点)
8. [常见失败原因](#8-常见失败原因)
9. [练习任务](#9-练习任务)
10. [下一步延伸](#10-下一步延伸)

## 1. 项目解决什么问题

这是一个基于官方 Python MCP SDK 的实战项目。

它解决的是：

1. 如何把一个真实外部 API 封装成 MCP Tool
2. 如何让 VS Code、Claude Desktop 这类宿主应用接入本地 MCP 服务
3. 为什么 MCP 工具的返回结果需要尽量结构化

当前项目会：

1. 输入城市名
2. 通过地理编码 API 找到城市坐标
3. 调用天气 API 获取当前天气
4. 把结果作为 MCP Tool 暴露给宿主应用

## 2. 为什么这个项目适合当前学习阶段

这个项目适合作为 **MCP 入门项目**，因为它足够小，但完整覆盖了：

- 服务端编写
- Tool 暴露
- 客户端接入
- 外部 API 调用

## 3. 前置知识

建议先完成：

1. [04-工具调用与函数调用/README.md](/Users/chenmingdong01/Documents/AI/agent/04-工具调用与函数调用/README.md)
2. [07-项目实战/2.MCP学习资料助手实战.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/2.MCP学习资料助手实战.md)

## 4. 学习目标

完成这个项目后，你应该能够：

1. 理解一个最小 MCP Server 的结构
2. 理解 Tool 如何接真实外部 API
3. 理解 `mcp.json` 如何配置本地服务
4. 理解客户端如何发现和调用 MCP Tool

## 5. 核心架构与流程

项目结构：

```text
07-项目实战/mcp-city-weather/
├── README.md
├── demo_client.py
├── mcp.json
├── pyproject.toml
└── weather_server.py
```

当前项目提供 1 个核心 Tool：

- `get_city_weather`

这个项目的完整链路可以理解成：

1. 用户或客户端输入城市
2. 服务端先请求地理编码接口
3. 再请求天气接口
4. 最后把结构化结果返回给宿主或模型

## 6. 运行方式

建议使用 `uv`：

```bash
cd 07-项目实战/mcp-city-weather
uv sync
```

本地直接运行服务端：

```bash
uv run weather_server.py
```

如果你想从客户端侧验证链路：

```bash
python demo_client.py --list-only
python demo_client.py --server city-weather
python demo_client.py --server city-weather --tool get_city_weather --arguments '{"city":"上海"}' --verbose
```

如果想看 HTTP 调用细节，可以加：

```bash
python demo_client.py --server city-weather --tool get_city_weather --arguments '{"city":"上海"}' --http-debug
```

## 7. 推荐观察点

建议重点观察：

1. 服务端如何定义 Tool
2. `mcp.json` 如何声明 `stdio` 服务
3. 客户端为什么先 `initialize` 再 `list_tools`
4. 为什么返回结果要同时适合人看和模型继续使用

## 8. 常见失败原因

常见失败点包括：

1. 当前目录和 `mcp.json` 里的相对路径不一致
2. 城市名匹配不到，导致地理编码失败
3. 外部 API 返回字段变化，但服务端没做兼容处理
4. 返回结果只是一堆原始 JSON，不利于模型继续使用

## 9. 练习任务

建议做下面 3 个练习：

1. 把当前天气扩展为未来天气查询
2. 增加批量查询多个城市的 Tool
3. 为天气结果补一个简洁摘要字段，方便后续模型引用

## 10. 下一步延伸

如果你已经能跑通这个项目，下一步建议：

1. 做一个更偏“知识型能力”的 MCP 项目：
   [mcp-study-assistant/README.md](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/mcp-study-assistant/README.md)
2. 继续进入 Agent 项目，把 MCP 能力接到更复杂的任务系统里。
