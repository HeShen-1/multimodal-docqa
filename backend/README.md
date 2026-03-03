# 多模态文档智能问答系统 - 后端

基于 FastAPI + Ollama + ChromaDB 的本地化文档问答系统

## 🚀 快速启动

### 1. 启动所有服务

```bash
start_services.bat
```

这会启动：
- PostgreSQL (Docker)
- Redis (Docker)
- Celery Worker (Docker)

### 2. 启动 FastAPI

```bash
conda activate multimodal-docqa
python -m uvicorn app.main:app --reload
```

### 3. 访问应用

- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/api/v1/health

---

## 📦 技术栈

### 后端框架
- **FastAPI** 0.115.0 - 现代化 Web 框架
- **Uvicorn** - ASGI 服务器
- **Pydantic** 2.8.0 - 数据验证

### 数据库
- **PostgreSQL** 15 (Docker) - 关系型数据库
- **Redis** 7 (Docker) - 缓存和消息队列
- **ChromaDB** - 向量数据库

### AI/ML
- **Ollama** - 本地 LLM 服务
- **PaddleOCR** - OCR 识别
- **PyMuPDF** - PDF 处理

### 异步任务
- **Celery** 5.3.6 (Docker) - 分布式任务队列

---

## 🎯 核心功能

### Phase 1: 用户认证 ✅
- 用户注册和登录
- JWT Token 管理
- 权限控制
- 会话管理
- API 限流

### Phase 2: 对话管理 ✅
- 多轮对话
- RAG 检索整合
- 流式响应 (SSE)
- 对话导出 (Markdown/JSON/PDF)
- 上下文管理

### Phase 3: 缓存优化 ✅
- 多级缓存 (L1 本地 + L2 Redis)
- 缓存装饰器
- 缓存统计和监控
- 热点键分析

### Phase 4: 文档管理增强 ✅
- 批量上传文档 (最多10个)
- 标签系统
- 文档分享 (密码保护、过期控制)
- 异步处理 (Celery)

---

## 📊 服务架构

```
┌─────────────────────────────────────────┐
│           FastAPI (本地)                 │
│         localhost:8000                   │
└─────────────────┬───────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
    ▼             ▼             ▼
┌────────┐  ┌──────────┐  ┌──────────┐
│PostgreSQL Redis      │  │  Celery  │
│ (Docker) │ (Docker)  │  │ (Docker) │
│  :5432   │  :6379    │  │  Worker  │
└──────────┘ └──────────┘  └──────────┘
```

---

## 🛠️ 开发指南

### 环境要求

- Python 3.11+
- Docker Desktop
- Conda
- Ollama (本地运行)

### 首次设置

```bash
# 1. 创建 conda 环境
conda create -n multimodal-docqa python=3.11
conda activate multimodal-docqa

# 2. 安装依赖
pip install -r requirements.txt

# 3. 初始化数据库
python scripts/init_phase4_db.py

# 4. 启动服务
start_services.bat

# 5. 启动 FastAPI
python -m uvicorn app.main:app --reload
```

### 日常开发

```bash
# 1. 启动 Docker 服务
start_services.bat

# 2. 启动 FastAPI
python -m uvicorn app.main:app --reload

# 3. 开始开发
# FastAPI 会自动重载代码更改
```

### 修改 Celery 任务

```bash
# 重新构建并重启 Celery Worker
docker-compose up -d --build celery-worker
```

---

## 📝 可用脚本

### 核心脚本
- `start_services.bat` - 启动所有 Docker 服务
- `stop_services.bat` - 停止所有服务
- `check_docker.bat` - 检查 Docker 状态
- `cleanup_docker.bat` - 清理未使用的容器

### 设置脚本
- `setup_phase4_docker.bat` - Phase 4 完整设置

### 测试脚本
- `run_testsPhase2.bat` - Phase 2 测试
- `run_testsPhase3.bat` - Phase 3 测试
- `run_testsPhase4.bat` - Phase 4 测试

