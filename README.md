# Kimi Coding Plan Gateway

这是一个 API 网关，用于将 OpenAI 兼容的 API 请求转发到 Kimi Coding Plan API (`api.kimi.com/coding`)。
它解决了 Kimi Coding API 的访问限制问题，并提供了完整的 OpenAI 兼容性，支持 Tools Calling 和 MCP 协议。

## 项目结构

```text
kimi_coding_gateway/
├── app/
│   └── main.py          # 网关核心服务
├── tests/
│   ├── test_basic.py    # 基础对话测试
│   ├── test_tools.py    # 工具调用测试
│   └── ...
├── requirements.txt     # 依赖列表
├── .env.example         # 环境变量模版
└── run.sh               # 启动脚本
```

## 快速开始

### 1. 配置

复制模版文件并配置 API Key：
```bash
cp .env.example .env
# 编辑 .env 文件填入你的 KIMI_API_KEY
```
*(如果不想创建 .env 文件，网关也可以直接读取环境变量)*

### 2. 启动服务

使用启动脚本（自动安装依赖）：
```bash
./run.sh
```

或者手动启动：
```bash
pip install -r requirements.txt
python3 app/main.py
```

### 3. 使用方法

服务默认运行在 `http://127.0.0.1:8765`。

#### Python SDK 集成
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8765/v1",
    api_key="ignored",  # 网关处理认证
)

response = client.chat.completions.create(
    model="kimi-for-coding",
    messages=[{"role": "user", "content": "你好"}]
)
```

#### MCP Agent (Claude Code / Cline) 集成
- **Base URL**: `http://127.0.0.1:8765/v1`
- **API Key**: 任意值
- **Model**: `kimi-for-coding`

## 测试

在服务运行的情况下，执行测试脚本：

```bash
python3 tests/test_basic.py
python3 tests/test_tools.py
```
