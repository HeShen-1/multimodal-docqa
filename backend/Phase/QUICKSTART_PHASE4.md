# Phase 4 快速启动指南

## 概述

Phase 4 实现了文档管理增强功能，包括：
- ✅ 批量上传文档（最多10个）
- ✅ 标签系统（创建、管理、关联文档）
- ✅ 文档分享（生成临时分享链接）
- ✅ 异步任务处理（Celery）

---

## 环境准备

### 方式一：使用 Docker（推荐）⭐

使用 Docker 运行 PostgreSQL 和 Redis，无需手动安装。

#### 1. 安装 Docker Desktop

- Windows: https://www.docker.com/products/docker-desktop
- 确保 Docker Desktop 已启动

#### 2. 启动服务

```bash
# 启动 PostgreSQL 和 Redis
start_docker.bat

# 或手动启动
docker-compose up -d postgres redis
```

#### 3. 安装 Python 依赖

```bash
# 激活环境
conda activate multimodal-docqa

# 安装新依赖
pip install celery redis reportlab markdown2
```

**优势:**
- ✅ 一键启动，无需手动安装
- ✅ 数据持久化，重启不丢失
- ✅ 环境隔离，不影响系统
- ✅ 易于备份和迁移

---

### 方式二：手动安装

#### 1. 安装依赖

```bash
# 激活环境
conda activate multimodal-docqa

# 安装新依赖
pip install celery redis reportlab markdown2
```

#### 2. 启动 PostgreSQL

确保 PostgreSQL 已安装并运行在 `localhost:5432`

#### 3. 启动 Redis

**Windows:**
```bash
# 下载 Redis for Windows
# https://github.com/microsoftarchive/redis/releases

# 启动 Redis
redis-server
```

**Linux/Mac:**
```bash
redis-server
```

---

## 快速启动

### 方法一：使用 Docker（推荐）⭐

```bash
# 一键完成所有设置（包括启动 Docker 服务）
setup_phase4_docker.bat
```

这个脚本会自动：
1. 启动 PostgreSQL 和 Redis Docker 容器
2. 安装 Python 依赖
3. 初始化数据库
4. 创建默认标签

### 方法二：使用脚本（手动安装）

```bash
# 运行 Phase 4 设置脚本（需要手动启动 PostgreSQL 和 Redis）
setup_phase4.bat
```

### 方法三：手动启动

#### 1. 启动 Docker 服务（如果使用 Docker）

```bash
start_docker.bat
# 或
docker-compose up -d postgres redis
```

#### 2. 初始化数据库

```bash
python scripts/init_phase4_db.py
```

#### 3. 启动 Celery Worker

```bash
# Windows
celery -A app.celery_app worker --loglevel=info --pool=solo

# Linux/Mac
celery -A app.celery_app worker --loglevel=info
```

#### 4. 启动 FastAPI 服务器

```bash
python -m uvicorn app.main:app --reload
```

---

## 数据库结构

### 新增表

#### 1. tags（标签表）
```sql
- id: 标签ID
- name: 标签名称（唯一）
- color: 标签颜色（HEX格式）
- description: 标签描述
- usage_count: 使用次数
- created_at: 创建时间
- updated_at: 更新时间
```

#### 2. document_tags（文档-标签关联表）
```sql
- document_id: 文档ID（外键）
- tag_id: 标签ID（外键）
- created_at: 创建时间
```

#### 3. share_links（分享链接表）
```sql
- id: 分享ID
- document_id: 文档ID（外键）
- token: 分享Token（唯一）
- password: 访问密码（加密）
- allow_download: 是否允许下载
- expires_at: 过期时间
- access_count: 访问次数
- max_access_count: 最大访问次数
- created_by: 创建者ID（外键）
- created_at: 创建时间
- updated_at: 更新时间
```

#### 4. documents（文档表）
```sql
- id: 文档ID
- user_id: 所属用户ID
- file_name: 文件名
- file_type: 文件类型
- file_size: 文件大小
- file_path: 文件路径
- status: 处理状态
- description: 文档描述
- page_count: 页数
- chunk_count: 分块数量
- image_count: 图像数量
- metadata: 元数据（JSON）
- created_at: 创建时间
- updated_at: 更新时间
```

---

## API 接口

### 1. 标签管理

#### 创建标签
```http
POST /api/v1/tags
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "重要",
  "color": "#EF4444",
  "description": "重要文档"
}
```

#### 获取标签列表
```http
GET /api/v1/tags?page=1&pageSize=20&keyword=重要
Authorization: Bearer {token}
```

#### 获取热门标签
```http
GET /api/v1/tags/popular?limit=10
Authorization: Bearer {token}
```

#### 搜索标签（自动补全）
```http
GET /api/v1/tags/search?keyword=工&limit=10
Authorization: Bearer {token}
```

