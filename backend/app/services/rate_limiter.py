import os
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from loguru import logger

from app.config import get_settings


settings = get_settings()


# 创建限流器实例
# 设置环境变量以避免 slowapi 读取 .env 文件时的编码问题
os.environ.setdefault("RATELIMIT_ENABLED", str(settings.rate_limit_enabled))

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.rate_limit_enabled,
    storage_uri=f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}",
    strategy="fixed-window",
    config_filename=""  # 使用空字符串而不是 None，完全禁用配置文件读取
)


def get_limiter():
    """获取限流器实例"""
    return limiter


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """限流异常处理"""
    logger.warning(f"请求限流: {request.client.host} - {request.url.path}")
    return _rate_limit_exceeded_handler(request, exc)

