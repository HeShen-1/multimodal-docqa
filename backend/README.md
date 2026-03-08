# Backend

后端聚焦 FastAPI + RAG 主链路与工程可信度。

## 快速开始

```bash
conda activate multimodal-docqa
cd backend
pip install -r requirements.txt
python -m compileall app
pytest -q tests/unit/test_config.py tests/unit/test_document_processor.py tests/unit/test_ollama_client.py tests/unit/test_document_route_service.py tests/unit/test_permission_service.py tests/unit/test_share_routes.py tests/unit/test_share_service.py
python -m uvicorn app.main:app --reload
```

## Docker

```bash
cd backend
docker compose up -d postgres redis ollama
docker compose up -d --build backend celery-worker
```

## 当前重点能力

- 文档接口统一挂载 `/api/v1`
- 文档 / 分享数据统一由数据库驱动
- 管理路由默认管理员权限
- `/health`、`/health/detailed`、`/stats` 返回真实依赖状态
- SSE 问答支持 grounded answer 与拒答策略

## 关键目录

- `app/main.py`：应用入口
- `app/api/v1/`：路由层
- `app/services/`：业务服务
- `scripts/run_rag_eval_baseline.py`：评测脚本
- `scripts/evaluation/`：评测样本与示例文档

## 说明

- `Ollama` 当前可暂时不连通，不阻塞工程演示
- 投递说明请优先看仓库根 `README.md`
