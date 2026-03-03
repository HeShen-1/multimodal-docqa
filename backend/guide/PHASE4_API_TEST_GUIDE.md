# Phase 4 API 测试指南

本文档提供 Phase 4 新增功能的完整 API 测试示例。

## 前置条件

1. 启动 Redis 服务器
2. 启动 Celery Worker: `start_celery.bat`
3. 启动 FastAPI 服务器: `python -m uvicorn app.main:app --reload`
4. 已注册用户并获取 Token

---

## 1. 标签管理 API 测试

### 1.1 创建标签

**请求:**
```http
POST http://localhost:8000/api/v1/tags
Authorization: Bearer {your_token}
Content-Type: application/json

{
  "name": "重要文档",
  "color": "#EF4444",
  "description": "标记为重要的文档"
}
```

**响应:**
```json
{
  "code": 100000,
  "message": "创建成功",
  "data": {
    "id": "tag_123",
    "name": "重要文档",
    "color": "#EF4444",
    "description": "标记为重要的文档",
    "usageCount": 0,
    "createdAt": "2026-02-27T10:00:00Z",
    "updatedAt": "2026-02-27T10:00:00Z"
  }
}
```

### 1.2 获取标签列表

**请求:**
```http
GET http://localhost:8000/api/v1/tags?page=1&pageSize=20
Authorization: Bearer {your_token}
```

**响应:**
```json
{
  "code": 100000,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "tag_1",
        "name": "重要",
        "color": "#EF4444",
        "usageCount": 5
      }
    ],
    "total": 10,
    "page": 1,
    "pageSize": 20,
    "totalPages": 1
  }
}
```

### 1.3 搜索标签（自动补全）

**请求:**
```http
GET http://localhost:8000/api/v1/tags/search?keyword=工作&limit=10
Authorization: Bearer {your_token}
```

### 1.4 获取热门标签

**请求:**
```http
GET http://localhost:8000/api/v1/tags/popular?limit=10
Authorization: Bearer {your_token}
```

### 1.5 更新标签

**请求:**
```http
PATCH http://localhost:8000/api/v1/tags/{tag_id}
Authorization: Bearer {your_token}
Content-Type: application/json

{
  "name": "非常重要",
  "color": "#DC2626"
}
```

### 1.6 删除标签

**请求:**
```http
DELETE http://localhost:8000/api/v1/tags/{tag_id}
Authorization: Bearer {your_token}
```

---

## 2. 文档标签操作 API 测试

### 2.1 为文档添加标签

**请求:**
```http
POST http://localhost:8000/api/v1/documents/{document_id}/tags
Authorization: Bearer {your_token}
Content-Type: application/json

{
  "tagIds": ["tag_1", "tag_2", "tag_3"]
}
```

**响应:**
```json
{
  "code": 100000,
  "message": "添加成功",
  "data": [
    {
      "id": "tag_1",
      "name": "重要",
      "color": "#EF4444"
    },
    {
      "id": "tag_2",
      "name": "工作",
      "color": "#3B82F6"
    }
  ]
}
```

### 2.2 获取文档的所有标签

**请求:**
```http
GET http://localhost:8000/api/v1/documents/{document_id}/tags
Authorization: Bearer {your_token}
```

### 2.3 从文档移除标签

**请求:**
```http
DELETE http://localhost:8000/api/v1/documents/{document_id}/tags
Authorization: Bearer {your_token}
Content-Type: application/json

{
  "tagIds": ["tag_1"]
}
```

---

## 3. 批量上传 API 测试

### 3.1 批量上传文档

**请求:**
```http
POST http://localhost:8000/api/v1/documents/batch-upload
Authorization: Bearer {your_token}
Content-Type: multipart/form-data

files: [file1.pdf, file2.pdf, file3.pdf]
description: "批量上传的测试文档"
```

**响应:**
```json
{
  "code": 100000,
  "message": "批量上传成功",
  "data": {
    "batchId": "batch_123",
    "totalFiles": 3,
    "acceptedFiles": 3,
    "rejectedFiles": [],
    "documentIds": ["doc_1", "doc_2", "doc_3"]
  }
}
```

### 3.2 获取批量上传状态

**请求:**
```http
GET http://localhost:8000/api/v1/documents/batch/{batch_id}/status
Authorization: Bearer {your_token}
```

**响应:**
```json
{
  "code": 100000,
  "message": "success",
  "data": {
    "batchId": "batch_123",
    "totalFiles": 3,
    "completed": 2,
    "processing": 1,
    "failed": 0,
    "progress": 66,
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
      }
    ]
  }
}
```

---

## 4. 文档分享 API 测试

### 4.1 创建分享链接

**请求:**
```http
POST http://localhost:8000/api/v1/share/documents/{document_id}
Authorization: Bearer {your_token}
Content-Type: application/json

{
  "expiresInHours": 24,
  "password": "1234",
  "allowDownload": true,
  "maxAccessCount": 10
}
```

**响应:**
```json
{
  "code": 100000,
  "message": "创建成功",
  "data": {
    "id": "share_123",
    "documentId": "doc_123",
    "token": "abc123xyz789",
    "shareUrl": "http://localhost:8000/api/v1/share/abc123xyz789",
    "hasPassword": true,
    "allowDownload": true,
    "expiresAt": "2026-02-28T10:00:00Z",
    "accessCount": 0,
    "maxAccessCount": 10,
    "createdAt": "2026-02-27T10:00:00Z"
  }
}
```

### 4.2 访问分享链接（无需登录）

**请求:**
```http
POST http://localhost:8000/api/v1/share/{token}/access
Content-Type: application/json

{
  "password": "1234"
}
```

