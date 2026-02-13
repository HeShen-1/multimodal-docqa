from fastapi import Depends
from typing import Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_service import RetrievalService
from app.services.llm_service import LLMService
from app.config import Settings, get_settings


# 数据库引擎
_engine = None
_async_session_maker = None


def get_engine():
    """获取数据库引擎"""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_size=20,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=3600
        )
    return _engine


def get_session_maker():
    """获取会话工厂"""
    global _async_session_maker
    if _async_session_maker is None:
        engine = get_engine()
        _async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    return _async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


# 服务实例缓存
_document_processor: Optional[DocumentProcessor] = None
_embedding_service: Optional[EmbeddingService] = None
_retrieval_service: Optional[RetrievalService] = None
_llm_service: Optional[LLMService] = None


def get_document_processor() -> DocumentProcessor:
    """获取文档处理服务"""
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor()
    return _document_processor


def get_embedding_service(
    settings: Settings = Depends(get_settings)
) -> EmbeddingService:
    """获取向量化服务"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(settings)
    return _embedding_service


def get_retrieval_service(
    embedding_service: EmbeddingService = Depends(get_embedding_service)
) -> RetrievalService:
    """获取检索服务"""
    global _retrieval_service
    if _retrieval_service is None:
        _retrieval_service = RetrievalService(embedding_service)
    return _retrieval_service


def get_llm_service(
    settings: Settings = Depends(get_settings)
) -> LLMService:
    """获取LLM服务"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService(settings)
    return _llm_service

