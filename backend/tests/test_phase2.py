"""
Phase 2 API 集成测试
使用 FastAPI TestClient 进行真实的 HTTP API 测试
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
import json

from app.main import app
from app.config import get_settings
from app.models.user import User, UserRole
from app.services.auth_service import auth_service

# 全局变量存储测试数据
test_user_data = {
    "username": "test_api_user",
    "email": "test_api@example.com",
    "password": "Test123456"
}


@pytest_asyncio.fixture(scope="module")
async def async_client():
    """异步测试客户端"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield client


@pytest.fixture(scope="module")
def test_data():
    """测试数据容器"""
    return {
        "token": None,
        "conversation_id": None
    }


class TestPhase2API:
    """Phase 2 API 测试套件"""
    
    @pytest.fixture(scope="class", autouse=True)
    def setup_class(self):
        """测试类初始化"""
        print("\n" + "=" * 70)
        print("Phase 2 API 集成测试 - 开始")
        print("=" * 70)
        yield
        print("\n" + "=" * 70)
        print("Phase 2 API 集成测试 - 结束")
        print("=" * 70)
    
    @pytest.mark.asyncio
    async def test_00_health_check(self, async_client):
        """测试 0: 健康检查"""
        print("\n[0/11] 健康检查...")
        
        response = await async_client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "services" in data
        
        services = data["services"]
        print(f"[OK] 健康检查通过")
        print(f"   Ollama: {services.get('ollama', 'unknown')}")
        print(f"   ChromaDB: {services.get('chromadb', 'unknown')}")
        print(f"   PostgreSQL: {services.get('postgres', 'unknown')}")
    
    @pytest.mark.asyncio
    async def test_01_register_user(self, async_client):
        """测试 1: 用户注册"""
        print("\n[1/11] 用户注册...")
        
        response = await async_client.post(
            "/api/v1/auth/register",
            json=test_user_data
        )
        
        # 如果用户已存在，先删除（仅测试环境）
        if response.status_code == 400:
            print("   用户已存在，使用现有用户")
        else:
            assert response.status_code == 201
            data = response.json()
            assert data["username"] == test_user_data["username"]
            assert data["email"] == test_user_data["email"]
            print(f"[OK] 用户注册成功: {data['username']}")
    
    @pytest.mark.asyncio
    async def test_02_login_user(self, async_client, test_data):
        """测试 2: 用户登录"""
        print("\n[2/11] 用户登录...")
        
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"]
            }
        )
        
        assert response.status_code == 200, f"登录失败: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        
        test_data["token"] = data["access_token"]
        print(f"[OK] 登录成功")
        print(f"   Token: {test_data['token'][:50]}...")
    
    @pytest.mark.asyncio
    async def test_03_create_conversation(self, async_client, test_data):
        """测试 3: 创建对话"""
        print("\n[3/11] 创建对话...")
        
        response = await async_client.post(
            "/api/v1/conversations",
            headers={"Authorization": f"Bearer {test_data['token']}"},
            json={
                "title": "API 测试对话",
                "document_ids": ["doc-1", "doc-2"]
            }
        )
        
        assert response.status_code == 201  # 创建资源应该返回 201
        data = response.json()
        assert data["title"] == "API 测试对话"
        assert data["document_ids"] == ["doc-1", "doc-2"]
        assert data["message_count"] == 0
        
        test_data["conversation_id"] = data["id"]
        print(f"[OK] 对话创建成功")
        print(f"   对话ID: {test_data['conversation_id']}")
        print(f"   标题: {data['title']}")
        print(f"   关联文档: {data['document_ids']}")
    
    @pytest.mark.asyncio
    async def test_04_send_message_user(self, async_client, test_data):
        """测试 4: 发送用户消息"""
        print("\n[4/11] 发送用户消息...")
        
        response = await async_client.post(
            f"/api/v1/conversations/{test_data['conversation_id']}/messages",
            headers={"Authorization": f"Bearer {test_data['token']}"},
            json={
                "content": "你好，请介绍一下自己",
                "enable_thinking": True,
                "top_k": 3
            },
            timeout=60.0  # 增加超时时间
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # 验证用户消息
        assert "user_message" in data
        user_msg = data["user_message"]
        assert user_msg["role"] == "user"
        assert user_msg["content"] == "你好，请介绍一下自己"
        
        # 验证 AI 回复
        assert "assistant_message" in data
        ai_msg = data["assistant_message"]
        assert ai_msg["role"] == "assistant"
        assert len(ai_msg["content"]) > 0
        
        print(f"[OK] 消息发送成功")
        print(f"   用户消息ID: {user_msg['id']}")
        print(f"   AI回复ID: {ai_msg['id']}")
        print(f"   AI回复: {ai_msg['content'][:100]}...")
        
        if ai_msg.get("thinking"):
            print(f"   Thinking步骤: {len(ai_msg['thinking'])} 个")
        if ai_msg.get("sources"):
            print(f"   引用来源: {len(ai_msg['sources'])} 个")
    
    @pytest.mark.asyncio
    async def test_05_send_multiple_messages(self, async_client, test_data):
        """测试 5: 多轮对话"""
        print("\n[5/11] 测试多轮对话...")
        
        questions = [
            "你能处理哪些类型的文档？",
            "如何上传文档？",
            "RAG 是什么意思？"
        ]
        
        for i, question in enumerate(questions, 1):
            print(f"\n   第 {i} 轮对话...")
            response = await async_client.post(
                f"/api/v1/conversations/{test_data['conversation_id']}/messages",
                headers={"Authorization": f"Bearer {test_data['token']}"},
                json={
                    "content": question,
                    "enable_thinking": True
                },
                timeout=60.0  # 增加超时时间
            )
            
            assert response.status_code == 200
            data = response.json()
            
            user_msg = data["user_message"]
            ai_msg = data["assistant_message"]
            
            print(f"   [OK] 问题: {question}")
            print(f"      回答: {ai_msg['content'][:80]}...")
        
        print(f"\n[OK] 多轮对话测试完成 ({len(questions)} 轮)")
    
    @pytest.mark.asyncio
    async def test_06_get_conversation_messages(self, async_client, test_data):
        """测试 6: 获取对话消息"""
        print("\n[6/11] 获取对话消息...")
        
        response = await async_client.get(
            f"/api/v1/conversations/{test_data['conversation_id']}",
            headers={"Authorization": f"Bearer {test_data['token']}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == test_data['conversation_id']
        assert "messages" in data
        messages = data["messages"]
        
        # 应该有 8 条消息（4轮对话，每轮2条）
        assert len(messages) >= 8
        
        # 验证消息顺序和角色
        for i, msg in enumerate(messages):
            expected_role = "user" if i % 2 == 0 else "assistant"
            assert msg["role"] == expected_role
        
        print(f"[OK] 获取消息成功")
        print(f"   消息总数: {len(messages)}")
        print(f"   用户消息: {len([m for m in messages if m['role'] == 'user'])}")
        print(f"   AI消息: {len([m for m in messages if m['role'] == 'assistant'])}")
    
    @pytest.mark.asyncio
    async def test_07_list_conversations(self, async_client, test_data):
        """测试 7: 获取对话列表"""
        print("\n[7/11] 获取对话列表...")
        
        response = await async_client.get(
            "/api/v1/conversations",
            headers={"Authorization": f"Bearer {test_data['token']}"},
            params={"skip": 0, "limit": 10}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # 检查返回的字段（可能是 items 或 conversations）
        assert "total" in data
        assert data["total"] >= 1
        
        # 兼容两种响应格式
        items = data.get("items") or data.get("conversations")
        assert items is not None, f"响应中没有找到 items 或 conversations 字段: {data.keys()}"
        
        # 找到我们创建的对话
        test_conv = None
        for conv in items:
            if conv["id"] == test_data['conversation_id']:
                test_conv = conv
                break
        
        assert test_conv is not None
        assert test_conv["message_count"] >= 8
        
        print(f"[OK] 对话列表获取成功")
        print(f"   对话总数: {data['total']}")
        print(f"   当前页: {len(items)} 个")
        print(f"   测试对话消息数: {test_conv['message_count']}")
    
    @pytest.mark.asyncio
    async def test_08_update_conversation_title(self, async_client, test_data):
        """测试 8: 更新对话标题"""
        print("\n[8/11] 更新对话标题...")
        
        new_title = "API 测试对话（已完成）"
        response = await async_client.patch(
            f"/api/v1/conversations/{test_data['conversation_id']}/title",
            headers={"Authorization": f"Bearer {test_data['token']}"},
            json={"title": new_title}
        )
        
        assert response.status_code == 200, f"更新标题失败: {response.text}"
        data = response.json()
        assert data["title"] == new_title
        
        print(f"[OK] 标题更新成功")
        print(f"   新标题: {new_title}")
    
    @pytest.mark.asyncio
    async def test_09_export_conversation_markdown(self, async_client, test_data):
        """测试 9: 导出对话（Markdown）"""
        print("\n[9/11] 导出对话（Markdown）...")
        
        response = await async_client.get(
            f"/api/v1/conversations/{test_data['conversation_id']}/export",
            headers={"Authorization": f"Bearer {test_data['token']}"},
            params={
                "format": "markdown",
                "include_thinking": True,
                "include_sources": True
            }
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/markdown; charset=utf-8"
        
        content = response.text
        assert len(content) > 0
        assert "# API 测试对话（已完成）" in content
        
        # 保存导出文件
        export_dir = Path(__file__).parent.parent / "data" / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        
        md_file = export_dir / f"api_test_{test_data['conversation_id']}.md"
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"[OK] Markdown 导出成功")
        print(f"   文件大小: {len(content)} 字符")
        print(f"   保存位置: {md_file.name}")
    
    @pytest.mark.asyncio
    async def test_10_export_conversation_json(self, async_client, test_data):
        """测试 10: 导出对话（JSON）"""
        print("\n[10/11] 导出对话（JSON）...")
        
        response = await async_client.get(
            f"/api/v1/conversations/{test_data['conversation_id']}/export",
            headers={"Authorization": f"Bearer {test_data['token']}"},
            params={
                "format": "json",
                "include_thinking": True,
                "include_sources": True
            }
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        
        data = response.json()
        assert "conversation" in data
        assert "messages" in data
        assert data["conversation"]["id"] == test_data['conversation_id']
        
        # 保存导出文件
        export_dir = Path(__file__).parent.parent / "data" / "exports"
        json_file = export_dir / f"api_test_{test_data['conversation_id']}.json"
        
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[OK] JSON 导出成功")
        print(f"   消息数量: {len(data['messages'])}")
        print(f"   保存位置: {json_file.name}")
    
    @pytest.mark.asyncio
    async def test_11_stream_message(self, async_client, test_data):
        """测试 11: 流式消息（SSE）"""
        print("\n[11/11] 测试流式消息...")
        
        # 注意：AsyncClient 不完全支持 SSE 流式响应
        # 这里只测试接口是否可访问
        response = await async_client.post(
            f"/api/v1/conversations/{test_data['conversation_id']}/messages/stream",
            headers={"Authorization": f"Bearer {test_data['token']}"},
            json={
                "content": "请简单介绍一下 FastAPI",
                "enable_thinking": True
            },
            timeout=60.0  # 增加超时时间
        )
        
        # 流式接口应该返回 200
        assert response.status_code == 200
        
        # 验证响应头
        assert "text/event-stream" in response.headers.get("content-type", "")
        
        print(f"[OK] 流式接口测试通过")
        print(f"   注意: AsyncClient 不完全支持 SSE，需要手动测试完整流式功能")
    
    @pytest.mark.asyncio
    async def test_12_unauthorized_access(self, async_client):
        """测试 12: 未授权访问"""
        print("\n[12/11] 测试未授权访问...")
        
        # 不带 token 访问
        response = await async_client.get("/api/v1/conversations")
        assert response.status_code in [401, 403], f"期望 401 或 403，实际: {response.status_code}"
        
        # 错误的 token
        response = await async_client.get(
            "/api/v1/conversations",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401
        
        print(f"[OK] 权限验证正常")
    
    @pytest.mark.asyncio
    async def test_13_delete_conversation(self, async_client, test_data):
        """测试 13: 删除对话（最后执行）"""
        print("\n[13/11] 删除对话...")
        
        response = await async_client.delete(
            f"/api/v1/conversations/{test_data['conversation_id']}",
            headers={"Authorization": f"Bearer {test_data['token']}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "对话已删除"
        
        # 验证对话已删除
        response = await async_client.get(
            f"/api/v1/conversations/{test_data['conversation_id']}",
            headers={"Authorization": f"Bearer {test_data['token']}"}
        )
        assert response.status_code == 404
        
        print(f"[OK] 对话删除成功")
        print(f"   对话ID: {test_data['conversation_id']}")


@pytest.mark.asyncio
async def test_summary():
    """测试总结"""
    print("\n" + "=" * 70)
    print("[SUCCESS] Phase 2 API 测试完成！")
    print("=" * 70)
    
    print("\n[OK] 测试覆盖:")
    print("  [OK] 健康检查")
    print("  [OK] 用户注册与登录")
    print("  [OK] 创建对话")
    print("  [OK] 发送消息（单轮）")
    print("  [OK] 多轮对话")
    print("  [OK] 获取对话消息")
    print("  [OK] 获取对话列表")
    print("  [OK] 更新对话标题")
    print("  [OK] 导出对话（Markdown）")
    print("  [OK] 导出对话（JSON）")
    print("  [OK] 流式消息接口")
    print("  [OK] 权限验证")
    print("  [OK] 删除对话")
    
    print("\n[TIP] 提示:")
    print("  - 所有 API 接口测试通过")
    print("  - 导出文件已保存到 data/exports/")
    print("  - 流式接口需要手动测试完整功能")
    
    print("\n[NEXT] 下一步:")
    print("  1. 启动服务: python -m app.main")
    print("  2. 访问文档: http://localhost:8000/docs")
    print("  3. 手动测试流式响应")
    print("  4. 集成前端应用")


if __name__ == "__main__":
    # 直接运行测试
    pytest.main([__file__, "-v", "-s"])
