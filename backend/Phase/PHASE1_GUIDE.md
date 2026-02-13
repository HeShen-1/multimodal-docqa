# Phase 1: 用户认证与权限管理 - 实施指南

## 概述

本文档描述 Phase 1（用户认证与权限管理）的实施细节和使用说明。

## 已实现功能

### 1. 核心组件

- ✅ **AuthService**: 认证服务，处理密码加密、Token生成和验证
- ✅ **PermissionService**: 权限服务，提供基于角色的访问控制
- ✅ **RateLimiter**: 限流器，防止API滥用

### 2. API接口

- ✅ `POST /api/v1/auth/register` - 用户注册
- ✅ `POST /api/v1/auth/login` - 用户登录
- ✅ `POST /api/v1/auth/logout` - 用户登出
- ✅ `POST /api/v1/auth/refresh` - 刷新Token
- ✅ `GET /api/v1/auth/me` - 获取当前用户信息

### 3. 数据库表

- ✅ `users` - 用户信息表
- ✅ `token_blacklist` - Token黑名单表

## 部署步骤

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 文件并根据实际情况修改：

```bash
# 复制配置模板
cp .env.example .env

# 或在 Windows PowerShell 中
Copy-Item .env.example .env
```

然后编辑 `.env` 文件，修改以下关键配置：

- **POSTGRES_PASSWORD**: 你的 PostgreSQL 密码
- **SECRET_KEY**: 生成强随机密钥（生产环境必须修改）
  ```bash
  # 生成随机密钥
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- **REDIS_PASSWORD**: 如果 Redis 设置了密码，填写密码；否则留空

完整的配置说明请查看 `.env.example` 文件中的注释。

### 3. 初始化数据库

```bash
# 创建数据库表
python scripts/init_auth_db.py

# 如果需要重建表（会删除所有数据）
python scripts/init_auth_db.py drop
```

### 4. 启动服务

```bash
# 开发模式
python -m app.main

# 或使用 uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API 使用示例

### 1. 用户注册

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "Test1234"
  }'
```

响应：
```json
{
  "id": "uuid",
  "username": "testuser",
  "email": "test@example.com",
  "role": "user",
  "is_active": true,
  "created_at": "2026-02-13T10:00:00Z"
}
```

### 2. 用户登录

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "Test1234"
  }'
```

响应：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### 3. 获取用户信息

```bash
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 4. 刷新Token

```bash
curl -X POST "http://localhost:8000/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "YOUR_REFRESH_TOKEN"
  }'
```

## 在其他接口中使用认证

### 方法1: 使用依赖注入

```python
from fastapi import APIRouter, Depends
from app.services.permission_service import get_current_user

router = APIRouter()

@router.get("/protected")
async def protected_route(current_user: dict = Depends(get_current_user)):
    """需要认证的接口"""
    return {
        "message": f"Hello {current_user['username']}",
        "user_id": current_user["user_id"]
    }
```

### 方法2: 要求管理员权限

```python
from app.services.permission_service import require_admin

@router.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: dict = Depends(require_admin)
):
    """只有管理员可以访问"""
    # 删除用户逻辑
    pass
```

## 安全建议

1. **生产环境配置**
   - 使用强随机字符串作为 `SECRET_KEY`
   - 启用 HTTPS
   - 配置合适的 CORS 策略

2. **密码策略**
   - 最小长度: 8字符
   - 必须包含字母和数字
   - 建议添加特殊字符要求

3. **Token管理**
   - Access Token: 24小时有效
   - Refresh Token: 7天有效
   - 登出时将Token加入黑名单

4. **限流保护**
   - 登录接口: 5次/分钟
   - 注册接口: 3次/分钟
   - 其他接口: 60次/分钟

## 测试

运行单元测试：

```bash
pytest tests/unit/test_auth.py -v
```

## 故障排查

### 1. Redis连接失败

确保Redis服务正在运行：
```bash
redis-cli ping
# 应该返回 PONG
```

### 2. 数据库连接失败

检查PostgreSQL服务和配置：
```bash
psql -h localhost -U postgres -d multimodal_docqa
```

### 3. Token验证失败

- 检查 `SECRET_KEY` 配置是否一致
- 确认Token未过期
- 检查Token格式是否正确（Bearer token）

## 下一步

Phase 1 完成后，可以继续实施：

- **Phase 2**: 对话管理功能
- **Phase 3**: 文档管理增强
- **Phase 4**: 高级检索功能

## 技术支持

如有问题，请查看：
- API文档: http://localhost:8000/docs
- 日志文件: `logs/app.log`

