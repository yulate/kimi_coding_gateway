"""
测试网关的 Tools Calling 功能
"""
import json
import os
from openai import OpenAI

# 网关配置
GATEWAY_URL = "http://127.0.0.1:8765/v1"

def test_tool_calling():
    print("=" * 60)
    print("[TEST] 测试 Tools Calling")
    print("=" * 60)
    
    client = OpenAI(
        base_url=GATEWAY_URL,
        api_key="not-needed",
    )
    
    # 定义一个简单的工具
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA",
                        },
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                    },
                    "required": ["location"],
                },
            },
        }
    ]
    
    try:
        print("[SEND] 发送带有 Tools 的请求...")
        response = client.chat.completions.create(
            model="kimi-for-coding",
            messages=[
                {"role": "user", "content": "What's the weather like in Shanghai today?"}
            ],
            tools=tools,
            tool_choice="auto",
        )
        
        message = response.choices[0].message
        print(f"[SUCCESS] 请求成功!")
        
        if message.tool_calls:
            print("[TOOL] 触发了工具调用:")
            for tool_call in message.tool_calls:
                print(f"  - ID: {tool_call.id}")
                print(f"  - Name: {tool_call.function.name}")
                print(f"  - Args: {tool_call.function.arguments}")
            return True
        else:
            print("[WARN] 未触发工具调用 (模型直接回复了文本):")
            print(f"  Content: {message.content}")
            return False
            
    except Exception as e:
        print(f"[FAILURE] 请求失败: {e}")
        return False

if __name__ == "__main__":
    test_tool_calling()
