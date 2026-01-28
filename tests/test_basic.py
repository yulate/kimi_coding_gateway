"""
测试 Kimi Coding Plan Gateway
使用 OpenAI SDK 调用本地网关
"""
import os
import sys
import asyncio
from openai import OpenAI

# 网关配置
GATEWAY_URL = "http://127.0.0.1:8765/v1"

def test_chat_completion():
    """
    测试非流式 Chat Completion
    """
    print("=" * 60)
    print("[TEST] 测试非流式 Chat Completion")
    print("=" * 60)
    
    client = OpenAI(
        base_url=GATEWAY_URL,
        api_key="not-needed",  # API key 由网关处理
    )
    
    try:
        response = client.chat.completions.create(
            model="kimi-for-coding",  # Kimi 模型名称
            messages=[
                {"role": "system", "content": "你是一个有帮助的助手。"},
                {"role": "user", "content": "你好，请用一句话介绍一下自己。"}
            ],
            max_tokens=100,
        )
        
        print(f"[SUCCESS] 请求成功!")
        print(f"[INFO] 模型: {response.model}")
        print(f"[REPLY] 回复: {response.choices[0].message.content}")
        print(f"[INFO] Token 使用: {response.usage}")
        return True
    except Exception as e:
        print(f"[FAILURE] 请求失败: {e}")
        return False


def test_chat_completion_stream():
    """
    测试流式 Chat Completion
    """
    print("\n" + "=" * 60)
    print("[TEST] 测试流式 Chat Completion")
    print("=" * 60)
    
    client = OpenAI(
        base_url=GATEWAY_URL,
        api_key="not-needed",
    )
    
    try:
        stream = client.chat.completions.create(
            model="kimi-for-coding",
            messages=[
                {"role": "system", "content": "你是一个编程助手。"},
                {"role": "user", "content": "写一个 Python 的 hello world 程序。"}
            ],
            max_tokens=200,
            stream=True,
        )
        
        print("[SUCCESS] 流式请求成功!")
        print("[REPLY] 回复: ", end="", flush=True)
        
        full_response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                print(content, end="", flush=True)
                full_response += content
        
        print("\n")
        print(f"[INFO] 完整回复长度: {len(full_response)} 字符")
        return True
    except Exception as e:
        print(f"[FAILURE] 流式请求失败: {e}")
        return False


def test_list_models():
    """
    测试列出模型
    """
    print("\n" + "=" * 60)
    print("[TEST] 测试列出模型")
    print("=" * 60)
    
    client = OpenAI(
        base_url=GATEWAY_URL,
        api_key="not-needed",
    )
    
    try:
        models = client.models.list()
        print("[SUCCESS] 请求成功!")
        print("[LIST] 可用模型:")
        for model in models.data:
            print(f"  - {model.id}")
        return True
    except Exception as e:
        print(f"[FAILURE] 请求失败: {e}")
        print("[NOTE] 注意: Kimi API 可能不支持 /models 端点")
        return False


def main():
    """
    运行所有测试
    """
    print("\n" + "Kimi Coding Plan Gateway 测试".center(60))
    print(f"Gateway URL: {GATEWAY_URL}")
    print("\n")
    
    results = []
    
    # 测试非流式
    results.append(("非流式 Chat Completion", test_chat_completion()))
    
    # 测试流式
    results.append(("流式 Chat Completion", test_chat_completion_stream()))
    
    # 测试列出模型（可选）
    results.append(("列出模型", test_list_models()))
    
    # 打印测试结果汇总
    print("\n" + "=" * 60)
    print("[SUMMARY] 测试结果汇总")
    print("=" * 60)
    
    passed = 0
    failed = 0
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status}: {name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 通过, {failed} 失败")


if __name__ == "__main__":
    main()
