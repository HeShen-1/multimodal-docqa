from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from fastapi import HTTPException, UploadFile
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.document import DocumentStatus
from app.models.document_db import Document as DocumentDB
from app.models.response import ApiResponse
from app.models.user import User
from app.schemas.document import BatchUploadResponse
from app.services.resilience_service import resilience_manager
from app.utils.exceptions import DocumentNotFoundError, FileSizeExceededError, UnsupportedFileTypeError
from app.utils.helpers import generate_uuid

if TYPE_CHECKING:
    from app.services.document_processor import DocumentProcessor
    from app.services.embedding_service import EmbeddingService

documents_db: Dict[str, dict] = {}
processing_status: Dict[str, dict] = {}


def resolve_current_user_id(current_user) -> str:
    """兼容 dict / ORM User 两种 current_user 形态。"""
    if isinstance(current_user, dict):
        user_id = current_user.get("user_id") or current_user.get("id")
    else:
        user_id = getattr(current_user, "id", None)

    if user_id is None:
        raise HTTPException(status_code=401, detail="无法识别当前用户")
    return str(user_id)


def resolve_upload_file_ext(file: UploadFile, allowed_file_types: List[str]) -> str:
    """根据扩展名或 MIME 类型解析并校验文件类型。"""
    file_name = file.filename or ""
    file_ext = Path(file_name).suffix.lower()
    if file_ext in allowed_file_types:
        return file_ext

    content_type = (file.content_type or "").lower()
    mime_to_ext = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "text/plain": ".txt",
        "text/markdown": ".md",
        "text/x-markdown": ".md",
        "text/csv": ".csv",
        "application/csv": ".csv",
        "text/tab-separated-values": ".tsv",
        "application/json": ".json",
        "application/x-ndjson": ".jsonl",
        "text/html": ".html",
        "application/xhtml+xml": ".html",
        "application/xml": ".xml",
        "text/xml": ".xml",
        "application/yaml": ".yaml",
        "text/yaml": ".yaml",
        "application/x-yaml": ".yaml",
        "text/x-yaml": ".yaml",
    }
    inferred_ext = mime_to_ext.get(content_type)
    if inferred_ext and inferred_ext in allowed_file_types:
        if not file_ext:
            logger.warning(
                f"文件缺少扩展名，按 content_type 推断类型: file_name={file_name}, content_type={content_type}, inferred_ext={inferred_ext}"
            )
        return inferred_ext

    if not file_ext and content_type.startswith("text/") and ".txt" in allowed_file_types:
        logger.warning(f"文件缺少扩展名，且 content_type={content_type}，按文本类型回退为 .txt")
        return ".txt"

    raise UnsupportedFileTypeError(file_ext or content_type or "unknown", allowed_file_types)


