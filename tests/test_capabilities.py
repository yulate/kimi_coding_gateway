"""
测试 Kimi 的内置能力
"""
import httpx
import asyncio
import os
import json
from openai import OpenAI

GATEWAY_URL = "http://127.0.0.1:8765/v1"

def test_capabilities():
    print("=" * 60)
    print("[TEST] 测试内置能力")
    print("=" * 60)
    
    client = OpenAI(base_url=GATEWAY_URL, api_key="ignored")
    
    try:
        print("[SEND] 询问实时信息...")
        response = client.chat.completions.create(
            model="kimi-for-coding",
            messages=[
                {"role": "user", "content": "现在的比特币价格是多少？请使用你可用的任何工具或能力。"}
            ],
            stream=True
        )
        
        print("[REPLY] 回复: ", end="", flush=True)
        full_content = ""
        for chunk in response:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                print(content, end="", flush=True)
                full_content += content
            
            # Check for tool calls or reasoning
            if hasattr(chunk.choices[0].delta, 'tool_calls') and chunk.choices[0].delta.tool_calls:
                 print("\n[Tool Call Detected!]")
        
        print("\n\n[DONE] 完成")
        
    except Exception as e:
        print(f"\n[FAILURE] 异常: {e}")

if __name__ == "__main__":
    test_capabilities()
