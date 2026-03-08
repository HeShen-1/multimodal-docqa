import pytest
import asyncio
from httpx import AsyncClient
from datetime import datetime

from app.main import app
from app.services.auth_service import auth_service
from app.schemas.auth import UserLogin, UserRegister


@pytest.fixture
def test_user_data():
    """测试用户数据"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "Test1234"
    }


@pytest.mark.asyncio
async def test_register_success(test_user_data):
    """测试用户注册成功"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/auth/register", json=test_user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == test_user_data["username"]
        assert data["email"] == test_user_data["email"]
        assert "password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_username(test_user_data):
    """测试重复用户名注册"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 第一次注册
        await client.post("/api/v1/auth/register", json=test_user_data)
        
        # 第二次注册相同用户名
        response = await client.post("/api/v1/auth/register", json=test_user_data)
        
        assert response.status_code == 400
        assert "用户名已存在" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_invalid_password():
    """测试无效密码"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/auth/register", json={
            "username": "testuser2",
            "email": "test2@example.com",
            "password": "short"  # 太短
        })
        
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(test_user_data):
    """测试登录成功"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 先注册
        await client.post("/api/v1/auth/register", json=test_user_data)
        
        # 登录
        response = await client.post("/api/v1/auth/login", json={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(test_user_data):
    """测试错误密码"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 先注册
        await client.post("/api/v1/auth/register", json=test_user_data)
        
        # 使用错误密码登录
        response = await client.post("/api/v1/auth/login", json={
            "username": test_user_data["username"],
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user(test_user_data):
    """测试获取当前用户信息"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 注册并登录
        await client.post("/api/v1/auth/register", json=test_user_data)
        login_response = await client.post("/api/v1/auth/login", json={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        })
        
        token = login_response.json()["access_token"]
        
        # 获取用户信息
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user_data["username"]
        assert data["email"] == test_user_data["email"]


@pytest.mark.asyncio
async def test_refresh_token(test_user_data):
    """测试刷新Token"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 注册并登录
        await client.post("/api/v1/auth/register", json=test_user_data)
        login_response = await client.post("/api/v1/auth/login", json={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        })
        
        refresh_token = login_response.json()["refresh_token"]
        
        # 刷新Token
        response = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data


def test_password_hashing():
    """测试密码加密"""
    password = "Test1234"
    hashed = auth_service.hash_password(password)
    
    assert hashed != password
    assert auth_service.verify_password(password, hashed)
    assert not auth_service.verify_password("wrongpassword", hashed)


def test_password_hashing_legacy_compatibility():
    """测试旧版密码哈希兼容与升级判断"""
    password = "Test1234"
    legacy_hashed = auth_service.pwd_context.hash(password)
    modern_hashed = auth_service.hash_password(password)

    assert auth_service.verify_password(password, legacy_hashed)
    assert auth_service.needs_password_rehash(password, legacy_hashed)
    assert not auth_service.needs_password_rehash(password, modern_hashed)


def test_auth_schema_normalization():
    """测试登录/注册字段标准化"""
    register_data = UserRegister(
        username="  River_User  ",
        email="  River@Example.COM  ",
        password="Test1234",
    )
    login_data = UserLogin(
        username="  river_user  ",
        password="Test1234",
    )

    assert register_data.username == "River_User"
    assert register_data.email == "river@example.com"
    assert login_data.username == "river_user"

    register_data_zero_width = UserRegister(
        username="\ufeff  River_User  \u200b",
        email="River@Example.COM",
        password="Test1234",
    )
    login_data_zero_width = UserLogin(
        username="\ufeff  river_user  \u200b",
        password="Test1234",
    )

    assert register_data_zero_width.username == "River_User"
    assert register_data_zero_width.email == "river@example.com"
    assert login_data_zero_width.username == "river_user"


def test_password_variant_compatibility():
    """测试密码输入变体兼容（空格/零宽字符）"""
    password = "Test1234"
    hashed = auth_service.hash_password(password)

    assert auth_service.verify_password(f"  {password}  ", hashed)
    assert auth_service.verify_password(f"\ufeff{password}\u200b", hashed)


def test_token_creation():
    """测试Token创建"""
    data = {
        "sub": "user123",
        "username": "testuser",
        "role": "user"
    }
    
    token = auth_service.create_access_token(data)
    assert token is not None
    assert isinstance(token, str)
    
    # 验证Token
    payload = auth_service.verify_token(token)
    assert payload["sub"] == data["sub"]
    assert payload["username"] == data["username"]

