# Phase 2 API测试指南

## 测试环境准备

### 1. 启动服务
```bash
python -m app.main
```

### 2. 获取访问令牌

首先需要注册并登录获取Token：

```bash
# 注册用户
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "Test123456"
  }'

# 登录获取Token
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "Test123456"
  }'
```

保存返回的`access_token`，后续请求都需要使用。

---

## API测试用例

### 测试1: 创建对话会话

**请求**:
```bash
curl -X POST "http://localhost:8000/api/v1/conversations" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "技术讨论",
    "document_ids": ["doc-123", "doc-456"]
  }'
```

**预期响应** (201 Created):
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "title": "技术讨论",
  "document_ids": ["doc-123", "doc-456"],
  "message_count": 0,
  "last_message": null,
  "created_at": "2026-02-14T10:00:00",
  "updated_at": "2026-02-14T10:00:00"
}
```

**验证点**:
- ✅ 返回状态码为201
- ✅ 返回的对话包含正确的标题
- ✅ document_ids正确保存
- ✅ message_count初始为0

---

### 测试2: 获取对话列表

**请求**:
```bash
curl -X GET "http://localhost:8000/api/v1/conversations?skip=0&limit=10" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**预期响应** (200 OK):
```json
{
  "total": 1,
  "conversations": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "title": "技术讨论",
      "document_ids": ["doc-123", "doc-456"],
      "message_count": 0,
      "last_message": null,
      "created_at": "2026-02-14T10:00:00",
      "updated_at": "2026-02-14T10:00:00"
    }
  ]
}
```

**验证点**:
- ✅ 返回状态码为200
- ✅ total字段正确
- ✅ 对话按更新时间倒序排列
- ✅ 只返回当前用户的对话

---

### 测试3: 发送消息

**请求**:
```bash
curl -X POST "http://localhost:8000/api/v1/conversations/{conversation_id}/messages" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "你好，请介绍一下自己"
  }'
```

**预期响应** (201 Created):
```json
{
  "id": "uuid",
  "conversation_id": "uuid",
  "role": "assistant",
  "content": "收到您的消息：你好，请介绍一下自己\n\n这是一个示例回复...",
  "thinking": {
    "note": "这是思考过程的示例"
  },
  "sources": [],
  "created_at": "2026-02-14T10:01:00"
}
```

**验证点**:
- ✅ 返回状态码为201
- ✅ 返回的是assistant角色的消息
- ✅ 包含thinking字段
- ✅ 对话的message_count增加

---

### 测试4: 获取对话详情

**请求**:
```bash
curl -X GET "http://localhost:8000/api/v1/conversations/{conversation_id}" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**预期响应** (200 OK):
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "title": "技术讨论",
  "document_ids": ["doc-123", "doc-456"],
  "message_count": 2,
  "last_message": "收到您的消息：你好，请介绍一下自己...",
  "created_at": "2026-02-14T10:00:00",
  "updated_at": "2026-02-14T10:01:00",
  "messages": [
    {
      "id": "uuid",
      "conversation_id": "uuid",
      "role": "user",
      "content": "你好，请介绍一下自己",
      "thinking": null,
      "sources": null,
      "created_at": "2026-02-14T10:01:00"
    },
    {
      "id": "uuid",
      "conversation_id": "uuid",
      "role": "assistant",
      "content": "收到您的消息...",
      "thinking": {"note": "这是思考过程的示例"},
      "sources": [],
      "created_at": "2026-02-14T10:01:00"
    }
  ]
}
```

**验证点**:
- ✅ 返回状态码为200
- ✅ 包含完整的消息列表
- ✅ 消息按时间顺序排列
- ✅ message_count正确

---

### 测试5: 更新对话标题

**请求**:
```bash
curl -X PATCH "http://localhost:8000/api/v1/conversations/{conversation_id}/title?title=新标题" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**预期响应** (200 OK):
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "title": "新标题",
  "document_ids": ["doc-123", "doc-456"],
  "message_count": 2,
  "last_message": "收到您的消息...",
  "created_at": "2026-02-14T10:00:00",
  "updated_at": "2026-02-14T10:05:00"
}
```

