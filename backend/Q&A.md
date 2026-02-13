# 后端问题记录

## 1. Ollama 连接问题修复 (2026-02-13)

### 问题描述
文档上传功能失败，后端无法连接到 Ollama 服务，收到 502 错误。

### 根本原因
**httpx.AsyncClient 在 Windows 上存在兼容性问题**，导致所有 POST 请求返回 502 错误，而 GET 请求正常。

### 测试结果
- ✓ `requests` 库：成功连接 Ollama
- ✗ `httpx.AsyncClient`：所有配置下都返回 502
- ✓ Ollama 服务本身：运行正常

### 解决方案
将 `httpx.AsyncClient` 替换为 `requests` 库，使用 `asyncio.to_thread()` 在异步环境中运行同步请求。

### 修改的文件

#### 1. backend/app/config.py
- 将 `ollama_base_url` 从 `http://localhost:11434/api` 改为 `http://127.0.0.1:11434/api`

#### 2. backend/app/services/embedding_service.py
- 移除 `httpx.AsyncClient`
- 使用 `requests.post()` + `asyncio.to_thread()`
- API 端点：`/api/embed`
- 请求参数：`{"model": "...", "input": "..."}`
- 响应字段：`embeddings` (数组)

#### 3. backend/app/services/llm_service.py
- 移除 `httpx.AsyncClient`
- 使用 `requests.post()` + `asyncio.to_thread()`
- API 端点：`/api/generate`
- 流式生成暂不支持（需要时可使用 aiohttp）

### API 端点参考
- 模型列表：`GET /api/tags`
- 文本向量化：`POST /api/embed`
- 文本生成：`POST /api/generate`

---

## 2. 向量维度不匹配问题修复 (2026-02-13)

### 问题描述
文档上传时报错：`Embedding dimension 1024 does not match collection dimensionality 896`

### 根本原因
ChromaDB 集合在创建时没有明确指定向量维度，第一次插入时自动推断为 896 维，但 `qwen3-embedding:0.6b-fp16` 模型实际生成的是 1024 维向量。

### 解决方案
1. 在初始化脚本中明确指定向量维度为 1024
2. 删除旧的 collection 并重新创建
3. 在 EmbeddingService 中也添加维度检查

### 修改的文件

#### 1. backend/scripts/init_db.py
- 删除旧的 collection（如果存在）
- 创建时明确指定 `dimension: 1024`

#### 2. backend/app/services/embedding_service.py
- 使用 `get_collection()` 和 `create_collection()` 替代 `get_or_create_collection()`
- 创建时明确指定 `dimension: 1024`

### 重新初始化步骤
```bash
python scripts/init_db.py
```

---

## 3. 无文档时查询优化 (2026-02-13)

### 问题描述
当没有上传文档时进行查询，系统耗时 11-12 秒但没有任何回答返回。

### 根本原因
- 检索到 0 条内容时，仍然调用 LLM 生成答案
- 空上下文导致 LLM 无法生成有效回答
- 缺少通用对话模式的支持

### 解决方案
实现智能模式切换：
1. **有文档时**：基于文档内容的 RAG 问答
2. **无文档时**：切换为通用对话模式

### 修改的文件

#### 1. backend/app/api/v1/query.py
- 检测检索结果数量
- 当 `len(retrieval_results) == 0` 时调用 `generate_general_answer()`
- 否则使用原有的 `generate_answer()`

#### 2. backend/app/services/llm_service.py
- 新增 `generate_general_answer()` 方法：通用对话模式
- 优化 `_build_prompt()` 方法：处理空上下文情况
- 添加友好的错误提示

### 优化效果
- ✓ 无文档时可以进行日常对话
- ✓ 提供友好的提示信息
- ✓ 避免无效的长时间等待
- ✓ 更好的用户体验

---

## 4. 实现真正的流式输出功能 (2026-02-13)

### 问题描述
流式接口 `/api/v1/query/stream` 报错：`TypeError: 'async for' requires an object with __aiter__ method, got coroutine`

### 根本原因
- `generate_answer(stream=True)` 返回的是协程，不是异步生成器
- `_generate_stream()` 方法未实现，抛出 `NotImplementedError`
- `requests` 库在异步环境中处理流式响应较复杂

### 解决方案
使用 `aiohttp` 库实现真正的逐字流式输出

### 修改的文件

#### 1. backend/requirements.txt
- 添加 `aiohttp==3.9.1` 依赖

#### 2. backend/app/services/llm_service.py
- 导入 `aiohttp` 库
- 实现 `_generate_stream()` 方法：
  - 使用 `aiohttp.ClientSession` 发送流式请求
  - 逐行读取响应内容
  - 解析 JSON 并提取 `response` 字段
  - 通过 `yield` 逐字返回生成的文本
- 更新 `generate_general_answer()` 方法：
  - 添加 `stream` 参数
  - 支持流式和非流式两种模式
  - 流式模式返回异步生成器

#### 3. backend/app/api/v1/query.py
- 重写 `/stream` 接口：
  - 无文档时：调用 `generate_general_answer(stream=True)`
  - 有文档且无 thinking：调用 `generate_answer(stream=True)`
  - 有文档且有 thinking：先非流式生成获取 thinking，再发送答案
  - 逐字发送答案 token
  - 添加完整的错误处理

### 实现细节

#### 流式响应格式
Ollama API 返回的流式响应格式：
```json
{"model":"...","response":"token","done":false}
{"model":"...","response":"","done":true}
```

#### SSE 事件类型
- `status`: 检索状态
- `thinking`: 推理步骤
- `answer`: 答案内容（逐字）
- `source`: 来源信息
- `done`: 完成信号
- `error`: 错误信息

### 优化效果
- ✓ 真正的逐字流式输出
- ✓ 支持无文档的通用对话流式模式
- ✓ 支持有文档的 RAG 流式模式
- ✓ 完整的错误处理和日志记录
- ✓ 更好的用户体验（实时看到生成过程）

### 使用说明
安装新依赖：
```bash
pip install aiohttp==3.9.1
```

---

