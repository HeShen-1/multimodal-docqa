# Phase 1 快速开始指南

##  已创建的文件

-  .env.example - 环境变量配置模板
-  setup_phase1.ps1 - 快速配置检查脚本
-  PHASE1_GUIDE.md - 详细部署指南
-  PHASE1_SUMMARY.md - 实施总结

##  快速开始（3步）

### 步骤 1: 配置环境变量

```bash
# 复制配置模板
Copy-Item .env.example .env

# 编辑 .env 文件，修改以下配置：
# - POSTGRES_PASSWORD（你的数据库密码）
# - SECRET_KEY（生成强随机密钥）
```

生成安全密钥：
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 步骤 2: 初始化数据库

```bash
# 创建数据库
psql -U postgres -c "CREATE DATABASE multimodal_docqa;"

# 初始化表结构
python scripts/init_auth_db.py
```

### 步骤 3: 启动服务

```bash
python -m app.main
```

访问 API 文档：http://localhost:8000/docs

##  使用配置检查脚本

运行自动检查脚本：
```powershell
.\setup_phase1.ps1
```

该脚本会检查：
-  环境变量配置
-  PostgreSQL 连接
-  Redis 连接
-  Python 依赖
-  下一步操作提示

##  配置说明

### 必须修改的配置

1. **POSTGRES_PASSWORD** - 数据库密码
2. **SECRET_KEY** - JWT 密钥（生产环境必须使用强随机字符串）

### 可选配置

- **REDIS_PASSWORD** - 如果 Redis 有密码
- **RATE_LIMIT_*** - 限流策略
- **ACCESS_TOKEN_EXPIRE_MINUTES** - Token 有效期

详细配置说明请查看 .env.example 文件。

##  测试 API

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

### 2. 用户登录

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "Test1234"
  }'
```

### 3. 获取用户信息

```bash
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

##  更多文档

- **PHASE1_GUIDE.md** - 完整部署指南
- **PHASE1_SUMMARY.md** - 技术实施总结
- **.env.example** - 配置参数说明

##  注意事项

1. **不要提交 .env 文件到版本控制**
2. **生产环境必须修改 SECRET_KEY**
3. **确保 PostgreSQL 和 Redis 服务已启动**
4. **首次运行前必须初始化数据库**

##  故障排查

### Redis 连接失败
```bash
# 检查 Redis 是否运行
redis-cli ping
# 应该返回 PONG
```

### PostgreSQL 连接失败
```bash
# 检查 PostgreSQL 服务
psql -h localhost -U postgres -d postgres
```

### 依赖安装问题
```bash
# 重新安装依赖
pip install -r requirements.txt --upgrade
```

##  获取帮助

- 查看日志：logs/app.log
- API 文档：http://localhost:8000/docs
- 详细指南：PHASE1_GUIDE.md

---

**Phase 1 开发完成！** 

下一步：Phase 2 - 对话管理功能