---

## 🔍 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看 Celery Worker 日志
docker-compose logs -f celery-worker

# 查看 PostgreSQL 日志
docker-compose logs -f postgres

# 查看 Redis 日志
docker-compose logs -f redis
```

---

## 🧪 运行测试

```bash
# 运行所有测试
pytest -v

# 运行特定 Phase 测试
pytest tests/test_phase4.py -v

# 生成覆盖率报告
pytest --cov=app tests/
```

---

## 📚 文档

- [快速启动指南](./README_START.md) - 详细的启动说明
- [Phase 4 文档](./Phase/QUICKSTART_PHASE4.md) - Phase 4 功能说明
- [API 测试指南](./docs/PHASE4_API_TEST_GUIDE.md) - API 测试示例
- [Docker 指南](./docs/DOCKER_GUIDE.md) - Docker 使用说明
- [Docker 脚本指南](./DOCKER_SCRIPTS_GUIDE.md) - 脚本参考

---

## 🔧 配置

### 环境变量

创建 `.env` 文件：

```env
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=multimodal_docqa

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434/api
OLLAMA_LLM_MODEL=qwen3-vl:2b-thinking-q4_K_M
OLLAMA_EMBEDDING_MODEL=qwen3-embedding:0.6b-fp16

# JWT
SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_DAYS=7
```

---

## 🎯 API 端点

### 认证
- `POST /api/v1/auth/register` - 用户注册
- `POST /api/v1/auth/login` - 用户登录
- `POST /api/v1/auth/logout` - 用户登出
- `POST /api/v1/auth/refresh` - 刷新 Token
- `GET /api/v1/auth/me` - 获取用户信息

### 文档管理
- `POST /api/v1/documents/upload` - 上传文档
- `POST /api/v1/documents/batch-upload` - 批量上传
- `GET /api/v1/documents` - 获取文档列表
- `GET /api/v1/documents/{id}` - 获取文档详情
- `DELETE /api/v1/documents/{id}` - 删除文档

### 标签管理
- `POST /api/v1/tags` - 创建标签
- `GET /api/v1/tags` - 获取标签列表
- `GET /api/v1/tags/popular` - 获取热门标签
- `GET /api/v1/tags/search` - 搜索标签

### 文档分享
- `POST /api/v1/share/documents/{id}` - 创建分享链接
- `POST /api/v1/share/{token}/access` - 访问分享链接
- `GET /api/v1/share/documents/{id}` - 获取分享列表
- `DELETE /api/v1/share/{id}` - 撤销分享

### 对话管理
- `POST /api/v1/conversations` - 创建对话
- `POST /api/v1/conversations/{id}/messages` - 发送消息
- `GET /api/v1/conversations` - 获取对话列表
- `GET /api/v1/conversations/{id}` - 获取对话详情
- `DELETE /api/v1/conversations/{id}` - 删除对话

---

## 🐛 故障排查

### Celery Worker 无法启动

```bash
# 查看日志
docker-compose logs celery-worker

# 重新构建
docker-compose up -d --build celery-worker
```

### FastAPI 无法连接数据库

```bash
# 检查 PostgreSQL
docker exec multimodal-docqa-postgres psql -U postgres -c "SELECT 1;"

# 检查配置
cat app/config.py | grep postgres
```

### Redis 连接失败

```bash
# 测试 Redis
docker exec multimodal-docqa-redis redis-cli ping
```

---

## 📈 性能监控

```bash
# 查看容器资源使用
docker stats

# 查看 Celery 任务状态
docker exec multimodal-docqa-celery celery -A app.celery_app inspect active

# 查看 Celery 统计
docker exec multimodal-docqa-celery celery -A app.celery_app inspect stats
```

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

MIT License

---

**版本**: v2.0 (Phase 4)  
**更新时间**: 2026-02-27  
**状态**: ✅ 生产就绪
