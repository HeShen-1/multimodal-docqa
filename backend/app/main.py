from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.utils.logger import setup_logger
from app.api.v1 import documents_router, query_router, health_router
from app.api.v1.auth import router as auth_router
from app.services.rate_limiter import limiter, rate_limit_exceeded_handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    settings = get_settings()
    setup_logger(settings.log_level, settings.log_file)
    
    from loguru import logger
    logger.info("应用启动")
    
    yield
    
    # 关闭时执行
    logger.info("应用关闭")


# 创建FastAPI应用
app = FastAPI(
    title="多模态文档智能问答系统",
    description="基于Ollama + ChromaDB的本地化文档问答系统",
    version="2.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置限流器
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# 注册路由
app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(query_router, prefix="/api/v1")


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "多模态文档智能问答系统 API",
        "version": "2.0.0",
        "docs": "/docs",
        "features": [
            "用户认证与权限管理",
            "文档上传与处理",
            "智能问答",
            "多轮对话（规划中）"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )

