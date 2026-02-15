# 多模态文档智能问答系统 - 技术架构文档

## 系统概述

本系统是一个基于 FastAPI + Ollama + ChromaDB 的本地化文档智能问答系统，支持多轮对话、RAG 检索增强生成、用户认证等功能。

## 整体架构

```mermaid
graph TB
    subgraph "前端层"
        FE[React 前端应用]
    end
    
    subgraph "API 网关层"
        GW[FastAPI 应用]
        MW1[CORS 中间件]
        MW2[认证中间件]
        MW3[限流中间件]
        
        GW --> MW1
        GW --> MW2
        GW --> MW3
    end
    
    subgraph "路由层"
        R1[Health Router<br/>健康检查]
        R2[Auth Router<br/>用户认证]
        R3[Conversations Router<br/>对话管理]
        R4[Documents Router<br/>文档管理]
    end
    
    subgraph "服务层"
        S1[AuthService<br/>认证服务]
        S2[ConversationService<br/>对话服务]
        S3[RetrievalService<br/>检索服务]
        S4[LLMService<br/>大模型服务]
        S5[EmbeddingService<br/>向量化服务]
        S6[ExportService<br/>导出服务]
        S7[ContextManager<br/>上下文管理]
    end
    
    subgraph "数据层"
        DB1[(PostgreSQL<br/>关系数据库)]
        DB2[(ChromaDB<br/>向量数据库)]
        DB3[(Redis<br/>缓存)]
        API1[Ollama API<br/>本地大模型]
    end
    
    FE --> GW
    
    GW --> R1
    GW --> R2
    GW --> R3
    GW --> R4
    
    R2 --> S1
    R3 --> S2
    R3 --> S3
    R3 --> S4
    R3 --> S6
    R4 --> S5
    
    S1 --> DB1
    S1 --> DB3
    S2 --> DB1
    S3 --> DB2
    S4 --> API1
    S5 --> API1
    S7 --> S2
    
    style R3 fill:#4CAF50,stroke:#2E7D32,stroke-width:3px
    style S2 fill:#4CAF50,stroke:#2E7D32,stroke-width:2px
    style S3 fill:#4CAF50,stroke:#2E7D32,stroke-width:2px
    style S4 fill:#4CAF50,stroke:#2E7D32,stroke-width:2px
```

## 核心流程

### 1. 用户认证流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant API as Auth API
    participant AS as AuthService
    participant DB as PostgreSQL
    participant RD as Redis
    
    U->>API: POST /auth/register
    API->>AS: 注册用户
    AS->>DB: 创建用户记录
    DB-->>AS: 返回用户信息
    AS-->>API: 注册成功
    API-->>U: 返回用户信息
    
    U->>API: POST /auth/login
    API->>AS: 验证用户
    AS->>DB: 查询用户
    DB-->>AS: 返回用户信息
    AS->>AS: 验证密码
    AS->>AS: 生成 JWT Token
    AS->>DB: 保存 Refresh Token
    AS->>RD: 缓存会话信息
    AS-->>API: 返回 Token
    API-->>U: 返回 access_token + refresh_token
```

### 2. 对话消息流程（RAG）

```mermaid
sequenceDiagram
    participant U as 用户
    participant API as Conversations API
    participant CS as ConversationService
    participant RS as RetrievalService
    participant LS as LLMService
    participant DB as PostgreSQL
    participant VDB as ChromaDB
    participant OL as Ollama
    
    U->>API: POST /conversations/{id}/messages
    Note over U,API: {"content": "问题", "top_k": 5}
    
    API->>CS: 保存用户消息
    CS->>DB: INSERT message (role=user)
    DB-->>CS: 消息已保存
    
    API->>CS: 获取对话信息
    CS->>DB: SELECT conversation
    DB-->>CS: 返回对话（含 document_ids）
    
    API->>RS: 检索相关文档
    Note over RS: hybrid_search(query, document_ids)
    RS->>VDB: 向量相似度检索
    VDB-->>RS: 返回 top_k 相关片段
    
    alt 有检索结果
        API->>LS: 生成基于文档的回答
        Note over LS: generate_answer(query, context)
        LS->>OL: POST /generate (带上下文)
        OL-->>LS: 返回生成内容 + thinking
    else 无检索结果
        API->>LS: 生成通用回答
        Note over LS: generate_general_answer(query)
        LS->>OL: POST /generate (无上下文)
        OL-->>LS: 返回生成内容
    end
    
    LS-->>API: 返回答案 + thinking + sources
    
    API->>CS: 保存 AI 回复
    CS->>DB: INSERT message (role=assistant)
    DB-->>CS: 消息已保存
    
    API-->>U: 返回完整回复
    Note over U,API: {answer, thinking, sources}
