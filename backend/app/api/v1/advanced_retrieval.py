"""
Phase 5 高级检索功能 API
"""
from datetime import datetime
import time
import uuid
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.document import DocumentStatus
from app.models.document_db import Document
from app.models.query_history import QueryHistory
from app.schemas.advanced_retrieval import MultiDocQueryRequest, RerankRequest
from app.models.response import ApiResponse as BaseResponse
from app.services.cache_service import cache_service
from app.services.embedding_service import EmbeddingService
from app.services.multi_doc_retriever import MultiDocRetriever
from app.services.recommendation_service import get_recommendation_service
from app.services.reranker_service import get_reranker_service
from app.services.resilience_service import resilience_manager
from app.services.retrieval_service import RetrievalService


router = APIRouter(tags=["高级检索"])


async def _get_user_document(
    db: AsyncSession, document_id: str, user_id: str
) -> Optional[Document]:
    stmt = select(Document).where(Document.id == document_id, Document.user_id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def _record_query_history(
    db: AsyncSession,
    user_id: str,
    question: str,
    document_ids: list[str],
    embedding_service: EmbeddingService,
    document_name_map: Dict[str, str],
) -> None:
    try:
        user_uuid = uuid.UUID(user_id)
    except (TypeError, ValueError):
        logger.warning(f"无效 user_id，跳过历史记录: {user_id}")
        return

    try:
        question_embedding = await embedding_service.embed_query(question)
    except Exception as exc:
        logger.warning(f"问题向量化失败，跳过历史记录: {exc}")
        return

    try:
        for doc_id in document_ids:
            stmt = select(QueryHistory).where(
                QueryHistory.user_id == user_uuid,
                QueryHistory.question == question,
                QueryHistory.document_id == doc_id,
            )
            existing = (await db.execute(stmt)).scalar_one_or_none()

            if existing:
                existing.query_count += 1
                existing.last_queried = datetime.utcnow()
                continue

            history = QueryHistory(
                user_id=user_uuid,
                question=question,
                question_embedding=question_embedding,
                document_id=doc_id,
                document_name=document_name_map.get(doc_id),
            )
            db.add(history)

        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.error(f"记录查询历史失败: {exc}")


@router.post("/query/multi-doc", summary="多文档联合检索")
async def multi_doc_query(
    request: MultiDocQueryRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        degradation = resilience_manager.evaluate_degradation()
        flags = degradation.get("flags", {})

        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="未认证用户")

        document_name_map: Dict[str, str] = {}
        for doc_id in request.document_ids:
            doc = await _get_user_document(db, doc_id, user_id)
            if not doc:
                raise HTTPException(status_code=404, detail=f"文档 {doc_id} 不存在或无权访问")
            if doc.status != DocumentStatus.COMPLETED:
                raise HTTPException(status_code=400, detail=f"文档 {doc_id} 尚未处理完成")
            document_name_map[doc_id] = doc.file_name

        retrieval_service = RetrievalService()
        retriever = MultiDocRetriever(
            retrieval_service=retrieval_service,
            cache_service=cache_service,
            fusion_method=request.fusion_method,
        )

        start_time = time.time()
        result = await retriever.retrieve(
            question=request.question,
            document_ids=request.document_ids,
            top_k=min(request.top_k, flags.get("maxRetrievalTopK", request.top_k)),
            enable_rerank=request.enable_rerank and flags.get("rerankEnabled", True),
        )
        result["processing_time"] = round(time.time() - start_time, 2)

        embedding_service = EmbeddingService()
        await _record_query_history(
            db=db,
            user_id=user_id,
            question=request.question,
            document_ids=request.document_ids,
            embedding_service=embedding_service,
            document_name_map=document_name_map,
        )

        return BaseResponse(
            code=200,
            message="检索成功",
            data=result,
            timestamp=datetime.utcnow(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"多文档检索失败: {exc}")
        raise HTTPException(status_code=500, detail=f"检索失败: {exc}")


@router.post("/query/rerank", summary="检索结果重排")
async def rerank_query(
    request: RerankRequest,
    current_user: dict = Depends(get_current_user),
):
    del current_user
    try:
        degradation = resilience_manager.evaluate_degradation()
        flags = degradation.get("flags", {})
        if not flags.get("rerankEnabled", True):
            raise HTTPException(status_code=503, detail="系统降级中，重排序功能暂不可用")

        for candidate in request.candidates:
            if not candidate.content:
                raise HTTPException(status_code=400, detail="候选结果必须包含 content 字段")

        reranker_service = get_reranker_service(
            model_name=request.model,
            cache_service=cache_service,
        )

        start_time = time.time()
        candidates_dict = [item.model_dump() for item in request.candidates]
        results = await reranker_service.rerank(
            question=request.question,
            candidates=candidates_dict,
            top_k=request.top_k,
        )

        return BaseResponse(
            code=200,
            message="重排序成功",
            data={
                "results": results,
                "total": len(results),
                "model": request.model,
                "processing_time": round(time.time() - start_time, 2),
            },
            timestamp=datetime.utcnow(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"重排序失败: {exc}")
        raise HTTPException(status_code=500, detail=f"重排序失败: {exc}")


@router.get("/query/suggestions", summary="相似问题推荐")
async def get_suggestions(
    question: Optional[str] = Query(None, description="参考问题"),
    document_id: Optional[str] = Query(None, description="文档ID"),
    limit: int = Query(5, ge=1, le=20, description="返回数量"),
    min_similarity: float = Query(0.7, ge=0.0, le=1.0, description="最小相似度阈值"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        degradation = resilience_manager.evaluate_degradation()
        flags = degradation.get("flags", {})
        if not flags.get("recommendationEnabled", True):
            raise HTTPException(status_code=503, detail="系统降级中，推荐功能暂不可用")

        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="未认证用户")

        if document_id:
            doc = await _get_user_document(db, document_id, user_id)
            if not doc:
                raise HTTPException(status_code=404, detail="文档不存在或无权访问")

        recommendation_service = get_recommendation_service(
            embedding_service=EmbeddingService(),
            vector_store=None,
            cache_service=cache_service,
            db_session=db,
        )

        start_time = time.time()
        suggestions = await recommendation_service.suggest_questions(
            question=question,
            document_id=document_id,
            limit=limit,
            min_similarity=min_similarity,
        )

        if not suggestions:
            raise HTTPException(status_code=404, detail="未找到相关推荐")

        return BaseResponse(
            code=200,
            message="推荐成功",
            data={
                "suggestions": suggestions,
                "total": len(suggestions),
                "processing_time": round(time.time() - start_time, 2),
            },
            timestamp=datetime.utcnow(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"推荐失败: {exc}")
        raise HTTPException(status_code=500, detail=f"推荐失败: {exc}")


@router.get("/documents/{document_id}/similar", summary="相关文档推荐")
async def get_similar_documents(
    document_id: str,
    limit: int = Query(5, ge=1, le=20, description="返回数量"),
    min_similarity: float = Query(0.6, ge=0.0, le=1.0, description="最小相似度阈值"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        degradation = resilience_manager.evaluate_degradation()
        flags = degradation.get("flags", {})
        if not flags.get("documentRecommendationEnabled", True):
            raise HTTPException(status_code=503, detail="系统降级中，文档推荐功能暂不可用")

        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="未认证用户")

        doc = await _get_user_document(db, document_id, user_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在或无权访问")

        recommendation_service = get_recommendation_service(
            embedding_service=EmbeddingService(),
            vector_store=None,
            cache_service=cache_service,
            db_session=db,
        )

        start_time = time.time()
        result = await recommendation_service.suggest_similar_documents(
            document_id=document_id,
            limit=limit,
            min_similarity=min_similarity,
        )
        result["processing_time"] = round(time.time() - start_time, 2)

        return BaseResponse(
            code=200,
            message="推荐成功",
            data=result,
            timestamp=datetime.utcnow(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"相关文档推荐失败: {exc}")
        raise HTTPException(status_code=500, detail=f"推荐失败: {exc}")