#### 更新标签
```http
PATCH /api/v1/tags/{tag_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "非常重要",
  "color": "#DC2626"
}
```

#### 删除标签
```http
DELETE /api/v1/tags/{tag_id}
Authorization: Bearer {token}
```

---

### 2. 文档标签操作

#### 为文档添加标签
```http
POST /api/v1/documents/{document_id}/tags
Authorization: Bearer {token}
Content-Type: application/json

{
  "tagIds": ["tag_id_1", "tag_id_2"]
}
```

#### 从文档移除标签
```http
DELETE /api/v1/documents/{document_id}/tags
Authorization: Bearer {token}
Content-Type: application/json

{
  "tagIds": ["tag_id_1"]
}
```

#### 获取文档的所有标签
```http
GET /api/v1/documents/{document_id}/tags
Authorization: Bearer {token}
```

---

### 3. 批量上传

#### 批量上传文档
```http
POST /api/v1/documents/batch-upload
Authorization: Bearer {token}
Content-Type: multipart/form-data

files: [file1.pdf, file2.pdf, ...]
description: "批量上传的文档"
```

**响应示例：**
```json
{
  "code": 100000,
  "message": "批量上传成功",
  "data": {
    "batchId": "batch_123",
    "totalFiles": 5,
    "acceptedFiles": 4,
    "rejectedFiles": [
      {
        "fileName": "invalid.txt",
        "reason": "不支持的文件类型: .txt"
      }
    ],
    "documentIds": ["doc_1", "doc_2", "doc_3", "doc_4"]
  }
}
```

#### 获取批量上传状态
```http
GET /api/v1/documents/batch/{batch_id}/status
Authorization: Bearer {token}
```

**响应示例：**
```json
{
  "code": 100000,
  "message": "success",
  "data": {
    "batchId": "batch_123",
    "totalFiles": 4,
    "completed": 2,
    "processing": 1,
    "failed": 1,
    "progress": 75,
    "documents": [
      {
        "document_id": "doc_1",
        "status": "completed",
        "message": "处理完成"
      },
      {
        "document_id": "doc_2",
        "status": "completed",
        "message": "处理完成"
      },
      {
        "document_id": "doc_3",
        "status": "processing",
        "message": "正在处理..."
      },
      {
        "document_id": "doc_4",
        "status": "failed",
        "message": "文档解析失败"
      }
    ]
  }
}
```

---

### 4. 文档分享

#### 创建分享链接
```http
POST /api/v1/share/documents/{document_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "expiresInHours": 24,
  "password": "1234",
  "allowDownload": true,
  "maxAccessCount": 10
}
```

**响应示例：**
```json
{
  "code": 100000,
  "message": "创建成功",
  "data": {
    "id": "share_123",
    "documentId": "doc_123",
    "token": "abc123xyz",
    "shareUrl": "http://localhost:8000/api/v1/share/abc123xyz",
    "hasPassword": true,
    "allowDownload": true,
    "expiresAt": "2026-02-28T10:00:00Z",
    "accessCount": 0,
    "maxAccessCount": 10,
    "createdAt": "2026-02-27T10:00:00Z"
  }
}
```

#### 访问分享链接
```http
POST /api/v1/share/{token}/access
Content-Type: application/json

{
  "password": "1234"
}
```

#### 获取文档的所有分享链接
```http
GET /api/v1/share/documents/{document_id}?includeExpired=false
Authorization: Bearer {token}
```

#### 撤销分享链接
```http
DELETE /api/v1/share/{share_id}
Authorization: Bearer {token}
```

#### 清理过期链接
```http
POST /api/v1/share/cleanup
Authorization: Bearer {token}
```

---

## 使用示例

### 示例 1：批量上传文档并添加标签

```python
import requests

# 1. 登录获取 token
login_response = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"username": "testuser", "password": "password123"}
)
token = login_response.json()["data"]["accessToken"]

headers = {"Authorization": f"Bearer {token}"}

# 2. 创建标签
tag_response = requests.post(
    "http://localhost:8000/api/v1/tags",
    headers=headers,
    json={"name": "项目文档", "color": "#3B82F6"}
)
tag_id = tag_response.json()["data"]["id"]

# 3. 批量上传文档
files = [
    ("files", open("doc1.pdf", "rb")),
    ("files", open("doc2.pdf", "rb")),
    ("files", open("doc3.pdf", "rb"))
]
upload_response = requests.post(
    "http://localhost:8000/api/v1/documents/batch-upload",
    headers=headers,
    files=files
)
batch_id = upload_response.json()["data"]["batchId"]
document_ids = upload_response.json()["data"]["documentIds"]

# 4. 等待处理完成
import time
while True:
    status_response = requests.get(
        f"http://localhost:8000/api/v1/documents/batch/{batch_id}/status",
        headers=headers
    )
    status = status_response.json()["data"]
    print(f"进度: {status['progress']}%")
    
    if status["processing"] == 0:
        break
    time.sleep(2)

# 5. 为所有文档添加标签
for doc_id in document_ids:
    requests.post(
        f"http://localhost:8000/api/v1/documents/{doc_id}/tags",
        headers=headers,
        json={"tagIds": [tag_id]}
    )

print("批量上传并标记完成！")
```

