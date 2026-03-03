# Phase 3 API 测试指南

## 📋 测试准备

### 1. 启动服务

```powershell
# 激活环境
conda activate multimodal-docqa

# 启动 Redis
docker run -d --name redis-cache -p 6379:6379 redis:7-alpine

# 启动应用
cd backend
python -m uvicorn app.main:app --reload
```

### 2. 获取访问令牌

首先需要登录获取管理员令牌（缓存管理接口需要管理员权限）：

```bash
# 登录
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

保存返回的 `access_token`，后续请求需要使用。

---

## 🧪 API 测试用例

### 测试 1: 获取缓存统计信息

**请求：**
```bash
curl -X GET "http://localhost:8000/api/v1/cache/stats" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**预期响应：**
```json
{
  "code": 200,
  "message": "获取缓存统计成功",
  "data": {
    "status": "connected",
    "memory": {
      "used": "1.2M",
      "peak": "2.5M"
    },
    "performance": {
      "hit_rate": 0.0,
      "hits": 0,
      "misses": 0,
      "total_requests": 0
    },
    "connections": {
      "clients": 1
    },
    "uptime": {
      "seconds": 120,
      "human": "2分钟"
    },
    "commands": {
      "total_processed": 50
    },
    "timestamp": "2026-02-15T10:30:00"
  }
}
```

**验证点：**
- ✅ 状态码 200
- ✅ status 为 "connected"
- ✅ 包含内存、性能、连接等信息

---

### 测试 2: 获取热点键

**请求：**
```bash
curl -X GET "http://localhost:8000/api/v1/cache/hot-keys?limit=10" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**预期响应：**
```json
{
  "code": 200,
  "message": "获取热点键成功",
  "data": {
    "hot_keys": [
      {
        "key": "query:a1b2c3d4...",
        "ttl": 1500,
        "pattern": "query:"
      },
      {
        "key": "document:e5f6g7h8...",
        "ttl": 3200,
        "pattern": "document:"
      }
    ],
    "count": 2
  }
}
```

**验证点：**
- ✅ 状态码 200
- ✅ 返回热点键列表
- ✅ 每个键包含 key、ttl、pattern

---

### 测试 3: 清除指定类型缓存

**请求：**
```bash
# 清除查询缓存
curl -X DELETE "http://localhost:8000/api/v1/cache/clear?cache_type=query" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**预期响应：**
```json
{
  "code": 200,
  "message": "成功清除 query 缓存，共 5 个键",
  "data": {
    "success": true,
    "type": "query",
    "deleted_count": 5,
    "message": "成功清除 query 缓存，共 5 个键",
    "timestamp": "2026-02-15T10:35:00"
  }
}
```

**验证点：**
- ✅ 状态码 200
- ✅ success 为 true
- ✅ deleted_count >= 0

---

### 测试 4: 清除所有缓存

**请求：**
```bash
curl -X DELETE "http://localhost:8000/api/v1/cache/clear?cache_type=all" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**预期响应：**
```json
{
  "code": 200,
  "message": "成功清除所有缓存，共 15 个键",
  "data": {
    "success": true,
    "type": "all",
    "deleted_count": 15,
    "message": "成功清除所有缓存，共 15 个键",
    "timestamp": "2026-02-15T10:40:00"
  }
}
```

**验证点：**
- ✅ 状态码 200
- ✅ 清除所有类型的缓存

---

### 测试 5: 缓存预热

**请求：**
```bash
curl -X POST "http://localhost:8000/api/v1/cache/warmup" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**预期响应：**
```json
{
  "code": 200,
  "message": "缓存预热完成，共 3 项",
  "data": {
    "success": true,
    "warmed_count": 3,
    "details": [
      "配置缓存: 3 项"
    ],
    "message": "缓存预热完成，共 3 项",
    "timestamp": "2026-02-15T10:45:00"
  }
}
```

**验证点：**
- ✅ 状态码 200
- ✅ success 为 true
- ✅ warmed_count > 0

---

### 测试 6: 获取缓存键数量

**请求：**
```bash
curl -X GET "http://localhost:8000/api/v1/cache/keys-count" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**预期响应：**
```json
{
  "code": 200,
  "message": "获取缓存键数量成功",
  "data": {
    "query": 5,
    "document": 3,
    "conversation": 2,
    "user": 1,
    "total": 11
  }
}
```

**验证点：**
- ✅ 状态码 200
- ✅ 包含各类型键数量
- ✅ total 等于各类型之和

---

### 测试 7: 获取缓存详情

**请求：**
```bash
curl -X GET "http://localhost:8000/api/v1/cache/detail/query:test123" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**预期响应（键存在）：**
```json
{
  "code": 200,
  "message": "获取缓存详情成功",
  "data": {
    "key": "query:test123",
    "value": {
      "question": "测试问题",
      "answer": "测试答案"
    },
    "ttl": 1500,
    "expires_at": "2026-02-15T11:00:00",
    "timestamp": "2026-02-15T10:45:00"
  }
}
```

**预期响应（键不存在）：**
```json
{
  "code": 404,
  "message": "缓存键不存在",
  "data": null
}
```

**验证点：**
- ✅ 键存在时返回详细信息
- ✅ 键不存在时返回 404

---

## 🔐 权限测试