async def get_document_db_record(
    db: AsyncSession,
    document_id: str,
    current_user: User,
) -> DocumentDB:
    user_id = resolve_current_user_id(current_user)
    result = await db.execute(
        select(DocumentDB).where(
            DocumentDB.id == document_id,
            DocumentDB.user_id == user_id,
        )
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise DocumentNotFoundError(document_id)
    return document


def build_preview_text(chunks: List[dict], limit: int = 1600) -> str:
    if not chunks:
        return ""

    parts: List[str] = []
    current_length = 0
    for chunk in chunks:
        content = str(chunk.get("content", "")).strip()
        if not content:
            continue
        remaining = limit - current_length
        if remaining <= 0:
            break
        snippet = content[:remaining]
        parts.append(snippet)
        current_length += len(snippet)
        if current_length >= limit:
            break
    return "\n\n".join(parts).strip()


def serialize_document_record(document: DocumentDB) -> dict:
    return {
        "id": document.id,
        "fileName": document.file_name,
        "fileType": document.file_type,
        "fileSize": document.file_size,
        "status": document.status,
        "description": document.description,
        "pageCount": document.page_count,
        "chunkCount": document.chunk_count,
        "imageCount": document.image_count,
        "metadata": document.doc_metadata or {},
        "createdAt": document.created_at,
        "updatedAt": document.updated_at,
    }


async def list_documents_from_db(
    db: AsyncSession,
    current_user: User,
    page: int,
    page_size: int,
    status: Optional[DocumentStatus] = None,
    keyword: Optional[str] = None,
) -> tuple[List[dict], int]:
    user_id = resolve_current_user_id(current_user)
    filters = [DocumentDB.user_id == user_id]

    if status:
        filters.append(DocumentDB.status == status)

    if keyword:
        keyword_like = f"%{keyword.strip()}%"
        filters.append(DocumentDB.file_name.ilike(keyword_like))

    total_result = await db.execute(
        select(func.count(DocumentDB.id)).where(*filters)
    )
    total = int(total_result.scalar() or 0)

    result = await db.execute(
        select(DocumentDB)
        .where(*filters)
        .order_by(DocumentDB.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    documents = result.scalars().all()
    return [serialize_document_record(document) for document in documents], total


def build_document_status_payload(document: DocumentDB) -> dict:
    document_status = document.status
    if isinstance(document_status, str):
        try:
            document_status = DocumentStatus(document_status)
        except ValueError:
            document_status = DocumentStatus.PROCESSING

    cached_status = processing_status.get(document.id)
    if cached_status:
        payload = dict(cached_status)
        payload["status"] = payload.get("status", document_status)
        return {
            "documentId": document.id,
            **payload,
        }

    default_payload = {
        DocumentStatus.PROCESSING: {
            "status": DocumentStatus.PROCESSING,
            "progress": 0,
            "currentStep": "处理中",
            "message": "文档正在处理中",
        },
        DocumentStatus.COMPLETED: {
            "status": DocumentStatus.COMPLETED,
            "progress": 100,
            "currentStep": "完成",
            "message": "文档处理完成",
        },
        DocumentStatus.FAILED: {
            "status": DocumentStatus.FAILED,
            "progress": 100,
            "currentStep": "失败",
            "message": "文档处理失败",
        },
    }
    payload = default_payload.get(document_status, default_payload[DocumentStatus.PROCESSING]).copy()
    metadata = document.doc_metadata or {}
    if document_status == DocumentStatus.FAILED and metadata.get("error"):
        payload["message"] = str(metadata["error"])
    return {
        "documentId": document.id,
        **payload,
    }


async def delete_document_from_db(
    db: AsyncSession,
    document_id: str,
    current_user: User,
    embedding_service: EmbeddingService,
) -> None:
    document = await get_document_db_record(db, document_id, current_user)

    try:
        await embedding_service.delete_document_chunks(document_id)
    except Exception as exc:
        logger.warning(f"删除文档向量失败: document_id={document_id}, error={exc}")

    file_path = Path(document.file_path)
    if file_path.exists() and file_path.is_file():
        file_path.unlink()

    await db.delete(document)
    await db.commit()

    documents_db.pop(document_id, None)
    processing_status.pop(document_id, None)


async def get_shared_document_record(db: AsyncSession, document_id: str) -> Optional[DocumentDB]:
    result = await db.execute(select(DocumentDB).where(DocumentDB.id == document_id))
    return result.scalar_one_or_none()


async def upload_document(
    file: UploadFile,
    description: Optional[str],
    processor: DocumentProcessor,
    embedding_service: EmbeddingService,
    db: AsyncSession,
    current_user: User,
) -> ApiResponse:
    settings = get_settings()
    flags = resilience_manager.evaluate_degradation().get("flags", {})
    if flags.get("uploadLimited"):
        raise HTTPException(status_code=503, detail="系统重度降级中，暂时限制文档上传")

    file_ext = resolve_upload_file_ext(file, settings.allowed_file_types)

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > settings.max_file_size:
        raise FileSizeExceededError(settings.max_file_size)

    document_id = generate_uuid()
    source_file_name = file.filename or f"document{file_ext}"
    original_name = Path(source_file_name).stem or "document"
    date_str = datetime.now().strftime("%Y%m%d")
    new_filename = f"{original_name}_{date_str}_{document_id}{file_ext}"

    upload_dir = Path("./data/documents")
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / new_filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    logger.info(f"文档上传成功: {source_file_name} -> {document_id}")

    user_id = resolve_current_user_id(current_user)
    db_document = DocumentDB(
        id=document_id,
        user_id=user_id,
        file_name=source_file_name,
        file_path=str(file_path),
        file_type=file_ext,
        file_size=file_size,
        status="processing",
        description=description,
    )
    db.add(db_document)
    await db.commit()
    await db.refresh(db_document)

    doc_record = {
        "id": document_id,
        "fileName": source_file_name,
        "fileType": file.content_type,
        "fileSize": file_size,
        "status": DocumentStatus.PROCESSING,
        "description": description,
        "pageCount": None,
        "chunkCount": None,
        "imageCount": None,
        "metadata": {},
        "createdAt": time.time(),
        "updatedAt": time.time(),
    }

    documents_db[document_id] = doc_record

    try:
        processing_status[document_id] = {
            "status": DocumentStatus.PROCESSING,
            "progress": 0,
            "currentStep": "文档解析",
            "message": "正在解析文档...",
        }

        result = await processor.process_document(file_path)

        processing_status[document_id]["progress"] = 50
        processing_status[document_id]["currentStep"] = "向量化"
        processing_status[document_id]["message"] = "正在生成向量..."

        await embedding_service.add_text_chunks(
            document_id=document_id,
            chunks=result["text_chunks"],
        )

        doc_record["status"] = DocumentStatus.COMPLETED
        doc_record["pageCount"] = result["page_count"]
        doc_record["chunkCount"] = result["metadata"]["chunk_count"]
        doc_record["imageCount"] = result["metadata"]["image_count"]
        doc_record["metadata"] = result["metadata"]
        doc_record["updatedAt"] = time.time()

        db_document.status = "completed"
        db_document.page_count = result["page_count"]
        db_document.chunk_count = result["metadata"]["chunk_count"]
        db_document.image_count = result["metadata"]["image_count"]
        db_document.doc_metadata = result["metadata"]
        await db.commit()

        processing_status[document_id] = {
            "status": DocumentStatus.COMPLETED,
            "progress": 100,
            "currentStep": "完成",
            "message": "处理完成",
        }

        logger.info(f"文档处理完成: {document_id}")
    except Exception as exc:
        logger.error(f"文档处理失败: {exc}")
        doc_record["status"] = DocumentStatus.FAILED
        doc_record["metadata"] = {"error": str(exc)}

        db_document.status = "failed"
        db_document.doc_metadata = {"error": str(exc)}
        await db.commit()

        processing_status[document_id] = {
            "status": DocumentStatus.FAILED,
            "progress": 0,
            "currentStep": "失败",
            "message": str(exc),
        }

    return ApiResponse(
        code=100000,
        message="上传成功",
        data={
            "id": document_id,
            "documentId": document_id,
            "fileName": source_file_name,
            "fileSize": file_size,
            "status": doc_record["status"],
            "createdAt": doc_record["createdAt"],
        },
    )


async def batch_upload_documents(
    files: List[UploadFile],
    current_user: User,
) -> ApiResponse:
    from app.services.batch_upload_service import batch_upload_service

    settings = get_settings()
    flags = resilience_manager.evaluate_degradation().get("flags", {})
    if flags.get("uploadLimited"):
        raise HTTPException(status_code=503, detail="系统重度降级中，暂时限制批量上传")

    if len(files) > 10:
        raise HTTPException(status_code=400, detail="最多只能上传10个文件")

    if len(files) == 0:
        raise HTTPException(status_code=400, detail="至少上传1个文件")

    batch_id = batch_upload_service.create_batch(len(files))
    accepted_files = []
    rejected_files = []
    file_infos = []

    upload_dir = Path("./data/documents")
    upload_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        try:
            source_file_name = file.filename or "document"

            try:
                file_ext = resolve_upload_file_ext(file, settings.allowed_file_types)
            except UnsupportedFileTypeError as exc:
                rejected_files.append({"fileName": source_file_name, "reason": exc.detail})
                continue

            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)

            if file_size > settings.max_file_size:
                rejected_files.append(
                    {
                        "fileName": source_file_name,
                        "reason": f"文件大小超过限制: {file_size} > {settings.max_file_size}",
                    }
                )
                continue

            document_id = generate_uuid()
            original_name = Path(source_file_name).stem or "document"
            date_str = datetime.now().strftime("%Y%m%d")
            new_filename = f"{original_name}_{date_str}_{document_id}{file_ext}"
            file_path = upload_dir / new_filename

            with file_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            file_infos.append(
                {
                    "file_path": str(file_path),
                    "file_name": source_file_name,
                    "file_size": file_size,
                    "file_type": file.content_type,
                }
            )
            accepted_files.append(source_file_name)
            logger.info(f"批量上传: {source_file_name} -> {document_id}")
        except Exception as exc:
            source_file_name = file.filename or "document"
            logger.error(f"保存文件失败: {source_file_name}, 错误: {exc}")
            rejected_files.append({"fileName": source_file_name, "reason": str(exc)})

    user_id = resolve_current_user_id(current_user)
    document_ids = await batch_upload_service.process_batch(batch_id, file_infos, user_id)

    return ApiResponse(
        code=100000,
        message="批量上传成功",
        data=BatchUploadResponse(
            batch_id=batch_id,
            total_files=len(files),
            accepted_files=len(accepted_files),
            rejected_files=rejected_files,
            document_ids=document_ids,
        ),
    )
