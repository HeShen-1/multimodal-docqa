from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, get_document_processor, get_embedding_service
from app.models.document import DocumentStatus
from app.models.response import ApiResponse
from app.models.user import User
from app.schemas.document import BatchStatusResponse
from app.schemas.tag import DocumentTagRequest
from app.services.document_route_service import (
    batch_upload_documents as process_batch_upload_documents,
    build_document_status_payload,
    build_preview_text,
    delete_document_from_db,
    get_document_db_record,
    list_documents_from_db,
    serialize_document_record,
    upload_document as process_upload_document,
)
from app.services.tag_service import tag_service
from app.utils.exceptions import DocumentNotFoundError
from app.utils.helpers import build_pagination_response

if TYPE_CHECKING:
    from app.services.document_processor import DocumentProcessor
    from app.services.embedding_service import EmbeddingService


router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=ApiResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    description: Optional[str] = None,
    processor: DocumentProcessor = Depends(get_document_processor),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await process_upload_document(
        file=file,
        description=description,
        processor=processor,
        embedding_service=embedding_service,
        db=db,
        current_user=current_user,
    )


@router.get("", response_model=ApiResponse)
async def get_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100, alias="pageSize"),
    status: Optional[DocumentStatus] = None,
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = await list_documents_from_db(
        db=db,
        current_user=current_user,
        page=page,
        page_size=page_size,
        status=status,
        keyword=keyword,
    )
    return ApiResponse(
        code=100000,
        message="success",
        data=build_pagination_response(items, total, page, page_size),
    )


@router.get("/{document_id}", response_model=ApiResponse)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
):
    document = await get_document_db_record(db, document_id, current_user)
    doc = serialize_document_record(document)
    chunks = await embedding_service.get_document_chunks(document_id)
    doc["previewText"] = build_preview_text(chunks)
    return ApiResponse(code=100000, message="success", data=doc)


@router.get("/{document_id}/chunks", response_model=ApiResponse)
async def get_document_chunks(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
):
    await get_document_db_record(db, document_id, current_user)
    chunks = await embedding_service.get_document_chunks(document_id)
    return ApiResponse(code=100000, message="success", data=chunks)


@router.get("/{document_id}/file")
async def get_document_file(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = await get_document_db_record(db, document_id, current_user)
    file_path = Path(document.file_path)
    if not file_path.exists():
        raise DocumentNotFoundError(document_id)

    media_type = mimetypes.guess_type(document.file_name)[0] or "application/octet-stream"
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=document.file_name,
    )


@router.delete("/{document_id}", response_model=ApiResponse)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
):
    await delete_document_from_db(
        db=db,
        document_id=document_id,
        current_user=current_user,
        embedding_service=embedding_service,
    )
    return ApiResponse(code=100000, message="删除成功", data=None)


@router.get("/{document_id}/status", response_model=ApiResponse)
async def get_document_status(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = await get_document_db_record(db, document_id, current_user)
    return ApiResponse(
        code=100000,
        message="success",
        data=build_document_status_payload(document),
    )


@router.post("/batch-upload", response_model=ApiResponse, status_code=201)
async def batch_upload_documents(
    files: List[UploadFile] = File(...),
    description: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    del description
    return await process_batch_upload_documents(files=files, current_user=current_user)


@router.get("/batch/{batch_id}/status", response_model=ApiResponse)
async def get_batch_status(
    batch_id: str,
    current_user: User = Depends(get_current_user),
):
    del current_user
    from app.services.batch_upload_service import batch_upload_service

    status = batch_upload_service.get_batch_status(batch_id)
    if not status:
        raise HTTPException(status_code=404, detail="批次不存在")
    return ApiResponse(code=100000, message="success", data=BatchStatusResponse(**status))


@router.post("/{document_id}/tags", response_model=ApiResponse)
async def add_document_tags(
    document_id: str,
    tag_request: DocumentTagRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await get_document_db_record(db, document_id, current_user)
        await tag_service.add_tags_to_document(db, document_id, tag_request.tag_ids)
        tags = await tag_service.get_document_tags(db, document_id)
        return ApiResponse(
            code=100000,
            message="添加成功",
            data=[{"id": tag.id, "name": tag.name, "color": tag.color} for tag in tags],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{document_id}/tags", response_model=ApiResponse)
async def remove_document_tags(
    document_id: str,
    tag_request: DocumentTagRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await get_document_db_record(db, document_id, current_user)
        await tag_service.remove_tags_from_document(db, document_id, tag_request.tag_ids)
        tags = await tag_service.get_document_tags(db, document_id)
        return ApiResponse(
            code=100000,
            message="移除成功",
            data=[{"id": tag.id, "name": tag.name, "color": tag.color} for tag in tags],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{document_id}/tags", response_model=ApiResponse)
async def get_document_tags(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_document_db_record(db, document_id, current_user)
    tags = await tag_service.get_document_tags(db, document_id)
    return ApiResponse(
        code=100000,
        message="success",
        data=[{"id": tag.id, "name": tag.name, "color": tag.color} for tag in tags],
    )
