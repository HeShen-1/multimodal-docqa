from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from app.models.response import ApiResponse
from app.services.monitoring_service import api_stats_collector, log_manager, performance_monitor, task_monitor
from app.services.permission_service import require_admin


router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


class RetryTaskRequest(BaseModel):
    task_name: str = Field(..., description="任务名，例如 tasks.process_single_document")
    args: List[Any] = Field(default_factory=list, description="位置参数")
    kwargs: Dict[str, Any] = Field(default_factory=dict, description="关键字参数")


@router.get("/tasks", response_model=ApiResponse, summary="任务队列监控")
async def get_task_snapshot():
    snapshot = task_monitor.get_snapshot()
    return ApiResponse(code=100000, message="获取任务监控成功", data=snapshot)


@router.post("/tasks/retry", response_model=ApiResponse, summary="重试失败任务")
async def retry_task(request: RetryTaskRequest):
    try:
        result = task_monitor.retry_task(
            task_name=request.task_name,
            args=request.args,
            kwargs=request.kwargs,
        )
        return ApiResponse(code=100000, message="任务已提交重试", data=result)
    except Exception as exc:
        logger.error(f"重试任务失败: {exc}")
        raise HTTPException(status_code=500, detail=f"重试任务失败: {exc}") from exc


@router.post("/tasks/{task_id}/cancel", response_model=ApiResponse, summary="取消运行中的任务")
async def cancel_task(
    task_id: str,
    terminate: bool = Query(True, description="是否强制终止"),
    signal: str = Query("SIGTERM", description="终止信号"),
):
    try:
        task_monitor.cancel_task(task_id=task_id, terminate=terminate, signal=signal)
        return ApiResponse(
            code=100000,
            message="任务取消请求已发送",
            data={"taskId": task_id, "terminate": terminate, "signal": signal},
        )
    except Exception as exc:
        logger.error(f"取消任务失败: task_id={task_id}, error={exc}")
        raise HTTPException(status_code=500, detail=f"取消任务失败: {exc}") from exc


@router.post("/tasks/cleanup", response_model=ApiResponse, summary="清理僵尸任务")
async def cleanup_zombie_tasks(
    max_runtime_seconds: int = Query(3600, ge=60, le=86400, description="最大允许运行时长"),
):
    result = task_monitor.cleanup_zombie_tasks(max_runtime_seconds=max_runtime_seconds)
    return ApiResponse(code=100000, message="僵尸任务清理完成", data=result)


@router.get("/api-stats", response_model=ApiResponse, summary="API 调用统计")
async def get_api_stats(
    hours: int = Query(24, ge=1, le=168, description="统计时间窗口（小时）"),
):
    report = api_stats_collector.get_report(hours=hours)
    return ApiResponse(code=100000, message="获取 API 统计成功", data=report)


@router.get("/logs/errors", response_model=ApiResponse, summary="错误日志查询")
async def query_error_logs(
    levels: str = Query("ERROR,WARNING,CRITICAL", description="日志级别，逗号分隔"),
    start_time: Optional[str] = Query(None, description="开始时间（ISO 格式）"),
    end_time: Optional[str] = Query(None, description="结束时间（ISO 格式）"),
    keyword: Optional[str] = Query(None, description="关键词匹配"),
    regex: Optional[str] = Query(None, description="正则匹配"),
    limit: int = Query(200, ge=1, le=1000, description="返回日志条数"),
):
    level_list = [level.strip() for level in levels.split(",") if level.strip()]
    result = log_manager.query_errors(
        levels=level_list,
        start_time=start_time,
        end_time=end_time,
        keyword=keyword,
        regex_pattern=regex,
        limit=limit,
    )
    return ApiResponse(code=100000, message="获取错误日志成功", data=result)


@router.get("/performance", response_model=ApiResponse, summary="系统性能监控")
async def get_performance_metrics(
    include_alerts: bool = Query(True, description="是否包含告警信息"),
):
    metrics = performance_monitor.collect_metrics()
    alerts = performance_monitor.evaluate_alerts(metrics) if include_alerts else []
    return ApiResponse(
        code=100000,
        message="获取性能监控成功",
        data={
            "metrics": metrics,
            "alerts": alerts,
            "collectedAt": datetime.utcnow().isoformat(),
        },
    )
