import time
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_db
from app.models.document import DocumentStatus
from app.models.document_db import Document as DocumentDB
from app.models.response import ApiResponse, HealthResponse, StatsResponse
from app.services.monitoring_service import api_stats_collector
from app.services.resilience_service import resilience_manager


router = APIRouter(tags=["health"])
start_time = time.time()


def _normalize_component_status(component: Dict[str, Any]) -> str:
    status = str(component.get("status", "unknown")).lower()
    if status in {"healthy", "degraded", "unhealthy"}:
        return status
    return "unknown"


def _build_health_summary(payload: Dict[str, Any]) -> HealthResponse:
    components = payload.get("components", {})
    settings = get_settings()
    return HealthResponse(
        status=payload.get("status", "unknown"),
        version=settings.app_version,
        services={
            "postgres": _normalize_component_status(components.get("database", {})),
            "redis": _normalize_component_status(components.get("redis", {})),
            "ollama": _normalize_component_status(components.get("ollama", {})),
            "vectorDB": _normalize_component_status(components.get("vectorDB", {})),
            "resources": _normalize_component_status(components.get("resources", {})),
        },
    )


def _format_bytes(total_bytes: int) -> str:
    value = float(max(total_bytes, 0))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)}{unit}"
            return f"{value:.2f}{unit}"
        value /= 1024
    return "0B"


async def _load_query_count(db: AsyncSession) -> int:
    try:
        result = await db.execute(text("SELECT COUNT(*) FROM query_history"))
        return int(result.scalar() or 0)
    except Exception as exc:
        logger.warning(f"读取 query_history 统计失败，按 0 返回: {exc}")
        return 0


@router.get("/health", response_model=HealthResponse)
async def health_check():
    result = await resilience_manager.check_health()
    return _build_health_summary(result)


@router.get("/health/detailed", response_model=ApiResponse)
async def detailed_health_check():
    result = await resilience_manager.check_health()
    return ApiResponse(code=100000, message="success", data=result)


@router.get("/stats", response_model=ApiResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    try:
        total_documents_result = await db.execute(select(func.count(DocumentDB.id)))
        total_documents = int(total_documents_result.scalar() or 0)

        totals_result = await db.execute(
            select(
                func.coalesce(func.sum(DocumentDB.chunk_count), 0),
                func.coalesce(func.sum(DocumentDB.image_count), 0),
                func.coalesce(func.sum(DocumentDB.file_size), 0),
            )
        )
        total_chunks, total_images, storage_bytes = totals_result.one()

        completed_documents = (
            await db.execute(
                select(DocumentDB.created_at, DocumentDB.updated_at).where(
                    DocumentDB.status == DocumentStatus.COMPLETED
                )
            )
        ).all()
        avg_processing_time = 0.0
        if completed_documents:
            durations = [
                max((updated_at - created_at).total_seconds(), 0.0)
                for created_at, updated_at in completed_documents
                if created_at and updated_at
            ]
            if durations:
                avg_processing_time = round(sum(durations) / len(durations), 3)

        api_report = api_stats_collector.get_report(hours=24)
        avg_query_time = round(api_report["summary"].get("avgResponseMs", 0.0) / 1000, 3)
        total_queries = await _load_query_count(db)

        stats = StatsResponse(
            totalDocuments=total_documents,
            totalQueries=total_queries,
            totalChunks=int(total_chunks or 0),
            totalImages=int(total_images or 0),
            avgProcessingTime=avg_processing_time,
            avgQueryTime=avg_query_time,
            storageUsed=_format_bytes(int(storage_bytes or 0)),
            uptime=int(time.time() - start_time),
        )
        return ApiResponse(code=100000, message="success", data=stats)
    except Exception as exc:
        logger.error(f"统计接口读取失败: {exc}")
        raise HTTPException(status_code=503, detail=f"统计数据暂时不可用: {exc}") from exc
