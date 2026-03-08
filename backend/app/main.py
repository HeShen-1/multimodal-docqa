from contextlib import asynccontextmanager
import time
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from slowapi.errors import RateLimitExceeded

from app.api.v1.admin import router as admin_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.auth import router as auth_router
from app.api.v1.cache import router as cache_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.share import router as share_router
from app.api.v1.stability import router as stability_router
from app.api.v1.tags import router as tags_router
from app.config import get_settings
from app.dependencies import close_engine
from app.services.monitoring_service import api_stats_collector
from app.services.rate_limiter import limiter, rate_limit_exceeded_handler
from app.utils.logger import setup_logger


settings = get_settings()

try:
    from app.api.v1.advanced_retrieval import router as advanced_retrieval_router
except Exception as exc:
    advanced_retrieval_router = None
    logger.warning(f"高级检索模块加载失败，将跳过路由注册: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logger(settings.log_level, settings.log_file)
    logger.info("应用启动")

    if settings.cache_enabled:
        from app.services.cache_service import cache_service

        await cache_service.connect()
        logger.info("缓存服务已连接")

    yield

    if settings.cache_enabled:
        from app.services.cache_service import cache_service

        await cache_service.disconnect()
        logger.info("缓存服务已断开")

    await close_engine()
    logger.info("数据库连接池已关闭")
    logger.info("应用关闭")


app = FastAPI(
    title=settings.app_name,
    description="基于 FastAPI + PostgreSQL + Redis + 向量检索的多模态文档问答后端",
    version=settings.app_version,
    lifespan=lifespan,
    swagger_ui_init_oauth={"usePkceWithAuthorizationCodeGrant": True},
    swagger_ui_parameters={"persistAuthorization": True},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials="*" not in settings.cors_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


@app.middleware("http")
async def collect_api_stats(request, call_next):
    request_id = uuid4().hex[:12]
    start = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"
    user_id = api_stats_collector.extract_user_id(request.headers.get("Authorization"))

    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        api_stats_collector.record_request(
            method=request.method,
            path=request.url.path,
            status_code=500,
            duration_ms=duration_ms,
            user_id=user_id,
            request_id=request_id,
            client_ip=client_ip,
        )
        logger.exception(
            f"API 请求异常: request_id={request_id}, method={request.method}, path={request.url.path}, "
            f"user_id={user_id}, client_ip={client_ip}, duration_ms={round(duration_ms, 3)}, error={exc}"
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    api_stats_collector.record_request(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        user_id=user_id,
        request_id=request_id,
        client_ip=client_ip,
    )

    logger.info(
        f"API 请求: request_id={request_id}, method={request.method}, path={request.url.path}, "
        f"status={response.status_code}, user_id={user_id}, client_ip={client_ip}, duration_ms={round(duration_ms, 3)}"
    )
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(cache_router, prefix="/api/v1")
app.include_router(tags_router, prefix="/api/v1")
app.include_router(share_router, prefix="/api/v1")
if advanced_retrieval_router is not None:
    app.include_router(advanced_retrieval_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(stability_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "message": f"{settings.app_name} API",
        "version": settings.app_version,
        "docs": "/docs",
        "features": [
            "用户认证与权限控制",
            "文档上传与处理",
            "多轮对话与 SSE 流式回答",
            "标签与分享访问",
            "健康检查与系统监控",
            "高级检索能力（按依赖可选加载）",
        ],
        "notes": {
            "ollama": "当前允许 Ollama 暂不可用，后续可接入微调模型，不影响工程链路演示。",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
