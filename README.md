# Kimi Coding Plan Gateway

这是一个 API 网关，用于将 OpenAI 兼容的 API 请求转发到 Kimi Coding Plan API (`api.kimi.com/coding`)。
它解决了 Kimi Coding API 的访问限制问题，并提供了完整的 OpenAI 兼容性，支持 Tools Calling 和 MCP 协议。

## 项目结构

```text
kimi_coding_gateway/
├── app/
│   ├── main.py             # 启动入口与管理端点
│   ├── proxy.py            # 请求分发
│   ├── normal_proxy.py     # 非流式代理
│   ├── stream_proxy.py     # 流式代理
│   ├── runtime.py          # 运行时与连接池
│   └── ...
├── tests/
│   ├── test_basic.py
│   ├── test_tools.py
│   └── test_concurrency_runtime.py
├── requirements.txt
├── .env.example
└── run.sh
```

## 快速开始

### 1. 配置

复制模版文件并配置 API Key：
```bash
cp .env.example .env
# 编辑 .env 文件填入你的 KIMI_API_KEY
```

*(如果不想创建 `.env` 文件，网关也可以直接读取环境变量。)*

如需开启调试日志（完整记录每次请求/响应 JSON 到 JSONL）：
```bash
GATEWAY_DEBUG=true
GATEWAY_DEBUG_JSONL_FILE=./logs/gateway_requests.jsonl
```

如需网关默认注入推理强度（不覆盖客户端显式传值）：
```bash
GATEWAY_REASONING_EFFORT=high
```

如需显式配置并发治理：
```bash
GATEWAY_MAX_UPSTREAM_CONCURRENCY=10
GATEWAY_NON_STREAM_MAX_UPSTREAM_CONCURRENCY=7
GATEWAY_STREAM_MAX_UPSTREAM_CONCURRENCY=3
GATEWAY_NON_STREAM_MAX_QUEUE_SIZE=14
GATEWAY_STREAM_MAX_QUEUE_SIZE=6
GATEWAY_UPSTREAM_QUEUE_TIMEOUT_SECONDS=10
GATEWAY_REQUEST_DEADLINE_SECONDS=600
GATEWAY_DISCONNECT_POLL_INTERVAL_SECONDS=0.5
```

如需显式配置连接池：
```bash
GATEWAY_NON_STREAM_MAX_CONNECTIONS=7
GATEWAY_STREAM_MAX_CONNECTIONS=3
GATEWAY_NON_STREAM_MAX_KEEPALIVE_CONNECTIONS=7
GATEWAY_STREAM_MAX_KEEPALIVE_CONNECTIONS=3
GATEWAY_KEEPALIVE_EXPIRY_SECONDS=30
```

### 2. 启动服务

使用启动脚本（自动安装依赖）：
```bash
./run.sh
```

或者手动启动：
```bash
pip install -r requirements.txt
python3 -m app.main
```

### 3. 使用方法

服务默认监听页面 `0.0.0.0`（允许局域网访问）。

启动后，控制台会打印本机局域网 IP，例如：
```text
[INFO] 局域网访问地址: http://192.168.1.5:8765
```

> [!WARNING]
> 开启局域网访问 (`0.0.0.0`) 意味着同一网络下的任何人都可以连接此端口使用你的 API Key。请确保在可信网络环境中使用，或通过防火墙限制访问。

#### Python SDK 集成
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8765/v1",
    api_key="ignored",
)

response = client.chat.completions.create(
    model="kimi-for-coding",
    messages=[{"role": "user", "content": "你好"}],
)
```

#### MCP Agent (Claude Code / Cline) 集成
- **Base URL**: `http://127.0.0.1:8765/v1`
- **API Key**: 任意值
- **Model**: `kimi-for-coding`

## 并发治理

- 网关现在使用两个独立池：普通请求池和流式请求池，避免长流把短请求全部饿死。
- 每个池都有独立的：并发上限、队列长度上限、连接池连接数。
- 请求在队列中等待超过 `GATEWAY_UPSTREAM_QUEUE_TIMEOUT_SECONDS` 会显式返回 `503`。
- 请求总生命周期超过 `GATEWAY_REQUEST_DEADLINE_SECONDS` 会显式返回 `504 gateway_request_deadline_exceeded`。
- 下游客户端断开连接后，网关会尽快取消对应的上游请求并释放槽位。
- 上游连接断开、连接超时、读取超时会映射为明确的 `502/503/504`，不再直接抛成本地 `500`。

## 指标与观测

网关提供三个管理端点：

- `/`：基础状态 + 并发配置 + 当前指标快照
- `/health`：轻量健康状态
- `/metrics`：完整 JSON 指标

当前指标包含：

- 普通请求池 / 流式请求池：`in_flight`、`waiters`、`avg_queue_wait_seconds`
- 流式活跃数：`active_streams`、`max_active_streams`
- 首字节指标：`normal_first_byte`、`stream_first_byte`
- 请求总量与平均耗时
- 客户端断连次数与 deadline 超时次数

## Debug JSONL 日志

开启 `GATEWAY_DEBUG=true` 后，网关会对每次请求追加一行 JSON 到 `GATEWAY_DEBUG_JSONL_FILE`。

每行会包含：
- `request_id`、`timestamp`、`method`、`path`、`target_url`
- `request_json`（原始入站请求 JSON）
- `forwarded_request_json`（网关修复后的转发 JSON）
- `status_code`
- `response_json`

> [!IMPORTANT]
> `GATEWAY_DEBUG=true` 会显著增加 CPU、内存和磁盘 IO 开销，压测或高并发场景建议关闭。

## 测试

在服务运行的情况下，执行测试脚本：

```bash
python3 tests/test_basic.py
python3 tests/test_tools.py
python3 -m unittest tests.test_concurrency_runtime
```