**响应:**
```json
{
  "code": 100000,
  "message": "访问成功",
  "data": {
    "documentId": "doc_123",
    "fileName": "example.pdf",
    "fileSize": 1024000,
    "allowDownload": true
  }
}
```

### 4.3 获取文档的所有分享链接

**请求:**
```http
GET http://localhost:8000/api/v1/share/documents/{document_id}?includeExpired=false
Authorization: Bearer {your_token}
```

**响应:**
```json
{
  "code": 100000,
  "message": "success",
  "data": [
    {
      "id": "share_1",
      "documentId": "doc_123",
      "token": "abc123",
      "shareUrl": "http://localhost:8000/api/v1/share/abc123",
      "hasPassword": true,
      "allowDownload": true,
      "expiresAt": "2026-02-28T10:00:00Z",
      "accessCount": 5,
      "maxAccessCount": 10,
      "createdAt": "2026-02-27T10:00:00Z"
    }
  ]
}
```

### 4.4 撤销分享链接

**请求:**
```http
DELETE http://localhost:8000/api/v1/share/{share_id}
Authorization: Bearer {your_token}
```

### 4.5 清理过期链接

**请求:**
```http
POST http://localhost:8000/api/v1/share/cleanup
Authorization: Bearer {your_token}
```

**响应:**
```json
{
  "code": 100000,
  "message": "清理了 5 个过期链接",
  "data": {
    "count": 5
  }
}
```

---

## 5. 完整测试流程

### 场景：批量上传文档并添加标签和分享

```python
import requests
import time

BASE_URL = "http://localhost:8000/api/v1"

# 1. 登录
login_response = requests.post(
    f"{BASE_URL}/auth/login",
    json={"username": "testuser", "password": "password123"}
)
token = login_response.json()["data"]["accessToken"]
headers = {"Authorization": f"Bearer {token}"}

# 2. 创建标签
tag_response = requests.post(
    f"{BASE_URL}/tags",
    headers=headers,
    json={
        "name": "项目文档",
        "color": "#3B82F6",
        "description": "项目相关文档"
    }
)
tag_id = tag_response.json()["data"]["id"]
print(f"✓ 创建标签: {tag_id}")

# 3. 批量上传文档
files = [
    ("files", open("doc1.pdf", "rb")),
    ("files", open("doc2.pdf", "rb")),
    ("files", open("doc3.pdf", "rb"))
]
upload_response = requests.post(
    f"{BASE_URL}/documents/batch-upload",
    headers=headers,
    files=files
)
batch_id = upload_response.json()["data"]["batchId"]
document_ids = upload_response.json()["data"]["documentIds"]
print(f"✓ 批量上传: {len(document_ids)} 个文档")

# 4. 等待处理完成
print("等待处理完成...")
while True:
    status_response = requests.get(
        f"{BASE_URL}/documents/batch/{batch_id}/status",
        headers=headers
    )
    status = status_response.json()["data"]
    print(f"  进度: {status['progress']}% (完成: {status['completed']}, 处理中: {status['processing']}, 失败: {status['failed']})")
    
    if status["processing"] == 0:
        break
    time.sleep(2)

print(f"✓ 处理完成: {status['completed']} 个成功, {status['failed']} 个失败")

# 5. 为所有文档添加标签
for doc_id in document_ids:
    requests.post(
        f"{BASE_URL}/documents/{doc_id}/tags",
        headers=headers,
        json={"tagIds": [tag_id]}
    )
print(f"✓ 为 {len(document_ids)} 个文档添加标签")

# 6. 为第一个文档创建分享链接
if document_ids:
    share_response = requests.post(
        f"{BASE_URL}/share/documents/{document_ids[0]}",
        headers=headers,
        json={
            "expiresInHours": 24,
            "password": "1234",
            "allowDownload": True
        }
    )
    share_data = share_response.json()["data"]
    print(f"✓ 创建分享链接: {share_data['shareUrl']}")
    print(f"  访问密码: 1234")
    print(f"  过期时间: {share_data['expiresAt']}")

print("\n✅ 所有操作完成！")
```

---

## 6. 错误处理测试

### 6.1 创建重复标签

**请求:**
```http
POST http://localhost:8000/api/v1/tags
Authorization: Bearer {your_token}
Content-Type: application/json

{
  "name": "重要",  // 已存在的标签名
  "color": "#EF4444"
}
```

**响应:**
```json
{
  "detail": "标签 '重要' 已存在"
}
```

### 6.2 批量上传超过限制

**请求:**
```http
POST http://localhost:8000/api/v1/documents/batch-upload
Authorization: Bearer {your_token}

files: [11个文件]  // 超过10个限制
```

**响应:**
```json
{
  "detail": "最多只能上传10个文件"
}
```

### 6.3 访问分享链接密码错误

**请求:**
```http
POST http://localhost:8000/api/v1/share/{token}/access
Content-Type: application/json

{
  "password": "wrong_password"
}
```

**响应:**
```json
{
  "detail": "访问密码错误"
}
```

---

## 7. 性能测试建议

### 7.1 批量上传性能

- 测试不同文件数量（1, 5, 10）
- 测试不同文件大小（1MB, 5MB, 10MB）
- 监控 Celery Worker 处理时间

### 7.2 标签查询性能

- 测试大量标签情况下的查询速度
- 测试搜索功能的响应时间
- 测试分页性能

### 7.3 分享链接性能

- 测试高并发访问分享链接
- 测试大量分享链接的查询性能

---

**更新时间**: 2026-02-27  
**版本**: Phase 4 v1.0