**验证点**:
- ✅ 返回状态码为200
- ✅ 标题已更新
- ✅ updated_at时间已更新

---

### 测试6: 导出对话（Markdown）

**请求**:
```bash
curl -X GET "http://localhost:8000/api/v1/conversations/{conversation_id}/export?format=markdown&include_thinking=true&include_sources=true" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -o conversation.md
```

**预期响应** (200 OK):
- 返回Markdown格式的文件
- Content-Type: text/markdown
- Content-Disposition: attachment

**验证点**:
- ✅ 文件成功下载
- ✅ 文件格式正确
- ✅ 包含对话标题和元信息
- ✅ 包含所有消息内容
- ✅ 包含思考过程（如果有）
- ✅ 包含引用来源（如果有）

---

### 测试7: 导出对话（JSON）

**请求**:
```bash
curl -X GET "http://localhost:8000/api/v1/conversations/{conversation_id}/export?format=json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -o conversation.json
```

**预期响应** (200 OK):
```json
{
  "conversation": {
    "id": "uuid",
    "title": "新标题",
    "document_ids": ["doc-123", "doc-456"],
    "message_count": 2,
    "created_at": "2026-02-14T10:00:00",
    "updated_at": "2026-02-14T10:05:00"
  },
  "messages": [
    {
      "id": "uuid",
      "role": "user",
      "content": "你好，请介绍一下自己",
      "created_at": "2026-02-14T10:01:00"
    },
    {
      "id": "uuid",
      "role": "assistant",
      "content": "收到您的消息...",
      "thinking": {"note": "这是思考过程的示例"},
      "sources": [],
      "created_at": "2026-02-14T10:01:00"
    }
  ],
  "exported_at": "2026-02-14T10:10:00"
}
```

**验证点**:
- ✅ 文件成功下载
- ✅ JSON格式正确
- ✅ 包含完整的对话和消息数据

---

### 测试8: 删除对话

**请求**:
```bash
curl -X DELETE "http://localhost:8000/api/v1/conversations/{conversation_id}" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**预期响应** (204 No Content):
- 无响应体

**验证点**:
- ✅ 返回状态码为204
- ✅ 对话已从数据库删除
- ✅ 相关消息也被删除（级联删除）
- ✅ 再次查询返回404

---

## 权限测试

### 测试9: 访问其他用户的对话

**场景**: 用户A尝试访问用户B的对话

**请求**:
```bash
curl -X GET "http://localhost:8000/api/v1/conversations/{other_user_conversation_id}" \
  -H "Authorization: Bearer USER_A_TOKEN"
```

**预期响应** (404 Not Found):
```json
{
  "detail": "对话不存在或无权访问"
}
```

**验证点**:
- ✅ 返回状态码为404
- ✅ 无法访问其他用户的对话

---

### 测试10: 未认证访问

**场景**: 不提供Token访问接口

**请求**:
```bash
curl -X GET "http://localhost:8000/api/v1/conversations"
```

**预期响应** (401 Unauthorized):
```json
{
  "detail": "Not authenticated"
}
```

**验证点**:
- ✅ 返回状态码为401
- ✅ 所有对话接口都需要认证

---

## 边界测试

### 测试11: 创建对话（不提供标题）

**请求**:
```bash
curl -X POST "http://localhost:8000/api/v1/conversations" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**预期响应** (201 Created):
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "title": "对话 1",
  "document_ids": [],
  "message_count": 0,
  "last_message": null,
  "created_at": "2026-02-14T10:00:00",
  "updated_at": "2026-02-14T10:00:00"
}
```

**验证点**:
- ✅ 自动生成标题
- ✅ document_ids默认为空数组

---

### 测试12: 发送空消息

**请求**:
```bash
curl -X POST "http://localhost:8000/api/v1/conversations/{conversation_id}/messages" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": ""
  }'
```

**预期响应** (422 Unprocessable Entity):
```json
{
  "detail": [
    {
      "loc": ["body", "content"],
      "msg": "ensure this value has at least 1 characters",
      "type": "value_error.any_str.min_length"
    }
  ]
}
```

**验证点**:
- ✅ 返回状态码为422
- ✅ 拒绝空消息

---

### 测试13: 分页测试

**请求**:
```bash
# 创建多个对话
for i in {1..25}; do
  curl -X POST "http://localhost:8000/api/v1/conversations" \
    -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"title\": \"对话 $i\"}"
