# 城市天气 MCP 实战项目

这是一个基于官方 Python MCP SDK 的实战项目。

它的目标很明确：

1. 输入一个城市名
2. 通过地理编码 API 找到城市坐标
3. 调用天气 API 获取当前天气
4. 把结果作为 MCP Tool 暴露给 VS Code、Claude Desktop 等宿主应用

## 这个项目适合学什么

这个项目重点不是“做一个天气网页”，而是让你真正看到：

- MCP 服务端怎么用官方 SDK 编写
- 一个 Tool 如何接真实外部 API
- VS Code 如何通过 `mcp.json` 接入本地 MCP 服务
- 返回结果为什么要尽量结构化

## 项目结构

```text
07-项目实战/mcp-city-weather/
├── README.md
├── demo_client.py
├── mcp.json
├── pyproject.toml
└── weather_server.py
```

## 核心能力

当前项目提供 1 个 MCP Tool：

- `get_city_weather`
  根据城市名称查询当前天气

输入示例：

- `上海`
- `北京`
- `Hangzhou`
- `Tokyo`

返回结果包含：

- 匹配到的城市信息
- 当前温度
- 体感温度
- 相对湿度
- 风速
- 天气描述
- 穿衣建议
- 一句适合模型继续使用的摘要

## 依赖安装

建议使用 `uv`：

```bash
cd 07-项目实战/mcp-city-weather
uv sync
```

如果你更习惯 `pip`，也可以按 `pyproject.toml` 自己安装依赖。

## 本地直接运行

在项目目录中运行：

```bash
uv run weather_server.py
```

注意：

- 这是一个 `stdio` MCP 服务
- 启动后会等待宿主进程通过标准输入输出和它通信
- 它不是普通的交互式 CLI，不会像脚本那样打印一堆可读文本

## 如果你是“接入别人 MCP 的客户端方”

本项目也提供了一个更通用的客户端示例，它会读取 `mcp.json`，按配置连接多个 MCP Server。

默认示例配置文件是：

1. [mcp.json](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/mcp-city-weather/mcp.json)

内容格式兼容 Cursor 常见的：

```json
{
  "mcpServers": {
    "city-weather": {
      "type": "stdio",
      "command": "python",
      "args": [
        "weather_server.py"
      ]
    }
  }
}
```

如果你的 `mcp.json` 不和 `weather_server.py` 放在同一个目录，也可以写成相对路径，例如：

```json
{
  "mcpServers": {
    "city-weather": {
      "type": "stdio",
      "command": "python",
      "args": [
        "07-项目实战/mcp-city-weather/weather_server.py"
      ]
    }
  }
}
```

先列出配置中的所有 server 和它们的工具：

```bash
cd 07-项目实战/mcp-city-weather
python demo_client.py --list-only
```

如果只想查看某个 server 暴露了哪些工具：

```bash
python demo_client.py --server city-weather
```

如果要真正调用某个工具：

```bash
python demo_client.py \
  --server city-weather \
  --tool get_city_weather \
  --arguments '{"city":"上海"}' \
  --verbose
```

如果你想看到服务端访问天气 API 时的 HTTP 入参和返回值摘要，可以加上 `--http-debug`：

```bash
python demo_client.py \
  --server city-weather \
  --tool get_city_weather \
  --arguments '{"city":"上海"}' \
  --http-debug
```

打开后，你会看到类似下面的信息：

- 地理编码接口请求参数
- 地理编码接口返回的首条结果摘要
- 天气接口请求参数
- 天气接口返回的 `current` 字段摘要

这对排查下面几类问题很有帮助：

- 城市名为什么没匹配到
- 请求实际打到了哪个接口
- 天气接口到底返回了什么字段
- 是工具逻辑有问题，还是外部 API 返回不符合预期

如果你的 `mcp.json` 不在当前目录，可以显式指定配置文件：

```bash
python demo_client.py \
  --config ./mcp.json \
  --server city-weather \
  --tool get_city_weather \
  --arguments '{"city":"上海"}'
```

如果你想用仓库根目录作为当前目录，也可以这样运行：

```bash
python 07-项目实战/mcp-city-weather/demo_client.py \
  --config 07-项目实战/mcp-city-weather/mcp.json \
  --server city-weather \
  --tool get_city_weather \
  --arguments '{"city":"上海"}'
```

这个客户端做了 4 件事：

1. 读取 `mcp.json`
2. 按配置启动目标 server
3. 执行 `initialize` 和 `list_tools`
4. 调用指定 tool 并解析结果

如果你只想理解客户端怎么写，重点看：

1. [demo_client.py](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/mcp-city-weather/demo_client.py)

其中最关键的几步是：

- 读取 `mcp.json` 中的 `mcpServers` / `servers`
- `StdioServerParameters(...)`
- `stdio_client(...)`
- `ClientSession(...)`
- `await session.initialize()`
- `await session.list_tools()`
- `await session.call_tool(...)`

## 在 VS Code 中接入

如果你的工作区就是这个仓库，可以在仓库根目录新建：

```text
.vscode/mcp.json
```

填入：

```json
{
  "servers": {
    "city-weather": {
      "type": "stdio",
      "command": "python",
      "args": [
        "weather_server.py"
      ]
    }
  }
}
```

如果你的 `.vscode/mcp.json` 放在仓库根目录，则更推荐写成：

```json
{
  "servers": {
    "city-weather": {
      "type": "stdio",
      "command": "python",
      "args": [
        "07-项目实战/mcp-city-weather/weather_server.py"
      ]
    }
  }
}
```

## 在 VS Code 里怎么验证

1. 打开命令面板
2. 运行 `MCP: List Servers`
3. 确认能看到 `city-weather`
4. 在聊天里输入：

```text
请使用 city-weather 的工具，查询今天上海的天气，并给我一个简短穿衣建议。
```

如果服务启动成功，宿主就能发现并调用 `get_city_weather`。

## 这个项目做了哪些工程处理

相比最小玩具示例，这个项目多做了几件更接近真实场景的事：

- 不写死固定城市坐标，而是先做地理编码
- 调用真实天气 API，而不是返回假数据
- 返回结构化字段，方便模型二次推理
- 增加网络异常和未知城市处理
- 使用日志而不是 `print()`，避免污染 `stdio` 协议通道

## 建议你重点看哪里

1. [weather_server.py](/Users/chenmingdong01/Documents/AI/agent/07-项目实战/mcp-city-weather/weather_server.py)

这里是完整服务端实现。重点看 `FastMCP`、`@mcp.tool()`、地理编码和天气查询两段逻辑是怎么串起来的。

## 推荐测试输入

- `请查询上海天气`
- `请查询北京天气并给穿衣建议`
- `帮我看一下 Hangzhou 现在天气`
- `帮我查 Tokyo 的天气`
- `帮我查一个不存在的城市，比如 火星城`

## 你可以继续扩展什么

1. 增加未来 3 天预报工具
2. 增加空气质量工具
3. 增加中文城市别名纠错
4. 把天气结果保存成 Resource 或日志文件
5. 为企业内部系统改造成“门店天气预警服务”
