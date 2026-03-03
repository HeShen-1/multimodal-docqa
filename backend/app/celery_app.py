from celery import Celery
from app.config import get_settings

settings = get_settings()

# 创建 Celery 应用
celery_app = Celery(
    "multimodal_docqa",
    broker=f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}",
    backend=f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
)

# Celery 配置
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1小时超时
    task_soft_time_limit=3000,  # 50分钟软超时
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    imports=['app.services.batch_upload_service']  # 导入任务模块
)

