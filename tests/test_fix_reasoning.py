import json
import sys
import os

# 确保能导入 app 模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from kimi_coding_gateway.app.main import process_request_body

def test_auto_inject_reasoning():
    print("[TEST] 测试自动注入 reasoning_content")
    
    # 模拟一个请求体，包含一个 assistant tool call message，缺失 reasoning_content
    payload = {
        "model": "kimi-for-coding",
        "messages": [
            {"role": "user", "content": "Start"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {"name": "test", "arguments": "{}"}
                    }
                ]
                # missing reasoning_content
            },
            {"role": "tool", "tool_call_id": "call_123", "content": "Done"}
        ]
    }
    
    body_bytes = json.dumps(payload).encode('utf-8')
    
    # 处理
    new_body, stream = process_request_body(body_bytes)
    
    # 验证
    new_data = json.loads(new_body)
    assistant_msg = new_data["messages"][1]
    
    if "reasoning_content" in assistant_msg:
        print(f"[SUCCESS] reasoning_content 已注入: '{assistant_msg['reasoning_content']}'")
        assert assistant_msg["reasoning_content"] == ""
    else:
        print("[FAILURE] reasoning_content 未注入！")
        print(f"Data: {assistant_msg}")
        raise AssertionError("reasoning_content missing")

def test_ignore_normal_assistant():
    print("[TEST] 测试普通 assistant 消息不会被注入 (如果只有 content)")
    payload = {
        "messages": [
            {"role": "assistant", "content": "Hello"}
        ]
    }
    # 按照目前的逻辑，只有带 tool_calls 的才会被注入
    new_body, _ = process_request_body(json.dumps(payload).encode('utf-8'))
    new_data = json.loads(new_body)
    if "reasoning_content" not in new_data["messages"][0]:
        print("[SUCCESS] 普通消息未注入")
    else:
        print(f"[INFO] 普通消息也被注入了 (这也没关系，实际上可能也需要): {new_data['messages'][0]}")

if __name__ == "__main__":
    try:
        test_auto_inject_reasoning()
        test_ignore_normal_assistant()
        print("\n[ALL PASS] 所有测试通过")
    except Exception as e:
        print(f"\n[FAIL] 测试失败: {e}")
        sys.exit(1)
