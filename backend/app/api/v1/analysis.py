from datetime import datetime
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_current_user, get_db
from app.models.document import DocumentStatus
from app.models.document_db import Document
from app.models.response import ApiResponse
from app.schemas.analysis import CompareRequest, KeywordsRequest, SummaryRequest
from app.services.analysis_service import AnalysisService, analysis_service
from app.services.llm_service import LLMService
from app.services.resilience_service import resilience_manager


router = APIRouter(prefix="/analysis", tags=["智能分析"])


async def _get_user_document(db: AsyncSession, document_id: str, user_id: str) -> Document | None:
    stmt = select(Document).where(
        Document.id == document_id,
        Document.user_id == user_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


def _is_completed_document(document: Document) -> bool:
    return document.status == DocumentStatus.COMPLETED or str(document.status) == DocumentStatus.COMPLETED.value


def _get_scoped_analysis_service(model: str | None = None) -> AnalysisService:
    if not model:
        return analysis_service
    return AnalysisService(
        embedding_service=analysis_service.embedding_service,
        llm_service=LLMService(get_settings(), default_model=model),
    )


@router.post("/summary", response_model=ApiResponse, summary="文档摘要生成")
async def generate_document_summary(
    request: SummaryRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="未认证用户")

        document = await _get_user_document(db, request.document_id, user_id)
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在或无权访问")
        if not _is_completed_document(document):
            raise HTTPException(status_code=400, detail="文档尚未处理完成")

        scoped_analysis_service = _get_scoped_analysis_service(request.model)
        text = await scoped_analysis_service.get_document_text(document.id)
        if not text:
            raise HTTPException(status_code=404, detail="文档内容不存在，请先完成向量化处理")

        start_time = time.time()
        summary_result = await scoped_analysis_service.generate_summary(
            text=text,
            method=request.method,
            max_length=request.max_length,
            style=request.style,
        )

        return ApiResponse(
            code=100000,
            message="摘要生成成功",
            data={
                "documentId": document.id,
                "summary": summary_result["summary"],
                "method": summary_result["method"],
                "style": summary_result["style"],
                "sourceLength": summary_result["source_length"],
                "compressionRatio": summary_result["compression_ratio"],
                "fallbackUsed": summary_result["fallback_used"],
                "processingTime": round(time.time() - start_time, 3),
            },
            timestamp=datetime.utcnow(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"生成摘要失败: {exc}")
        raise HTTPException(status_code=500, detail=f"摘要生成失败: {exc}")


@router.post("/keywords", response_model=ApiResponse, summary="关键词提取")
async def extract_document_keywords(
    request: KeywordsRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="未认证用户")

        document = await _get_user_document(db, request.document_id, user_id)
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在或无权访问")
        if not _is_completed_document(document):
            raise HTTPException(status_code=400, detail="文档尚未处理完成")

        scoped_analysis_service = _get_scoped_analysis_service(request.model)
        text = await scoped_analysis_service.get_document_text(document.id)
        if not text:
            raise HTTPException(status_code=404, detail="文档内容不存在，请先完成向量化处理")

        start_time = time.time()
        keywords = await scoped_analysis_service.extract_keywords(
            text=text,
            method=request.method,
            top_k=request.top_k,
        )
        if not keywords:
            raise HTTPException(status_code=404, detail="未提取到关键词")

        return ApiResponse(
            code=100000,
            message="关键词提取成功",
            data={
                "documentId": document.id,
                "method": request.method,
                "keywords": keywords,
                "totalWords": len(scoped_analysis_service._tokenize(text)),
                "processingTime": round(time.time() - start_time, 3),
            },
            timestamp=datetime.utcnow(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"提取关键词失败: {exc}")
        raise HTTPException(status_code=500, detail=f"关键词提取失败: {exc}")


@router.post("/compare", response_model=ApiResponse, summary="文档对比")
async def compare_documents(
    request: CompareRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="未认证用户")
        if request.document_id_a == request.document_id_b:
            raise HTTPException(status_code=400, detail="请提供两个不同的文档 ID")

        document_a = await _get_user_document(db, request.document_id_a, user_id)
        document_b = await _get_user_document(db, request.document_id_b, user_id)
        if not document_a or not document_b:
            raise HTTPException(status_code=404, detail="文档不存在或无权访问")
        if not _is_completed_document(document_a) or not _is_completed_document(document_b):
            raise HTTPException(status_code=400, detail="文档尚未处理完成")

        start_time = time.time()
        compare_result = await analysis_service.compare_documents(
            doc_a=document_a,
            doc_b=document_b,
            top_k=request.top_k,
        )

        return ApiResponse(
            code=100000,
            message="文档对比成功",
            data={
                "documentA": {"id": document_a.id, "name": document_a.file_name},
                "documentB": {"id": document_b.id, "name": document_b.file_name},
                "result": compare_result,
                "processingTime": round(time.time() - start_time, 3),
            },
            timestamp=datetime.utcnow(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"文档对比失败: {exc}")
        raise HTTPException(status_code=500, detail=f"文档对比失败: {exc}")


@router.get("/similar/{document_id}", response_model=ApiResponse, summary="相似文档推荐")
async def recommend_similar_documents(
    document_id: str,
    limit: int = Query(5, ge=1, le=20, description="返回数量"),
    min_similarity: float = Query(0.4, ge=0.0, le=1.0, alias="minSimilarity", description="最小相似度"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        flags = resilience_manager.evaluate_degradation().get("flags", {})
        if not flags.get("documentRecommendationEnabled", True):
            raise HTTPException(status_code=503, detail="系统降级中，文档推荐功能暂不可用")

        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="未认证用户")

        source_document = await _get_user_document(db, document_id, user_id)
        if not source_document:
            raise HTTPException(status_code=404, detail="文档不存在或无权访问")
        if not _is_completed_document(source_document):
            raise HTTPException(status_code=400, detail="文档尚未处理完成")

        stmt = (
            select(Document)
            .where(
                Document.user_id == user_id,
                Document.id != document_id,
                Document.status == DocumentStatus.COMPLETED,
            )
            .order_by(Document.created_at.desc())
            .limit(100)
        )
        candidate_documents = (await db.execute(stmt)).scalars().all()

        start_time = time.time()
        similar_documents = await analysis_service.recommend_similar_documents(
            source_doc=source_document,
            target_docs=candidate_documents,
            limit=limit,
            min_similarity=min_similarity,
        )

        return ApiResponse(
            code=100000,
            message="相似文档推荐成功",
            data={
                "sourceDocument": {
                    "id": source_document.id,
                    "name": source_document.file_name,
                    "uploadTime": source_document.created_at.isoformat() if source_document.created_at else "",
                },
                "similarDocuments": similar_documents,
                "total": len(similar_documents),
                "processingTime": round(time.time() - start_time, 3),
            },
            timestamp=datetime.utcnow(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"相似文档推荐失败: {exc}")
        raise HTTPException(status_code=500, detail=f"相似文档推荐失败: {exc}")
