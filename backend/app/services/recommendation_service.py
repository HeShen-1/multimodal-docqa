"""
推荐服务

提供相似问题推荐和相关文档推荐。
"""
from typing import Any, Dict, List, Optional
import hashlib

import numpy as np
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentStatus
from app.models.document_db import Document
from app.models.query_history import QueryHistory


class RecommendationService:
    """推荐服务"""

    def __init__(
        self,
        embedding_service,
        vector_store,
        cache_service,
        db_session: AsyncSession,
    ):
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.cache_service = cache_service
        self.db = db_session

    async def suggest_questions(
        self,
        question: Optional[str] = None,
        document_id: Optional[str] = None,
        limit: int = 5,
        min_similarity: float = 0.7,
    ) -> List[Dict[str, Any]]:
        cache_key = self._generate_cache_key(
            "question", question, document_id, limit, min_similarity
        )
        cached_result = await self.cache_service.get(cache_key)
        if cached_result:
            return cached_result

        if question:
            suggestions = await self._suggest_by_similarity(
                question, document_id, limit * 2, min_similarity
            )
        else:
            suggestions = await self._suggest_by_popularity(document_id, limit * 2)

        filtered = self._filter_suggestions(suggestions, min_similarity)
        ranked = self._rank_suggestions(filtered, limit)

        await self.cache_service.set(cache_key, ranked, ttl=1800)
        return ranked

    async def _suggest_by_similarity(
        self,
        question: str,
        document_id: Optional[str],
        limit: int,
        min_similarity: float,
    ) -> List[Dict[str, Any]]:
        query_embedding = np.array(await self.embedding_service.embed_query(question), dtype=float)

        stmt = select(QueryHistory)
        if document_id:
            stmt = stmt.where(QueryHistory.document_id == document_id)
        stmt = stmt.order_by(QueryHistory.created_at.desc()).limit(1000)

        rows = (await self.db.execute(stmt)).scalars().all()

        suggestions: List[Dict[str, Any]] = []
        for row in rows:
            if row.question_embedding is None:
                continue

            history_embedding = np.array(row.question_embedding, dtype=float)
            if history_embedding.shape != query_embedding.shape:
                continue

            similarity = self._cosine_similarity(query_embedding, history_embedding)
            if similarity < min_similarity:
                continue

            suggestions.append(
                {
                    "question": row.question,
                    "similarity": float(similarity),
                    "query_count": row.query_count,
                    "last_queried": row.last_queried.isoformat() if row.last_queried else None,
                    "document_id": str(row.document_id) if row.document_id else None,
                    "document_name": row.document_name,
                }
            )

        suggestions.sort(key=lambda item: item["similarity"], reverse=True)
        return suggestions[:limit]

    async def _suggest_by_popularity(
        self, document_id: Optional[str], limit: int
    ) -> List[Dict[str, Any]]:
        stmt = select(QueryHistory)
        if document_id:
            stmt = stmt.where(QueryHistory.document_id == document_id)
        stmt = stmt.order_by(QueryHistory.query_count.desc()).limit(limit)

        rows = (await self.db.execute(stmt)).scalars().all()
        return [
            {
                "question": row.question,
                "similarity": 1.0,
                "query_count": row.query_count,
                "last_queried": row.last_queried.isoformat() if row.last_queried else None,
                "document_id": str(row.document_id) if row.document_id else None,
                "document_name": row.document_name,
            }
            for row in rows
        ]

    def _filter_suggestions(
        self, suggestions: List[Dict[str, Any]], min_similarity: float
    ) -> List[Dict[str, Any]]:
        filtered: List[Dict[str, Any]] = []
        seen_questions = set()

        for suggestion in suggestions:
            question = suggestion.get("question", "")
            if not question or question in seen_questions:
                continue
            if len(question) < 2:
                continue
            if suggestion.get("similarity", 0.0) < min_similarity:
                continue

            seen_questions.add(question)
            filtered.append(suggestion)

        return filtered

    def _rank_suggestions(
        self, suggestions: List[Dict[str, Any]], limit: int
    ) -> List[Dict[str, Any]]:
        for suggestion in suggestions:
            similarity_score = float(suggestion.get("similarity", 0.0))
            popularity_score = np.log1p(int(suggestion.get("query_count", 0))) / 10
            suggestion["final_score"] = 0.7 * similarity_score + 0.3 * popularity_score

        suggestions.sort(key=lambda item: item["final_score"], reverse=True)
        return suggestions[:limit]

    async def suggest_similar_documents(
        self,
        document_id: str,
        limit: int = 5,
        min_similarity: float = 0.6,
    ) -> Dict[str, Any]:
        cache_key = f"similar_docs:{document_id}:{limit}:{min_similarity}"
        cached_result = await self.cache_service.get(cache_key)
        if cached_result:
            return cached_result

        source_stmt = select(Document).where(Document.id == document_id)
        source_doc = (await self.db.execute(source_stmt)).scalar_one_or_none()
        if source_doc is None:
            raise ValueError(f"Document {document_id} not found")

        source_embedding = await self._get_document_embedding(document_id)
        if source_embedding is None:
            return {
                "source_document": {
                    "id": source_doc.id,
                    "name": source_doc.file_name,
                    "upload_time": source_doc.created_at.isoformat(),
                },
                "similar_documents": [],
                "total": 0,
            }

        target_stmt = select(Document).where(
            Document.id != document_id,
            Document.status == DocumentStatus.COMPLETED,
        )
        target_docs = (await self.db.execute(target_stmt)).scalars().all()

        similar_documents = []
        for doc in target_docs:
            doc_embedding = await self._get_document_embedding(doc.id)
            if doc_embedding is None:
                continue

            similarity = self._cosine_similarity(source_embedding, doc_embedding)
            if similarity < min_similarity:
                continue

            similar_documents.append(
                {
                    "id": doc.id,
                    "name": doc.file_name,
                    "similarity": float(similarity),
                    "common_topics": [],
                    "upload_time": doc.created_at.isoformat(),
                    "file_size": doc.file_size,
                    "page_count": doc.page_count,
                }
            )

        similar_documents.sort(key=lambda item: item["similarity"], reverse=True)

        result = {
            "source_document": {
                "id": source_doc.id,
                "name": source_doc.file_name,
                "upload_time": source_doc.created_at.isoformat(),
            },
            "similar_documents": similar_documents[:limit],
            "total": len(similar_documents),
        }

        await self.cache_service.set(cache_key, result, ttl=3600)
        return result

    async def _get_document_embedding(self, document_id: str) -> Optional[np.ndarray]:
        if self.vector_store is None:
            return None

        try:
            results = self.vector_store.get(where={"document_id": document_id})
            if not results or not results.get("embeddings"):
                return None

            embeddings = np.array(results["embeddings"], dtype=float)
            return np.mean(embeddings, axis=0)
        except Exception as exc:
            logger.error(f"获取文档向量失败 {document_id}: {exc}")
            return None

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    @staticmethod
    def _generate_cache_key(
        prefix: str,
        question: Optional[str],
        document_id: Optional[str],
        limit: int,
        min_similarity: float,
    ) -> str:
        key = "|".join(
            [
                prefix,
                question or "none",
                document_id or "all",
                str(limit),
                str(min_similarity),
            ]
        )
        return f"recommend:{hashlib.md5(key.encode()).hexdigest()}"


def get_recommendation_service(
    embedding_service,
    vector_store,
    cache_service,
    db_session: AsyncSession,
) -> RecommendationService:
    return RecommendationService(
        embedding_service=embedding_service,
        vector_store=vector_store,
        cache_service=cache_service,
        db_session=db_session,
    )