### 示例 2：创建分享链接

```python
import requests

# 1. 登录
login_response = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"username": "testuser", "password": "password123"}
)
token = login_response.json()["data"]["accessToken"]
headers = {"Authorization": f"Bearer {token}"}

# 2. 创建分享链接（24小时有效，需要密码）
share_response = requests.post(
    f"http://localhost:8000/api/v1/share/documents/{document_id}",
    headers=headers,
    json={
        "expiresInHours": 24,
        "password": "1234",
        "allowDownload": True,
        "maxAccessCount": 10
    }
)

share_data = share_response.json()["data"]
print(f"分享链接: {share_data['shareUrl']}")
print(f"访问密码: 1234")
print(f"过期时间: {share_data['expiresAt']}")

# 3. 访问分享链接（无需登录）
access_response = requests.post(
    f"http://localhost:8000/api/v1/share/{share_data['token']}/access",
    json={"password": "1234"}
)

if access_response.status_code == 200:
    doc_info = access_response.json()["data"]
    print(f"文档名称: {doc_info['fileName']}")
    print(f"文件大小: {doc_info['fileSize']}")
```

---

## 测试

### 运行测试

```bash
# 运行 Phase 4 测试
pytest tests/test_phase4.py -v

# 运行所有测试
pytest -v
```

---

## 故障排查

### 1. Docker 相关问题

**问题：** Docker 容器无法启动

**解决方案：**
```bash
# 查看容器状态
docker-compose ps

# 查看日志
docker-compose logs postgres
docker-compose logs redis

# 重启容器
docker-compose restart
```

**问题：** 端口被占用

**解决方案：**
```bash
# 查看端口占用
netstat -ano | findstr :5432
netstat -ano | findstr :6379

# 修改 docker-compose.yml 中的端口映射
```

### 2. 数据库连接问题

**问题：** 无法连接到 PostgreSQL

**解决方案：**
- 确保 Docker 容器已启动：`docker-compose ps`
- 等待容器完全启动（约 10-15 秒）
- 检查连接配置：`localhost:5432`

**问题：** 无法连接到 Redis

**解决方案：**
```bash
# 测试 Redis 连接
docker exec multimodal-docqa-redis redis-cli ping
# 应该返回 PONG
```

### 3. Celery Worker 无法启动

**问题：** `celery -A app.celery_app worker` 报错

**解决方案：**
- Windows 用户必须使用 `--pool=solo` 参数
- 确保 Redis 已启动
- 检查 Redis 连接配置

### 4. 批量上传失败

**问题：** 批量上传后所有文档都失败

**解决方案：**
- 检查 Celery Worker 是否运行
- 查看 Celery Worker 日志
- 确保文件格式和大小符合要求

### 5. 分享链接无法访问

**问题：** 访问分享链接返回 403

**解决方案：**
- 检查链接是否过期
- 验证访问密码是否正确
- 检查访问次数是否达到上限

### 6. 标签无法添加到文档

**问题：** 添加标签时报错 "文档不存在"

**解决方案：**
- 确保文档已在数据库中（需要迁移现有文档）
- 检查 document_id 是否正确
- 运行数据库迁移脚本

---

## 性能优化

### 1. Celery 配置优化

```python
# app/celery_app.py
celery_app.conf.update(
    worker_prefetch_multiplier=1,  # 每次只取1个任务
    worker_max_tasks_per_child=1000,  # 每个worker最多处理1000个任务后重启
    task_time_limit=3600,  # 任务超时时间（秒）
)
```

### 2. Redis 连接池

```python
# 使用连接池提高性能
from redis import ConnectionPool

pool = ConnectionPool(
    host='localhost',
    port=6379,
    max_connections=50
)
```

### 3. 批量操作优化

- 批量上传限制为10个文件
- 使用异步任务避免阻塞
- 实时推送处理进度

---

## 下一步

Phase 4 完成后，可以继续开发：

- **Phase 5**: 高级检索功能（多文档检索、Rerank重排序）
- **Phase 6**: 智能分析功能（文档摘要、关键词提取）
- **Phase 7**: 系统监控与管理
- **Phase 8**: 系统稳定性增强

---

## 参考文档

- [API接口文档 v2.0](../../docs/apiDoc/API接口文档_v2.md)
- [后端开发文档 v2.0](../../docs/backendDoc/后端开发文档_v2.md)
- [Celery 官方文档](https://docs.celeryproject.org/)
- [Redis 官方文档](https://redis.io/documentation)

---

**更新时间**: 2026-02-27  
**版本**: Phase 4 v1.0