```

### 3. 流式消息流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant API as Conversations API
    participant CS as ConversationService
    participant RS as RetrievalService
    participant LS as LLMService
    participant OL as Ollama
    
    U->>API: POST /conversations/{id}/messages/stream
    
    API->>CS: 保存用户消息
    API->>CS: 获取对话信息
    API->>RS: 检索相关文档
    
    API-->>U: SSE: {"type": "status", "content": "检索到5条"}
    
    alt enable_thinking=true
        API->>LS: 生成答案（非流式）
        LS->>OL: POST /generate
        OL-->>LS: 返回完整答案 + thinking
        
        loop 每个思考步骤
            API-->>U: SSE: {"type": "thinking", "step": "...", "content": "..."}
        end
        
        API-->>U: SSE: {"type": "answer", "content": "完整答案"}
    else enable_thinking=false
        API->>LS: 生成答案（流式）
        LS->>OL: POST /generate (stream=true)
        
        loop 每个 token
            OL-->>LS: 返回 token
            LS-->>API: 返回 token
            API-->>U: SSE: {"type": "answer", "content": "token"}
        end
    end
    
    loop 每个引用来源
        API-->>U: SSE: {"type": "source", "fileName": "...", "page": 1}
    end
    
    API->>CS: 保存 AI 回复
    API-->>U: SSE: {"type": "done"}
```

### 4. 文档上传与向量化流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant API as Documents API
    participant ES as EmbeddingService
    participant VDB as ChromaDB
    participant OL as Ollama
    
    U->>API: POST /documents/upload
    Note over U,API: 上传 PDF/DOCX 文件
    
    API->>API: 解析文档内容
    Note over API: 提取文本、图片、表格
    
    API->>API: 文档分块
    Note over API: chunk_size=500, overlap=50
    
    loop 每个文本块
        API->>ES: 生成向量
        ES->>OL: POST /embeddings
        OL-->>ES: 返回 1024 维向量
        ES-->>API: 返回向量
        
        API->>VDB: 存储向量
        Note over VDB: 保存 (id, vector, metadata)
    end
    
    API->>API: 保存文档元数据
    API-->>U: 返回文档 ID
