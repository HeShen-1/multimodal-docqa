"""测试配置"""
import pytest
import asyncio
import warnings
import sys
import os
import requests
from pathlib import Path
import io


@pytest.fixture(scope="module")
def event_loop():
    """为整个测试模块创建一个事件循环"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    
    # 在关闭事件循环前，先清理数据库引擎
    deps = sys.modules.get("app.dependencies")
    if deps is not None and getattr(deps, "_engine", None) is not None:
        try:
            # 强制关闭所有连接
            loop.run_until_complete(deps._engine.dispose())
        except Exception:
            pass  # 忽略清理时的错误
        finally:
            deps._engine = None
            deps._async_session_maker = None
    
    # 取消所有待处理的任务
    try:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        # 等待所有任务取消完成
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except Exception:
        pass
    
    # 最后关闭事件循环
    loop.close()


# 过滤 SQLAlchemy 连接池清理时的异常输出
@pytest.fixture(scope="session", autouse=True)
def suppress_cleanup_errors():
    """抑制测试清理时的无害错误输出"""
    import logging
    
    # 降低 SQLAlchemy 连接池的日志级别
    logging.getLogger('sqlalchemy.pool').setLevel(logging.CRITICAL)
    
    # 抑制 SQLAlchemy 的 SAWarning
    warnings.filterwarnings("ignore", category=Warning, module="sqlalchemy")
    
    # 设置环境变量来抑制 asyncpg 的警告
    os.environ['PYTHONWARNINGS'] = 'ignore::Warning'
    
    yield


@pytest.fixture
def test_settings():
    """测试配置"""
    from app.config import Settings
    return Settings(
        debug=True,
        ollama_base_url="http://localhost:11434",
        chroma_persist_dir="./data/test_vector_db"
    )


@pytest.fixture(scope="module")
def client():
    """创建测试客户端 - 使用 requests 库"""
    class RequestsClient:
        def __init__(self, base_url):
            self.base_url = base_url
            self.session = requests.Session()
        
        def post(self, url, **kwargs):
            return self.session.post(f"{self.base_url}{url}", **kwargs)
        
        def get(self, url, **kwargs):
            return self.session.get(f"{self.base_url}{url}", **kwargs)
        
        def put(self, url, **kwargs):
            return self.session.put(f"{self.base_url}{url}", **kwargs)
        
        def delete(self, url, **kwargs):
            return self.session.delete(f"{self.base_url}{url}", **kwargs)
        
        def close(self):
            self.session.close()
    
    client = RequestsClient("http://127.0.0.1:8000")
    yield client
    client.close()


@pytest.fixture(scope="module")
def auth_headers(client):
    """创建认证头 - 模块级别共享"""
    import time
    
    # 先注册用户
    register_data = {
        "username": "testuser_phase4",
        "email": "testphase4@example.com",
        "password": "password123"
    }
    
    # 尝试注册（如果已存在会失败，但没关系）
    try:
        register_response = client.post("/api/v1/auth/register", json=register_data)
        if register_response.status_code == 201:
            print(f"✓ 用户注册成功")
        elif register_response.status_code == 400:
            print(f"✓ 用户已存在，跳过注册")
    except Exception as e:
        print(f"注册错误: {e}")
    
    # 登录获取 token
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser_phase4", "password": "password123"}
    )
    
    if login_response.status_code == 200:
        response_data = login_response.json()
        token = response_data["access_token"]
        print(f"✓ 登录成功，获取 Token")
        return {"Authorization": f"Bearer {token}"}
    else:
        raise Exception(f"Login failed: {login_response.status_code} - {login_response.text}")


@pytest.fixture(scope="module")
def test_document_id(client, auth_headers: dict):
    """创建测试文档并返回 ID - 模块级别共享"""
    # 创建一个简单的测试 PDF 文件
    content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 100 700 Td (Test Phase 4 Document) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000317 00000 n\ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n410\n%%EOF"
    
    files = {
        "file": ("test_phase4_document.pdf", io.BytesIO(content), "application/pdf")
    }
    
    response = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files=files
    )
    
    if response.status_code == 201:
        response_data = response.json()
        # 尝试从 data.id 或 data.documentId 获取
        doc_id = response_data.get("data", {}).get("id") or response_data.get("data", {}).get("documentId")
        if doc_id:
            print(f"✓ 测试文档创建成功: {doc_id}")
            return doc_id
        else:
            print(f"文档上传成功但响应格式异常: {response.text}")
            raise Exception(f"Failed to parse document ID from response: {response.text}")
    else:
        print(f"文档上传失败: {response.status_code} - {response.text}")
        raise Exception(f"Failed to create test document: {response.status_code}")
