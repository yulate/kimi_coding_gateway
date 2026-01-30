"""
Kimi Coding Plan API Gateway
将 OpenAI 兼容的请求转发到 Kimi Coding Plan API (api.kimi.com/coding)
"""
import os
import json
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


app = FastAPI(title="Kimi Coding Plan Gateway")

# Kimi Coding API 配置
KIMI_BASE_URL = "https://api.kimi.com/coding/v1"
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "sk-kimi")

# 关键：模拟 Kimi CLI 的 User-Agent
KIMI_CLI_USER_AGENT = "KimiCLI/1.3"

# 本地网关配置
GATEWAY_HOST = os.getenv("GATEWAY_HOST", "0.0.0.0")
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8765"))


@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_v1(path: str, request: Request):
    """代理 /v1/* 路径的请求到 Kimi Coding API"""
    target_url = f"{KIMI_BASE_URL}/{path}"
    return await forward_request(target_url, request)


def process_request_body(body: bytes) -> tuple[bytes, bool]:
    """
    处理请求体：
    1. 检测 stream 参数
    2. 修复 Kimi API 对 reasoning_content 的严格检查
    """
    if not body:
        return body, False
        
    try:
        data = json.loads(body)
        stream = data.get("stream", False)
        
        # 修复逻辑：为 assistant 消息补充 reasoning_content
        messages = data.get("messages", [])
        modified = False
        for i, msg in enumerate(messages):
            if msg.get("role") == "assistant":
                # Kimi API 严格要求 Thinking 模型必须包含 reasoning_content
                # 无论是普通回复还是 Tool Call，都可能需要
                if "reasoning_content" not in msg:
                    msg["reasoning_content"] = " " # 注入一个空格或点，尽量减少对模型的影响
                    modified = True
        
        if modified:
            return json.dumps(data).encode("utf-8"), stream
        return body, stream
    except json.JSONDecodeError:
        return body, False


async def forward_request(target_url: str, request: Request):
    """转发请求到 Kimi Coding API"""
    # 获取原始 body
    original_body = await request.body()
    # 处理 body（自动修复 messages）
    body, stream = process_request_body(original_body)
    
    if stream:
        return await handle_stream_request(target_url, body)
    else:
        return await handle_normal_request(target_url, request.method, body)


async def handle_stream_request(target_url: str, body: bytes):
    """处理流式请求"""
    # 使用 httpx 低级别 API 来确保 headers 正确发送
    async def stream_generator():
        async with httpx.AsyncClient(timeout=300.0) as client:
            # 构建请求
            req = client.build_request(
                method="POST",
                url=target_url,
                content=body,
                headers={
                    "Authorization": f"Bearer {KIMI_API_KEY}",
                    "Content-Type": "application/json",
                    "User-Agent": KIMI_CLI_USER_AGENT,
                },
            )
            print(f"[DEBUG] Stream Request URL: {req.url}")
            try:
                response = await client.send(req, stream=True)
                print(f"[DEBUG] Stream Response Status: {response.status_code}")
                
                if response.status_code != 200:
                    content = await response.aread()
                    print(f"[DEBUG] Stream Error Body: {content}")
                    error_msg = {"error": {"message": f"Upstream error: {response.status_code}", "type": "upstream_error"}}
                    yield f"data: {json.dumps(error_msg)}\n\n".encode()
                    yield b"data: [DONE]\n\n"
                    await response.aclose()
                    return

                try:
                    async for chunk in response.aiter_bytes():
                        yield chunk
                finally:
                    await response.aclose()
            except Exception as e:
                print(f"[ERROR] Stream Exception: {e}")
                yield f"data: {{\"error\": \"{str(e)}\"}}\n\n".encode()
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


async def handle_normal_request(target_url: str, method: str, body: bytes):
    """处理非流式请求"""
    # 使用 httpx 低级别 API 来确保 headers 正确发送
    async with httpx.AsyncClient(timeout=300.0) as client:
        req = client.build_request(
            method=method,
            url=target_url,
            content=body,
            headers={
                "Authorization": f"Bearer {KIMI_API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": KIMI_CLI_USER_AGENT,
            },
        )
        
        # 打印调试信息
        print(f"[DEBUG] Request URL: {req.url}")
        
        response = await client.send(req)
        
        print(f"[DEBUG] Response Status: {response.status_code}")
        
        try:
            content = response.json()
        except json.JSONDecodeError:
            content = {"data": response.text}
        
        return JSONResponse(
            content=content,
            status_code=response.status_code,
        )


@app.get("/")
async def root():
    """健康检查与配置信息"""
    return {
        "status": "running",
        "service": "Kimi Coding Plan Gateway",
        "kimi_base_url": KIMI_BASE_URL,
        "gateway_url": f"http://{GATEWAY_HOST}:{GATEWAY_PORT}",
        "user_agent": KIMI_CLI_USER_AGENT,
    }

@app.get("/health")
async def health():
    return {"status": "ok"}

def get_local_ip():
    """获取本机局域网 IP"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def start_gateway():
    """启动网关服务"""
    print(f"[INFO] 启动 Kimi Coding Plan Gateway...")
    print(f"[INFO] 监听地址: http://{GATEWAY_HOST}:{GATEWAY_PORT}")
    
    if GATEWAY_HOST == "0.0.0.0":
        local_ip = get_local_ip()
        print(f"[INFO] 局域网访问地址: http://{local_ip}:{GATEWAY_PORT}")
        print(f"[WARN] 注意：允许外部访问可能导致 API Key 被局域网内其他人使用")
        
    uvicorn.run(app, host=GATEWAY_HOST, port=GATEWAY_PORT)

if __name__ == "__main__":
    start_gateway()
