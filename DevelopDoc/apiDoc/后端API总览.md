# 多模态 DocQA 后端 API 总览

更新时间：2026-03-05  
服务入口：`http://127.0.0.1:8000`  
版本前缀：`/api/v1`

## 1. 说明

- 本文档基于当前后端代码路由自动梳理（共 **67** 个接口）。
- 统一响应结构：`code`、`message`、`data`、`timestamp`（少数接口可能返回标准错误结构）。
- 鉴权方式：`Authorization: Bearer <access_token>`。
- 当前无需登录的常见接口：
  - `GET /`
  - `GET /api/v1/health`
  - `GET /api/v1/health/detailed`
  - `GET /api/v1/stats`
  - `POST /api/v1/auth/register`
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/refresh`
  - `POST /api/v1/share/{token}/access`

---

## 2. Root

| 方法 | 路径 | 登录 | 说明 |
|---|---|---|---|
| GET | `/` | 否 | API 根信息 |

## 3. Health

| 方法 | 路径 | 登录 | 说明 |
|---|---|---|---|
| GET | `/api/v1/health` | 否 | 健康检查 |
| GET | `/api/v1/health/detailed` | 否 | 详细健康检查（Phase 8） |
| GET | `/api/v1/stats` | 否 | 统计信息 |

## 4. Auth

| 方法 | 路径 | 登录 | 说明 |
|---|---|---|---|
| POST | `/api/v1/auth/register` | 否 | 用户注册 |
| POST | `/api/v1/auth/login` | 否 | 用户登录，返回 access/refresh token |
| POST | `/api/v1/auth/refresh` | 否 | 刷新 access token |
| POST | `/api/v1/auth/logout` | 是 | 用户登出，撤销 Token |
| GET | `/api/v1/auth/me` | 是 | 获取当前用户信息 |
| GET | `/api/v1/auth/sessions` | 是 | 获取活跃会话列表 |
| DELETE | `/api/v1/auth/sessions/{session_id}` | 是 | 撤销指定会话 |

## 5. Conversations

| 方法 | 路径 | 登录 | 说明 |
|---|---|---|---|
| POST | `/api/v1/conversations` | 是 | 创建对话 |
| GET | `/api/v1/conversations` | 是 | 对话列表 |
| GET | `/api/v1/conversations/{conversation_id}` | 是 | 对话详情 |
| DELETE | `/api/v1/conversations/{conversation_id}` | 是 | 删除对话 |
| POST | `/api/v1/conversations/{conversation_id}/messages` | 是 | 发送消息并获取回复 |
| POST | `/api/v1/conversations/{conversation_id}/messages/stream` | 是 | 流式对话（SSE） |
| PATCH | `/api/v1/conversations/{conversation_id}/title` | 是 | 更新对话标题 |
| GET | `/api/v1/conversations/{conversation_id}/export` | 是 | 导出对话（markdown/json/pdf） |

补充说明：
- `POST /api/v1/conversations/{conversation_id}/messages`
- `POST /api/v1/conversations/{conversation_id}/messages/stream`
- 两个接口均新增可选字段 `model`，支持传入 `deepseek` 或 `qwen3-vl:2b-thinking-q4_K_M`
- 当用户当前已处于“最新空白会话”时，后端会复用该会话，避免重复创建草稿会话
- 流式 SSE 的 `done` 事件现额外返回：
  - `model_name`
  - `latency_ms`
  - `retrieved_chunks`
  - `citation_count`
  - `fallback_reason`
  - `retrieval_strategy`
  - `rewritten_query`

## 6. Documents

| 方法 | 路径 | 登录 | 说明 |
|---|---|---|---|
| POST | `/api/v1/documents/upload` | 是 | 上传单个文档 |
| GET | `/api/v1/documents` | 否 | 文档列表 |
| GET | `/api/v1/documents/{document_id}` | 否 | 文档详情 |
| GET | `/api/v1/documents/{document_id}/chunks` | 是 | 文档切块列表 |
| GET | `/api/v1/documents/{document_id}/file` | 是 | 原始文件预览/下载 |
| DELETE | `/api/v1/documents/{document_id}` | 否 | 删除文档 |
| GET | `/api/v1/documents/{document_id}/status` | 否 | 文档处理状态 |
| POST | `/api/v1/documents/batch-upload` | 是 | 批量上传 |
| GET | `/api/v1/documents/batch/{batch_id}/status` | 是 | 批量任务状态 |
| POST | `/api/v1/documents/{document_id}/tags` | 是 | 为文档打标签 |
| GET | `/api/v1/documents/{document_id}/tags` | 是 | 获取文档标签 |
| DELETE | `/api/v1/documents/{document_id}/tags` | 是 | 移除文档标签 |

补充说明：
- `GET /api/v1/documents/{document_id}` 现额外返回 `previewText`，用于文档文本预览
- `GET /api/v1/documents/{document_id}` / `GET /api/v1/documents` 现额外返回 `processingSummary`：
  - `extractMethod`
  - `ocrUsed`
  - `pageCount`
  - `chunkCount`
  - `hasTables`
  - `hasImages`
  - `sourceType`
- `GET /api/v1/documents/{document_id}/chunks` 返回按页码与切块序号排序后的文本块
- `GET /api/v1/documents/{document_id}/file` 可用于前端打开原始文件预览

## 7. Tags

| 方法 | 路径 | 登录 | 说明 |
|---|---|---|---|
| POST | `/api/v1/tags` | 是 | 创建标签 |
| GET | `/api/v1/tags` | 是 | 标签列表 |
| GET | `/api/v1/tags/popular` | 是 | 热门标签 |
| GET | `/api/v1/tags/search` | 是 | 搜索标签 |
| GET | `/api/v1/tags/{tag_id}` | 是 | 标签详情 |
| PATCH | `/api/v1/tags/{tag_id}` | 是 | 更新标签 |
| DELETE | `/api/v1/tags/{tag_id}` | 是 | 删除标签 |

## 8. Share

| 方法 | 路径 | 登录 | 说明 |
|---|---|---|---|
| POST | `/api/v1/share/documents/{document_id}` | 是 | 创建分享链接 |
| GET | `/api/v1/share/documents/{document_id}` | 是 | 获取文档分享列表 |
| DELETE | `/api/v1/share/{share_id}` | 是 | 撤销分享链接 |
| POST | `/api/v1/share/cleanup` | 是 | 清理过期分享链接 |
| POST | `/api/v1/share/{token}/access` | 否 | 通过 token 访问分享 |

## 9. 缓存管理（Phase 3）

| 方法 | 路径 | 登录 | 说明 |
|---|---|---|---|
| GET | `/api/v1/cache/stats` | 是 | 缓存统计 |
| GET | `/api/v1/cache/hot-keys` | 是 | 热点键 |
| DELETE | `/api/v1/cache/clear` | 是 | 清理缓存 |
| POST | `/api/v1/cache/warmup` | 是 | 缓存预热 |
| GET | `/api/v1/cache/keys-count` | 是 | 各类型缓存键数量 |
| GET | `/api/v1/cache/detail/{key}` | 是 | 缓存键详情 |

## 10. 高级检索（Phase 5）

| 方法 | 路径 | 登录 | 说明 |
|---|---|---|---|
| POST | `/api/v1/query/multi-doc` | 是 | 多文档联合检索 |
| POST | `/api/v1/query/rerank` | 是 | 检索重排序 |
| GET | `/api/v1/query/suggestions` | 是 | 相似问题推荐 |
| GET | `/api/v1/documents/{document_id}/similar` | 是 | 相关文档推荐 |

## 11. 智能分析（Phase 6）

| 方法 | 路径 | 登录 | 说明 |
|---|---|---|---|
| POST | `/api/v1/analysis/summary` | 是 | 文档摘要 |
| POST | `/api/v1/analysis/keywords` | 是 | 关键词提取 |
| POST | `/api/v1/analysis/compare` | 是 | 文档对比 |
| GET | `/api/v1/analysis/similar/{document_id}` | 是 | 相似文档推荐 |

补充说明：
- `POST /api/v1/analysis/summary` 新增可选字段 `model`
- `POST /api/v1/analysis/keywords` 新增可选字段 `model`
- `summary.style` 支持 `简洁 | 详细 | concise | detailed`

## 12. 系统监控与管理（Phase 7）

| 方法 | 路径 | 登录 | 说明 |
|---|---|---|---|
| GET | `/api/v1/admin/tasks` | 是 | 任务队列监控 |
| POST | `/api/v1/admin/tasks/retry` | 是 | 重试任务 |
| POST | `/api/v1/admin/tasks/{task_id}/cancel` | 是 | 取消任务 |
| POST | `/api/v1/admin/tasks/cleanup` | 是 | 清理僵尸任务 |
| GET | `/api/v1/admin/api-stats` | 是 | API 调用统计 |
| GET | `/api/v1/admin/logs/errors` | 是 | 错误日志查询 |
| GET | `/api/v1/admin/performance` | 是 | 系统性能监控 |

## 13. 系统稳定性（Phase 8）

| 方法 | 路径 | 登录 | 说明 |
|---|---|---|---|
| GET | `/api/v1/stability/status` | 是 | 稳定性状态概览 |
| POST | `/api/v1/stability/degradation/evaluate` | 是 | 触发降级评估 |
| POST | `/api/v1/stability/degradation/manual/{level}` | 是 | 手动设置降级级别 |
| DELETE | `/api/v1/stability/degradation/manual` | 是 | 清除手动降级 |
| GET | `/api/v1/stability/health` | 是 | 稳定性详细健康检查 |

---

## 14. 补充说明

- 文档中“是否登录”依据当前路由依赖（`Depends(get_current_user)`）整理。
- `admin` / `stability` 模块当前代码已要求登录，管理员角色细粒度校验建议后续补齐。
- 若接口有增删改，请同步更新本文件，避免与实际代码不一致。
