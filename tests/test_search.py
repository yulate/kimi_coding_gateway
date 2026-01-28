"""
测试 Kimi 的 Skills 端点 (Search)
"""
import httpx
import asyncio
import os
import json

GATEWAY_URL = "http://127.0.0.1:8765/v1"

async def test_search_skill():
    print("=" * 60)
    print("[TEST] 测试 Search Skill (/v1/search)")
    print("=" * 60)
    
    # 构造 search 请求
    # 注意：具体参数可能需要根据文档猜测，通常是 {"query": "..."}
    async with httpx.AsyncClient() as client:
        try:
            print("[SEND] 发送 Search 请求...")
            response = await client.post(
                f"{GATEWAY_URL}/search",
                json={"query": "Moonshot AI Kimi"},
                headers={"Authorization": "Bearer passed-by-gateway"},
                timeout=30.0
            )
            
            print(f"Response Status: {response.status_code}")
            if response.status_code == 200:
                print("[SUCCESS] 请求成功!")
                try:
                    data = response.json()
                    print(f"数据预览: {json.dumps(data, ensure_ascii=False)[:200]}...")
                    return True
                except:
                    print(f"Body: {response.text[:200]}")
            else:
                print(f"[FAILURE] 请求失败: {response.text}")
                return False
                
        except Exception as e:
            print(f"[FAILURE] 异常: {e}")
            return False

if __name__ == "__main__":
    asyncio.run(test_search_skill())
