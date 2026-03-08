from fastapi import APIRouter, Depends, Query

from app.models.response import ApiResponse
from app.services.permission_service import get_current_user
from app.services.resilience_service import DegradationLevel, resilience_manager


router = APIRouter(prefix="/stability", tags=["系统稳定性"])


@router.get("/status", response_model=ApiResponse, summary="稳定性状态概览")
async def get_stability_status(current_user: dict = Depends(get_current_user)):
    del current_user
    return ApiResponse(code=100000, message="获取稳定性状态成功", data=resilience_manager.status_snapshot())


@router.post("/degradation/evaluate", response_model=ApiResponse, summary="执行降级评估")
async def evaluate_degradation(current_user: dict = Depends(get_current_user)):
    del current_user
    result = resilience_manager.evaluate_degradation()
    return ApiResponse(code=100000, message="降级评估完成", data=result)


@router.post("/degradation/manual/{level}", response_model=ApiResponse, summary="手动设置降级级别")
async def set_manual_degradation_level(
    level: DegradationLevel,
    current_user: dict = Depends(get_current_user),
):
    del current_user
    resilience_manager.degradation.set_manual_level(level)
    return ApiResponse(
        code=100000,
        message="手动降级级别设置成功",
        data=resilience_manager.degradation.snapshot(),
    )


@router.delete("/degradation/manual", response_model=ApiResponse, summary="清除手动降级设置")
async def clear_manual_degradation(current_user: dict = Depends(get_current_user)):
    del current_user
    resilience_manager.degradation.clear_manual_level()
    return ApiResponse(
        code=100000,
        message="已恢复自动降级策略",
        data=resilience_manager.degradation.snapshot(),
    )


@router.get("/health", response_model=ApiResponse, summary="详细健康检查")
async def get_detailed_health(
    refresh_degradation: bool = Query(True, description="检查前是否刷新降级状态"),
    current_user: dict = Depends(get_current_user),
):
    del current_user
    if refresh_degradation:
        resilience_manager.evaluate_degradation()

    health_result = await resilience_manager.check_health()
    return ApiResponse(code=100000, message="健康检查完成", data=health_result)
