# AGENTS.md

本文件用于指导在 `multimodal-docqa` 仓库内协作开发的智能代理与开发者。

## 1) 仓库概览

- 前端/其他：仓库根目录下的其他子目录按实际需求使用。
- 后端主工程：`backend/`（FastAPI + SQLAlchemy + Redis + Celery）。
- 开发文档：`DevelopDoc/`。

## 2) 后端目录约定（重点）

- `backend/app/main.py`：应用入口、路由挂载、中间件。
- `backend/app/api/v1/`：API 路由层（按功能拆分）。
- `backend/app/services/`：业务服务层（外部调用、检索、监控、稳定性等）。
- `backend/app/models/`：Pydantic/SQLAlchemy 模型。
- `backend/app/schemas/`：请求/响应 schema。
- `backend/scripts/`：集成测试和运维脚本。
- `backend/logs/`：运行日志和测试日志。

## 3) 开发规范

- 所有后端路由统一挂在 `/api/v1` 前缀下。
- 新接口优先使用统一响应结构 `ApiResponse`。
- 需要登录的接口统一使用 `Depends(get_current_user)`。
- 变更接口后必须同步更新 API 文档（`DevelopDoc/apiDoc/`）。
- 日志使用 `loguru`，记录关键上下文（请求ID、用户、耗时、错误信息）。
- 优先修复根因，不做仅“表面兜底”的补丁。

## 4) 测试与验证

- 推荐环境：`conda` 环境 `multimodal-docqa`。
- 语法检查：`python -m compileall app`
- 单元/集成测试：`pytest -v`
- 阶段性脚本测试示例：
  - `python -m scripts.run_phase6_api_tests`
  - `python -m scripts.run_phase78_api_tests`

## 5) 文档输出要求

- API 总览文档放在：`DevelopDoc/apiDoc/`
- 开发说明文档放在：`DevelopDoc/backendDoc/`
- 测试输出建议包含：
  - 请求方法、路径、参数
  - 响应状态码与响应体摘要
  - 失败堆栈和定位建议

## 6) 变更边界

- 不要在未被要求时修改无关模块。
- 不要提交敏感凭据（账号、token、密钥）到代码或文档。
- 大范围重构前先产出简短方案并与需求方确认。
