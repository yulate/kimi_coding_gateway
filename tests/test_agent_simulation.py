import sys
import os
import time
from openai import OpenAI

# 确保能连接到 Gateway
GATEWAY_URL = "http://127.0.0.1:8765/v1"

def test_simulation():
    print("[TEST] 模拟 Agent 历史消息修复")
    
    client = OpenAI(base_url=GATEWAY_URL, api_key="ignored")
    
    # 构造一个包含历史 Tool Call 但缺失 reasoning_content 的消息列表
    messages = [
        {"role": "user", "content": "What's the weather?"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_sanity_check",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": "{}"}
                }
            ]
            # 缺失 reasoning_content
        },
        {"role": "tool", "tool_call_id": "call_sanity_check", "content": "Sunny"},
        {"role": "user", "content": "Cool, thanks."}
    ]
    
    try:
        print("[SEND] 发送包含缺陷历史消息的请求...")
        # 我们请求一个新的 completion，带有这个历史
        resp = client.chat.completions.create(
            model="kimi-for-coding",
            messages=messages,
            max_tokens=10 # 只需要通过校验
        )
        print("[SUCCESS] 请求成功，说明网关成功修复了消息！")
        print(f"[INFO] Response: {resp.choices[0].message.content}")
        
    except Exception as e:
        print(f"[FAILURE] 请求失败: {e}")
        # 如果是 400 且包含 reasoning_content missing，则说明修复失败
        if "msg" in str(e) or "reasoning_content" in str(e):
             print("[FAIL] 依然收到 reasoning_content 错误！")
        sys.exit(1)

if __name__ == "__main__":
    test_simulation()