done

# 测试分页
curl -X GET "http://localhost:8000/api/v1/conversations?skip=0&limit=10" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

curl -X GET "http://localhost:8000/api/v1/conversations?skip=10&limit=10" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**验证点**:
- ✅ 第一页返回10条记录
- ✅ 第二页返回10条记录
- ✅ total字段正确显示总数
- ✅ 按更新时间倒序排列

---

## 性能测试

### 测试14: 并发创建对话

**工具**: Apache Bench (ab) 或 wrk

```bash
# 使用ab进行并发测试
ab -n 100 -c 10 -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
   -p conversation.json -T application/json \
   http://localhost:8000/api/v1/conversations
```

**验证点**:
- ✅ 所有请求都成功
- ✅ 响应时间在可接受范围内
- ✅ 无数据竞争问题

---

## 自动化测试脚本

### Python测试脚本

```python
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

# 1. 注册并登录
def get_token():
    # 注册
    requests.post(f"{BASE_URL}/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "Test123456"
    })
    
    # 登录
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "testuser",
        "password": "Test123456"
    })
    return response.json()["access_token"]

# 2. 运行测试
def run_tests():
    token = get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 测试1: 创建对话
    print("测试1: 创建对话...")
    response = requests.post(
        f"{BASE_URL}/conversations",
        headers=headers,
        json={"title": "测试对话"}
    )
    assert response.status_code == 201
    conversation_id = response.json()["id"]
    print("✅ 通过")
    
    # 测试2: 发送消息
    print("测试2: 发送消息...")
    response = requests.post(
        f"{BASE_URL}/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "你好"}
    )
    assert response.status_code == 201
    print("✅ 通过")
    
    # 测试3: 获取对话详情
    print("测试3: 获取对话详情...")
    response = requests.get(
        f"{BASE_URL}/conversations/{conversation_id}",
        headers=headers
    )
    assert response.status_code == 200
    assert len(response.json()["messages"]) == 2
    print("✅ 通过")
    
    # 测试4: 导出对话
    print("测试4: 导出对话...")
    response = requests.get(
        f"{BASE_URL}/conversations/{conversation_id}/export",
        headers=headers,
        params={"format": "markdown"}
    )
    assert response.status_code == 200
    print("✅ 通过")
    
    # 测试5: 删除对话
    print("测试5: 删除对话...")
    response = requests.delete(
        f"{BASE_URL}/conversations/{conversation_id}",
        headers=headers
    )
    assert response.status_code == 204
    print("✅ 通过")
    
    print("\n所有测试通过！")

if __name__ == "__main__":
    run_tests()
```

---

## 测试检查清单

### 功能测试
- [ ] 创建对话会话
- [ ] 获取对话列表
- [ ] 获取对话详情
- [ ] 发送消息
- [ ] 更新对话标题
- [ ] 删除对话
- [ ] 导出对话（Markdown）
- [ ] 导出对话（JSON）
- [ ] 导出对话（PDF）

### 权限测试
- [ ] 认证保护
- [ ] 用户隔离
- [ ] Token验证

### 边界测试
- [ ] 空标题处理
- [ ] 空消息拒绝
- [ ] 分页功能
- [ ] 不存在的对话ID

### 性能测试
- [ ] 并发创建对话
- [ ] 大量消息处理
- [ ] 导出大型对话

---

## 常见问题

### Q1: 如何获取conversation_id？
A: 创建对话后，从响应中获取`id`字段，或通过获取对话列表接口查看。

### Q2: 为什么导出PDF失败？
A: 需要安装reportlab库：`pip install reportlab`

### Q3: 如何测试多轮对话？
A: 多次调用发送消息接口，系统会自动管理上下文。

### Q4: Token过期怎么办？
A: 使用refresh token刷新，或重新登录获取新token。

---

**测试完成后，请确保所有功能正常工作！** ✅

