from fastapi import APIRouter
from app.models.response import HealthResponse, ApiResponse, StatsResponse
import time

router = APIRouter(tags=["health"])

# 记录启动时间
start_time = time.time()


@router.get("/health")
async def health_check():
    """健康检查"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        services={
            "ollama": "healthy",
            "chromadb": "healthy",
            "milvus": "unknown",
            "redis": "unknown",
            "postgres": "unknown"
        }
    )


@router.get("/stats", response_model=ApiResponse)
async def get_stats():
    """获取统计信息"""
    from app.api.v1.documents import documents_db
    from app.api.v1.query import query_history_db
    
    total_chunks = sum(
        doc.get("chunkCount", 0) 
        for doc in documents_db.values()
    )
    
    total_images = sum(
        doc.get("imageCount", 0) 
        for doc in documents_db.values()
    )
    
    avg_query_time = (
        sum(q.get("processingTime", 0) for q in query_history_db) / len(query_history_db)
        if query_history_db else 0
    )
    
    stats = StatsResponse(
        totalDocuments=len(documents_db),
        totalQueries=len(query_history_db),
        totalChunks=total_chunks,
        totalImages=total_images,
        avgProcessingTime=2.5,
        avgQueryTime=round(avg_query_time, 2),
        storageUsed="0MB",
        uptime=int(time.time() - start_time)
    )
    
    return ApiResponse(
        code=100000,
        message="success",
        data=stats
    )