```

## 数据模型

### 数据库表结构

```mermaid
erDiagram
    users ||--o{ conversations : "创建"
    users ||--o{ refresh_tokens : "拥有"
    conversations ||--o{ messages : "包含"
    
    users {
        uuid id PK
        string username UK
        string email UK
        string password_hash
        enum role
        string avatar
        boolean is_active
        timestamp created_at
        timestamp last_login_at
    }
    
    refresh_tokens {
        uuid id PK
        uuid user_id FK
        string token UK
        string jti UK
        timestamp expires_at
        timestamp created_at
        timestamp last_used_at
        string device_info
        string ip_address
        boolean is_revoked
    }
    
    conversations {
        uuid id PK
        uuid user_id FK
        string title
        text[] document_ids
        int message_count
        text last_message
        jsonb extra_data
        timestamp created_at
        timestamp updated_at
    }
    
    messages {
        uuid id PK
        uuid conversation_id FK
        string role
        text content
        jsonb thinking
        jsonb sources
        jsonb extra_data
        timestamp created_at
    }
```

### ChromaDB 集合结构

```python
{
    "collection_name": "documents",
    "dimension": 1024,
    "documents": [
        {
            "id": "chunk-uuid",
            "embedding": [0.1, 0.2, ...],  # 1024维向量
            "metadata": {
                "document_id": "doc-uuid",
                "page": 1,
                "chunk_index": 0,
                "content": "文档内容片段..."
            }
        }
    ]
}
```

## 技术栈

### 后端技术

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 编程语言 |
| FastAPI | 0.104+ | Web 框架 |
| SQLAlchemy | 2.0+ | ORM |
| Pydantic | 2.0+ | 数据验证 |
| PostgreSQL | 14+ | 关系数据库 |
| ChromaDB | 0.4+ | 向量数据库 |
| Redis | 7+ | 缓存 |
| Ollama | - | 本地大模型 |

### 核心依赖

```txt
fastapi==0.104.1
uvicorn==0.24.0
sqlalchemy==2.0.23
asyncpg==0.29.0
pydantic==2.5.0
pydantic-settings==2.1.0
chromadb==0.4.18
redis==5.0.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt==4.1.2
python-multipart==0.0.6
slowapi==0.1.9
loguru==0.7.2
requests==2.31.0
aiohttp==3.9.1
```

## 部署架构

### 开发环境

```mermaid
graph LR
    subgraph "本地开发环境"
        DEV[开发机器]
        
        subgraph "服务"
            PG[(PostgreSQL)]
            RD[(Redis)]
            CH[(ChromaDB)]
            OL[Ollama]
        end
        
        DEV --> PG
        DEV --> RD
        DEV --> CH
        DEV --> OL
    end
```

### 生产环境（建议）

```mermaid
graph TB
    subgraph "负载均衡层"
        LB[Nginx / Traefik]
    end
    
    subgraph "应用层"
        APP1[FastAPI 实例 1]
        APP2[FastAPI 实例 2]
        APP3[FastAPI 实例 N]
    end
    
    subgraph "数据层"
        PG[(PostgreSQL<br/>主从复制)]
        RD[(Redis<br/>集群)]
        CH[(ChromaDB<br/>持久化)]
        OL[Ollama<br/>GPU 加速]
    end
    
    LB --> APP1
    LB --> APP2
    LB --> APP3
    
    APP1 --> PG
    APP1 --> RD
    APP1 --> CH
    APP1 --> OL
    
    APP2 --> PG
    APP2 --> RD
    APP2 --> CH
    APP2 --> OL
    
    APP3 --> PG
    APP3 --> RD
    APP3 --> CH
    APP3 --> OL
```

## 性能优化

### 1. 数据库优化

- 使用连接池（asyncpg）
- 添加索引（user_id, conversation_id, created_at）
- 定期清理过期数据

### 2. 缓存策略

- Redis 缓存用户会话
- Redis 缓存热门查询结果
- Token 黑名单使用 Redis TTL

### 3. 向量检索优化

- ChromaDB 使用 HNSW 索引
- 限制检索数量（top_k <= 20）
- 批量向量化处理

### 4. LLM 调用优化

- 使用流式响应减少等待时间
- 控制上下文长度
- 合理设置 temperature 参数

## 安全措施

### 1. 认证与授权

- JWT Token 认证
- Refresh Token 数据库存储
- Token 黑名单机制
- 会话管理（多设备登录）

### 2. 接口安全

- CORS 配置
- 请求限流（SlowAPI）
- 输入验证（Pydantic）
- SQL 注入防护（SQLAlchemy ORM）

### 3. 数据安全

- 密码哈希（bcrypt）
- 敏感信息加密
- 数据库连接加密
- 定期备份

## 监控与日志

### 1. 日志系统

```python
# 使用 loguru
logger.info("用户登录成功: {username}", username=user.username)
logger.error("查询失败: {error}", error=str(e))
```

### 2. 监控指标

- API 响应时间
- 数据库查询性能
- 向量检索耗时
- LLM 生成耗时
- 错误率统计

### 3. 健康检查

```
GET /api/v1/health
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "chromadb": "connected",
  "ollama": "connected"
}
```

## 扩展性设计

### 1. 水平扩展

- 无状态 API 设计
- 支持多实例部署
- 负载均衡

### 2. 功能扩展

- 插件化架构
- 支持多种向量数据库
- 支持多种 LLM 后端
- 支持多种文档格式

### 3. 性能扩展

- 异步处理
- 批量操作
- 缓存优化

## 开发规范

### 1. 代码结构

```
backend/
├── app/
│   ├── api/          # API 路由
│   ├── models/       # 数据模型
│   ├── schemas/      # Pydantic 模型
│   ├── services/     # 业务逻辑
│   ├── utils/        # 工具函数
│   └── main.py       # 应用入口
├── scripts/          # 脚本工具
├── tests/            # 测试代码
└── docs/             # 文档
```

### 2. 命名规范

- 文件名：小写下划线（snake_case）
- 类名：大驼峰（PascalCase）
- 函数名：小写下划线（snake_case）
- 常量：大写下划线（UPPER_CASE）

### 3. 注释规范

```python
def function_name(param1: str, param2: int) -> dict:
    """
    函数简短描述
    
    Args:
        param1: 参数1说明
        param2: 参数2说明
        
    Returns:
        返回值说明
        
    Raises:
        异常说明
    """
    pass
```

## 测试策略

### 1. 单元测试

- 测试服务层逻辑
- 测试工具函数
- 覆盖率 > 80%

### 2. 集成测试

- 测试 API 接口
- 测试数据库操作
- 测试外部服务调用

### 3. 性能测试

- 压力测试
- 并发测试
- 响应时间测试

## 版本历史

### Phase 1 (v1.0.0)
- ✅ 基础 RAG 功能
- ✅ 文档上传与处理
- ✅ 单次问答接口
- ✅ 用户认证

### Phase 2 (v2.0.0)
- ✅ 对话管理功能
- ✅ 整合 RAG 到对话
- ✅ 流式响应
- ✅ 对话导出
- ✅ 废弃 query 接口

### 未来计划
- ⏳ WebSocket 实时推送
- ⏳ 对话分享功能
- ⏳ 全文搜索
- ⏳ 多模态支持（图片、语音）
- ⏳ 知识图谱

## 参考资料

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
- [ChromaDB 文档](https://docs.trychroma.com/)
- [Ollama 文档](https://ollama.ai/docs)

---

**文档维护**: 后端团队  
**最后更新**: 2026-02-14

