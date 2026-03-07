# API接口文档 v1.0

## 文档信息

**项目名称**: 多模态文档智能问答系统  
**API版本**: v1.0  
**Base URL**: `http://localhost:8000/api/v1`  
**文档更新**: 2025-02-13

---

## 目录

1. [接口概览](#接口概览)
2. [认证方式](#认证方式)
3. [通用说明](#通用说明)
4. [文档管理接口](#文档管理接口)
5. [查询问答接口](#查询问答接口)
6. [系统管理接口](#系统管理接口)
7. [错误码说明](#错误码说明)
8. [数据模型](#数据模型)

---

## 接口概览

### 接口列表

| 模块 | 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|------|
| 文档管理 | 上传文档 | POST | `/documents/upload` | 上传常见文档与文本文件 |
| 文档管理 | 获取文档列表 | GET | `/documents` | 分页获取文档列表 |
| 文档管理 | 获取文档详情 | GET | `/documents/{id}` | 获取单个文档信息 |
| 文档管理 | 删除文档 | DELETE | `/documents/{id}` | 删除指定文档 |
| 文档管理 | 获取文档处理状态 | GET | `/documents/{id}/status` | 查询文档处理进度 |
| 查询问答 | 执行问答 | POST | `/query` | 基于文档的智能问答 |
| 查询问答 | 流式问答 | POST | `/query/stream` | 流式返回问答结果 |
| 查询问答 | 获取历史记录 | GET | `/query/history` | 获取问答历史 |
| 系统管理 | 健康检查 | GET | `/health` | 检查服务状态 |
| 系统管理 | 获取统计信息 | GET | `/stats` | 获取系统统计数据 |

---

## 认证方式

### JWT Token认证

所有需要认证的接口都需要在请求头中携带JWT Token：

```http
Authorization: Bearer <your_jwt_token>
```

**注意**: 当前版本认证功能正在开发中，暂时可以跳过认证直接访问接口。

---

## 通用说明

### 请求格式

- **Content-Type**: `application/json`（除文件上传外）
- **字符编码**: UTF-8
- **时间格式**: ISO 8601（`2025-02-13T10:00:00Z`）

### 响应格式

所有接口统一返回以下格式：

```json
{
  "code": 100000,
  "message": "success",
  "data": {},
  "timestamp": "2025-02-13T10:00:00Z"
}
```

**字段说明**:
- `code`: 业务状态码（详见错误码说明）
- `message`: 响应消息
- `data`: 响应数据（具体结构见各接口说明）
- `timestamp`: 服务器时间戳

### 分页参数

需要分页的接口统一使用以下参数：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | integer | 否 | 1 | 页码（从1开始）|
| pageSize | integer | 否 | 10 | 每页数量（1-100）|
| sortBy | string | 否 | createdAt | 排序字段 |
| sortOrder | string | 否 | desc | 排序方向（asc/desc）|

**分页响应格式**:
```json
{
  "items": [],
  "total": 100,
  "page": 1,
  "pageSize": 10,
  "totalPages": 10
}
```

---

## 文档管理接口

### 1. 上传文档

上传常见文档/文本文件进行处理（如 PDF、DOCX、TXT、MD、CSV、JSON、HTML、XML、YAML）。

**接口地址**: `POST /api/v1/documents/upload`

**请求头**:
```http
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | 是 | 文档文件（支持：PDF、DOCX、TXT、MD、CSV、TSV、JSON、JSONL、HTML、XML、YAML、LOG、INI）|
| description | string | 否 | 文档描述 |

**请求示例**:
```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@/path/to/document.pdf" \
  -F "description=技术文档"
```

**响应示例**:
```json
{
  "code": 100000,
  "message": "上传成功",
  "data": {
    "documentId": "550e8400-e29b-41d4-a716-446655440001",
    "fileName": "document.pdf",
    "fileSize": 2048576,
    "status": "processing",
    "createdAt": "2025-02-13T10:00:00Z"
  },
  "timestamp": "2025-02-13T10:00:00Z"
}
```

**状态码**:
- 201: 上传成功
- 400: 文件格式不支持
- 413: 文件过大（超过10MB）
- 500: 服务器错误

---

### 2. 获取文档列表

分页获取用户上传的文档列表。

**接口地址**: `GET /api/v1/documents`

**请求参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | integer | 否 | 1 | 页码 |
| pageSize | integer | 否 | 10 | 每页数量 |
| status | string | 否 | - | 过滤状态（processing/completed/failed）|
| keyword | string | 否 | - | 搜索关键词 |

**请求示例**:
```bash
curl -X GET "http://localhost:8000/api/v1/documents?page=1&pageSize=10&status=completed" \
  -H "Authorization: Bearer <token>"
```

**响应示例**:
```json
{
  "code": 100000,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "fileName": "技术文档.pdf",
        "fileType": "application/pdf",
        "fileSize": 2048576,
        "status": "completed",
        "description": "技术文档",
        "pageCount": 50,
        "chunkCount": 120,
        "imageCount": 15,
        "createdAt": "2025-02-13T10:00:00Z",
        "updatedAt": "2025-02-13T10:05:00Z"
      }
    ],
    "total": 25,
    "page": 1,
    "pageSize": 10,
    "totalPages": 3
  },
  "timestamp": "2025-02-13T10:00:00Z"
}
```

---

### 3. 获取文档详情

获取单个文档的详细信息。

**接口地址**: `GET /api/v1/documents/{id}`

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 文档ID（UUID）|

**请求示例**:
```bash
curl -X GET http://localhost:8000/api/v1/documents/550e8400-e29b-41d4-a716-446655440001 \
  -H "Authorization: Bearer <token>"
```

**响应示例**:
```json
{
  "code": 100000,
  "message": "success",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "fileName": "技术文档.pdf",
    "fileType": "application/pdf",
    "fileSize": 2048576,
    "status": "completed",
    "description": "技术文档",
    "pageCount": 50,
    "chunkCount": 120,
    "imageCount": 15,
    "metadata": {
      "author": "张三",
      "createdDate": "2025-01-01",
      "keywords": ["技术", "文档", "AI"]
    },
    "processingLog": [
      {
        "step": "文档解析",
        "status": "completed",
        "duration": 2.5,
        "timestamp": "2025-02-13T10:00:30Z"
      },
      {
        "step": "文本分块",
        "status": "completed",
        "duration": 1.2,
        "timestamp": "2025-02-13T10:00:32Z"
      },
      {
        "step": "向量化",
        "status": "completed",
        "duration": 5.8,
        "timestamp": "2025-02-13T10:00:38Z"
      }
    ],
    "createdAt": "2025-02-13T10:00:00Z",
    "updatedAt": "2025-02-13T10:05:00Z"
  },
  "timestamp": "2025-02-13T10:00:00Z"
}
```

---

### 4. 删除文档

删除指定文档及其相关数据。

**接口地址**: `DELETE /api/v1/documents/{id}`

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 文档ID（UUID）|

**请求示例**:
```bash
curl -X DELETE http://localhost:8000/api/v1/documents/550e8400-e29b-41d4-a716-446655440001 \
  -H "Authorization: Bearer <token>"
```

**响应示例**:
```json
{
  "code": 100000,
  "message": "删除成功",
  "data": null,
  "timestamp": "2025-02-13T10:00:00Z"
}
```

**状态码**:
- 204: 删除成功
- 404: 文档不存在
- 403: 无权限删除

---

### 5. 获取文档处理状态

查询文档处理进度和状态。

**接口地址**: `GET /api/v1/documents/{id}/status`

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 文档ID（UUID）|

**请求示例**:
```bash
curl -X GET http://localhost:8000/api/v1/documents/550e8400-e29b-41d4-a716-446655440001/status \
  -H "Authorization: Bearer <token>"
```

**响应示例**:
```json
{
  "code": 100000,
  "message": "success",
  "data": {
    "documentId": "550e8400-e29b-41d4-a716-446655440001",
    "status": "processing",
    "progress": 65,
    "currentStep": "向量化",
    "estimatedTimeRemaining": 30,
    "message": "正在生成文本向量..."
  },
  "timestamp": "2025-02-13T10:00:00Z"
}
```

**状态说明**:
- `processing`: 处理中
- `completed`: 处理完成
- `failed`: 处理失败

---

## 查询问答接口

### 1. 执行问答

基于上传的文档进行智能问答。

**接口地址**: `POST /api/v1/query`

**请求头**:
```http
Content-Type: application/json
Authorization: Bearer <token>
```

**请求参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| question | string | 是 | - | 用户问题（1-500字符）|
| topK | integer | 否 | 5 | 检索返回数量（1-20）|
| enableThinking | boolean | 否 | true | 是否启用推理链 |
| documentIds | array | 否 | [] | 指定文档ID列表（空则搜索全部）|
| temperature | float | 否 | 0.7 | 生成温度（0-1）|

**请求示例**:
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "question": "这份文档的主要内容是什么？",
    "topK": 5,
    "enableThinking": true,
    "documentIds": ["550e8400-e29b-41d4-a716-446655440001"]
  }'
```

**响应示例**:
```json
{
  "code": 100000,
  "message": "success",
  "data": {
    "answer": "根据文档内容，该系统是一个多模态文档智能问答系统，主要功能包括：\n\n1. **文档处理**：支持PDF、DOCX等格式的文档上传和解析\n2. **向量检索**：使用ChromaDB和Milvus进行文本和图像的向量存储\n3. **智能问答**：基于Qwen3-VL模型进行多模态理解和回答\n4. **推理可视化**：展示AI的思考过程\n\n系统采用FastAPI后端和React前端，支持本地化部署。",
    "thinking": [
      {
        "step": "问题分析",
        "content": "用户询问系统的主要功能，需要从文档中提取核心功能点"
      },
      {
        "step": "信息检索",
        "content": "从文档的功能介绍章节检索到4个主要功能模块"
      },
      {
        "step": "证据评估",
        "content": "检索结果相关性高，置信度0.92，来源可靠"
      },
      {
        "step": "推理过程",
        "content": "基于检索到的文本和架构图，归纳总结系统的核心功能"
      },
      {
        "step": "答案构建",
        "content": "按照功能分类，使用列表形式组织答案，便于阅读"
      }
    ],
    "sources": [
      {
        "fileName": "技术文档.pdf",
        "page": 3,
        "chunkId": "chunk-001",
        "content": "系统采用多模态RAG架构，支持文本和图像的混合检索...",
        "relevanceScore": 0.92
      },
      {
        "fileName": "技术文档.pdf",
        "page": 5,
        "chunkId": "chunk-015",
        "content": "前端使用React 18.3.0，后端使用FastAPI 0.115.0...",
        "relevanceScore": 0.88
      }
    ],
    "processingTime": 2.35,
    "retrievalStats": {
      "vectorResults": 10,
      "bm25Results": 8,
      "imageResults": 3,
      "fusedResults": 5
    }
  },
  "timestamp": "2025-02-13T10:00:00Z"
}
```

**状态码**:
- 200: 查询成功
- 400: 参数错误
- 404: 指定文档不存在
- 500: 服务器错误

---

### 2. 流式问答

使用Server-Sent Events (SSE)流式返回问答结果。

**接口地址**: `POST /api/v1/query/stream`

**请求参数**: 同"执行问答"接口

**请求示例**:
```javascript
const eventSource = new EventSource(
  'http://localhost:8000/api/v1/query/stream',
  {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer <token>'
    },
    body: JSON.stringify({
      question: '这份文档的主要内容是什么？',
      topK: 5,
      enableThinking: true
    })
  }
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data);
};
```

**响应格式** (SSE流):
```
data: {"type": "thinking", "step": "问题分析", "content": "用户询问..."}

data: {"type": "thinking", "step": "信息检索", "content": "从文档中..."}

data: {"type": "answer", "content": "根据文档内容..."}

data: {"type": "source", "fileName": "技术文档.pdf", "page": 3}

data: {"type": "done", "processingTime": 2.35}
```

**事件类型**:
- `thinking`: 推理步骤
- `answer`: 答案内容（逐token返回）
- `source`: 参考来源
- `done`: 生成完成

---

### 3. 获取历史记录

获取用户的问答历史记录。

**接口地址**: `GET /api/v1/query/history`

**请求参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | integer | 否 | 1 | 页码 |
| pageSize | integer | 否 | 20 | 每页数量 |
| startDate | string | 否 | - | 开始日期（ISO 8601）|
| endDate | string | 否 | - | 结束日期（ISO 8601）|

**请求示例**:
```bash
curl -X GET "http://localhost:8000/api/v1/query/history?page=1&pageSize=20" \
  -H "Authorization: Bearer <token>"
```

**响应示例**:
```json
{
  "code": 100000,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "query-001",
        "question": "这份文档的主要内容是什么？",
        "answer": "根据文档内容，该系统是...",
        "documentIds": ["550e8400-e29b-41d4-a716-446655440001"],
        "processingTime": 2.35,
        "createdAt": "2025-02-13T10:00:00Z"
      }
    ],
    "total": 50,
    "page": 1,
    "pageSize": 20,
    "totalPages": 3
  },
  "timestamp": "2025-02-13T10:00:00Z"
}
```

---

## 系统管理接口

### 1. 健康检查

检查服务运行状态。

**接口地址**: `GET /api/v1/health`

**请求示例**:
```bash
curl -X GET http://localhost:8000/api/v1/health
```

**响应示例**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-02-13T10:00:00Z",
  "services": {
    "ollama": "healthy",
    "chromadb": "healthy",
    "milvus": "healthy",
    "redis": "healthy",
    "postgres": "healthy"
  }
}
```

---

### 2. 获取统计信息

获取系统统计数据。

**接口地址**: `GET /api/v1/stats`

**请求示例**:
```bash
curl -X GET http://localhost:8000/api/v1/stats \
  -H "Authorization: Bearer <token>"
```

**响应示例**:
```json
{
  "code": 100000,
  "message": "success",
  "data": {
    "totalDocuments": 125,
    "totalQueries": 1580,
    "totalChunks": 15000,
    "totalImages": 850,
    "avgProcessingTime": 2.5,
    "avgQueryTime": 1.8,
    "storageUsed": "2.5GB",
    "uptime": 86400
  },
  "timestamp": "2025-02-13T10:00:00Z"
}
```

---

## 错误码说明

### 业务错误码

| 错误码 | 说明 | HTTP状态码 |
|--------|------|-----------|
| 100000 | 成功 | 200 |
| 101001 | 请求参数错误 | 400 |
| 101002 | 未授权，请先登录 | 401 |
| 101003 | 无权限执行此操作 | 403 |
| 101004 | 请求的资源不存在 | 404 |
| 102001 | 服务器内部错误 | 500 |
| 102002 | 服务暂时不可用 | 503 |
| 201001 | 文档不存在 | 404 |
| 201002 | 文档上传失败 | 500 |
| 201003 | 文档处理失败 | 500 |
| 201004 | 不支持的文件类型 | 400 |
| 201005 | 文件大小超过限制 | 413 |
| 301001 | 查询失败 | 500 |
| 301002 | 无效的查询 | 400 |
| 301003 | 未找到相关结果 | 404 |
| 301004 | 检索失败 | 500 |

### 错误响应格式

```json
{
  "code": 201004,
  "message": "不支持的文件类型",
  "errors": [
    {
      "field": "file",
      "message": "仅支持 PDF、DOCX、TXT、MD、CSV、TSV、JSON、JSONL、HTML、XML、YAML、LOG、INI 格式"
    }
  ],
  "timestamp": "2025-02-13T10:00:00Z"
}
```

---

## 数据模型

### Document（文档）

```typescript
interface Document {
  id: string;                    // 文档ID（UUID）
  fileName: string;              // 文件名
  fileType: string;              // 文件类型（MIME）
  fileSize: number;              // 文件大小（字节）
  status: DocumentStatus;        // 处理状态
  description?: string;          // 文档描述
  pageCount?: number;            // 页数
  chunkCount?: number;           // 分块数量
  imageCount?: number;           // 图像数量
  metadata?: object;             // 元数据
  createdAt: string;             // 创建时间（ISO 8601）
  updatedAt: string;             // 更新时间（ISO 8601）
}

enum DocumentStatus {
  PROCESSING = 'processing',     // 处理中
  COMPLETED = 'completed',       // 已完成
  FAILED = 'failed'              // 失败
}
```

### QueryRequest（查询请求）

```typescript
interface QueryRequest {
  question: string;              // 用户问题（1-500字符）
  topK?: number;                 // 检索数量（1-20，默认5）
  enableThinking?: boolean;      // 启用推理链（默认true）
  documentIds?: string[];        // 指定文档ID列表
  temperature?: number;          // 生成温度（0-1，默认0.7）
}
```

### QueryResponse（查询响应）

```typescript
interface QueryResponse {
  answer: string;                // 回答内容
  thinking?: ThinkingStep[];     // 推理链
  sources: Source[];             // 参考来源
  processingTime: number;        // 处理时间（秒）
  retrievalStats?: object;       // 检索统计
}

interface ThinkingStep {
  step: string;                  // 步骤名称
  content: string;               // 步骤内容
}

interface Source {
  fileName: string;              // 文件名
  page: number;                  // 页码
  chunkId?: string;              // 分块ID
  content?: string;              // 内容片段
  relevanceScore?: number;       // 相关性分数
}
```

---

## 附录

### 调用示例（Python）

```python
import requests

# 配置
BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your_jwt_token"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# 上传文档
with open("document.pdf", "rb") as f:
    files = {"file": f}
    response = requests.post(
        f"{BASE_URL}/documents/upload",
        files=files,
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    document_id = response.json()["data"]["documentId"]

# 执行问答
query_data = {
    "question": "这份文档的主要内容是什么？",
    "topK": 5,
    "enableThinking": True,
    "documentIds": [document_id]
}

response = requests.post(
    f"{BASE_URL}/query",
    json=query_data,
    headers=headers
)

result = response.json()
print(result["data"]["answer"])
```

### 调用示例（JavaScript）

```javascript
const BASE_URL = 'http://localhost:8000/api/v1';
const TOKEN = 'your_jwt_token';

// 执行问答
async function query(question) {
  const response = await fetch(`${BASE_URL}/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${TOKEN}`
    },
    body: JSON.stringify({
      question: question,
      topK: 5,
      enableThinking: true
    })
  });
  
  const result = await response.json();
  return result.data;
}

// 使用
query('这份文档的主要内容是什么？')
  .then(data => console.log(data.answer));
```

---

**文档维护**: 技术团队  
**最后更新**: 2026-02-13  
**版本**: v1.0 - 基础功能版本