### 测试 8: 非管理员访问（应失败）

**请求：**
```bash
# 使用普通用户登录
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user",
    "password": "user123"
  }'

# 使用普通用户token访问缓存接口
curl -X GET "http://localhost:8000/api/v1/cache/stats" \
  -H "Authorization: Bearer USER_ACCESS_TOKEN"
```

**预期响应：**
```json
{
  "detail": "需要管理员权限"
}
```

**验证点：**
- ✅ 状态码 403
- ✅ 返回权限错误信息

---

### 测试 9: 未登录访问（应失败）

**请求：**
```bash
curl -X GET "http://localhost:8000/api/v1/cache/stats"
```

**预期响应：**
```json
{
  "detail": "Not authenticated"
}
```

**验证点：**
- ✅ 状态码 401
- ✅ 返回未认证错误

---

## 🎯 集成测试场景

### 场景 1: 缓存生命周期测试

**步骤：**

1. **清除所有缓存**
```bash
curl -X DELETE "http://localhost:8000/api/v1/cache/clear?cache_type=all" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

2. **执行查询（生成缓存）**
```bash
curl -X POST "http://localhost:8000/api/v1/conversations/CONV_ID/messages" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "测试问题",
    "document_ids": ["DOC_ID"]
  }'
```

3. **检查缓存统计**
```bash
curl -X GET "http://localhost:8000/api/v1/cache/stats" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

4. **验证缓存键数量增加**
```bash
curl -X GET "http://localhost:8000/api/v1/cache/keys-count" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**预期结果：**
- ✅ 缓存键数量增加
- ✅ 命中率初始为 0
- ✅ 第二次相同查询命中率提升

---

### 场景 2: 缓存性能测试

**步骤：**

1. **第一次查询（无缓存）**
```bash
time curl -X POST "http://localhost:8000/api/v1/conversations/CONV_ID/messages" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "什么是人工智能？",
    "document_ids": ["DOC_ID"]
  }'
```

2. **第二次相同查询（有缓存）**
```bash
time curl -X POST "http://localhost:8000/api/v1/conversations/CONV_ID/messages" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "什么是人工智能？",
    "document_ids": ["DOC_ID"]
  }'
```

3. **对比响应时间**

**预期结果：**
- ✅ 第二次查询明显更快（50-70% 提升）
- ✅ 缓存命中率提升

---

### 场景 3: 缓存清理测试

**步骤：**

1. **生成多种类型缓存**
   - 执行查询（生成 query 缓存）
   - 获取文档信息（生成 document 缓存）
   - 获取用户信息（生成 user 缓存）

2. **检查键数量**
```bash
curl -X GET "http://localhost:8000/api/v1/cache/keys-count" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

3. **清除特定类型**
```bash
curl -X DELETE "http://localhost:8000/api/v1/cache/clear?cache_type=query" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

4. **再次检查键数量**
```bash
curl -X GET "http://localhost:8000/api/v1/cache/keys-count" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**预期结果：**
- ✅ query 类型键数量变为 0
- ✅ 其他类型键数量不变

---

## 📊 性能基准

### 预期性能指标

| 操作 | 无缓存 | 有缓存 | 提升 |
|------|--------|--------|------|
| 查询问答 | 2-3秒 | 0.5-1秒 | 60-70% |
| 文档检索 | 1-2秒 | 0.2-0.5秒 | 70-80% |
| 用户信息 | 0.5秒 | 0.05秒 | 90% |

### 缓存命中率目标

- **初始阶段**: 20-40%
- **稳定运行**: 60-80%
- **优化后**: > 80%

---

## 🐛 常见问题

### 问题 1: Redis 未连接

**现象：**
```json
{
  "status": "disconnected",
  "message": "Redis未连接"
}
```

**解决：**
```bash
# 启动 Redis
docker start redis-cache

# 或重新创建
docker run -d --name redis-cache -p 6379:6379 redis:7-alpine
```

### 问题 2: 权限被拒绝

**现象：**
```json
{
  "detail": "需要管理员权限"
}
```

**解决：**
- 确认使用管理员账号登录
- 检查 token 是否正确
- 验证用户角色是否为 admin

### 问题 3: 缓存未生效

**现象：**
- 命中率始终为 0
- 响应时间没有改善

**排查：**
1. 检查 `CACHE_ENABLED=true`
2. 验证 Redis 连接状态
3. 查看应用日志中的缓存信息
4. 确认查询参数完全相同

---

## 📝 测试检查清单

### 功能测试
- [ ] 获取缓存统计
- [ ] 获取热点键
- [ ] 清除指定类型缓存
- [ ] 清除所有缓存
- [ ] 缓存预热
- [ ] 获取缓存键数量
- [ ] 获取缓存详情

### 权限测试
- [ ] 管理员可以访问所有接口
- [ ] 普通用户被拒绝访问
- [ ] 未登录用户被拒绝访问

### 性能测试
- [ ] 缓存命中时响应更快
- [ ] 缓存命中率符合预期
- [ ] 内存使用在合理范围

### 集成测试
- [ ] 缓存生命周期正常
- [ ] 缓存清理功能正常
- [ ] 多类型缓存互不影响

---

**文档维护**: 后端团队  
**最后更新**: 2026-02-15  
**版本**: Phase 3 API 测试指南

