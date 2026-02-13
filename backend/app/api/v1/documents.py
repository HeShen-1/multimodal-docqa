from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from typing import Optional, List
from pathlib import Path
import shutil
import time
from datetime import datetime
from loguru import logger

from app.models.document import (
    DocumentResponse, 
    DocumentListResponse, 
    DocumentDetailResponse,
    DocumentStatusResponse,
    DocumentStatus
)
from app.models.response import ApiResponse
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import EmbeddingService
from app.dependencies import get_document_processor, get_embedding_service
from app.utils.exceptions import (
    UnsupportedFileTypeError, 
    FileSizeExceededError,
    DocumentNotFoundError
)
from app.utils.helpers import generate_uuid, build_pagination_response
from app.config import get_settings

router = APIRouter(prefix="/documents", tags=["documents"])

# 临时存储文档状态（生产环境应使用数据库）
documents_db = {}
processing_status = {}


@router.post("/upload", response_model=ApiResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    description: Optional[str] = None,
    processor: DocumentProcessor = Depends(get_document_processor),
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """上传文档"""
    settings = get_settings()
    
    # 验证文件类型
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.allowed_file_types:
        raise UnsupportedFileTypeError(file_ext)
    
    # 验证文件大小
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > settings.max_file_size:
        raise FileSizeExceededError(settings.max_file_size)
    
    # 生成文档ID
    document_id = generate_uuid()
    
    # 生成文件名：原文件名（不含扩展名）+ 日期 + UUID
    original_name = Path(file.filename).stem
    date_str = datetime.now().strftime("%Y%m%d")
    new_filename = f"{original_name}_{date_str}_{document_id}{file_ext}"
    
    # 保存文件
    upload_dir = Path("./data/documents")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = upload_dir / new_filename
    
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    logger.info(f"文档上传成功: {file.filename} -> {document_id}")
    
    # 创建文档记录
    doc_record = {
        "id": document_id,
        "fileName": file.filename,
        "fileType": file.content_type,
        "fileSize": file_size,
        "status": DocumentStatus.PROCESSING,
        "description": description,
        "pageCount": None,
        "chunkCount": None,
        "imageCount": None,
        "metadata": {},
        "createdAt": time.time(),
        "updatedAt": time.time()
    }
    
    documents_db[document_id] = doc_record
    
    # 异步处理文档（这里简化为同步，生产环境应使用后台任务）
    try:
        processing_status[document_id] = {
            "status": DocumentStatus.PROCESSING,
            "progress": 0,
            "currentStep": "文档解析",
            "message": "正在解析文档..."
        }
        
        # 处理文档
        result = await processor.process_document(file_path)
        
        processing_status[document_id]["progress"] = 50
        processing_status[document_id]["currentStep"] = "向量化"
        processing_status[document_id]["message"] = "正在生成向量..."
        
        # 向量化并存储
        await embedding_service.add_text_chunks(
            document_id=document_id,
            chunks=result["text_chunks"]
        )
        
        # 更新文档记录
        doc_record["status"] = DocumentStatus.COMPLETED
        doc_record["pageCount"] = result["page_count"]
        doc_record["chunkCount"] = result["metadata"]["chunk_count"]
        doc_record["imageCount"] = result["metadata"]["image_count"]
        doc_record["updatedAt"] = time.time()
        
        processing_status[document_id] = {
            "status": DocumentStatus.COMPLETED,
            "progress": 100,
            "currentStep": "完成",
            "message": "处理完成"
        }
        
        logger.info(f"文档处理完成: {document_id}")
        
    except Exception as e:
        logger.error(f"文档处理失败: {e}")
        doc_record["status"] = DocumentStatus.FAILED
        processing_status[document_id] = {
            "status": DocumentStatus.FAILED,
            "progress": 0,
            "currentStep": "失败",
            "message": str(e)
        }
    
    return ApiResponse(
        code=100000,
        message="上传成功",
        data={
            "documentId": document_id,
            "fileName": file.filename,
            "fileSize": file_size,
            "status": doc_record["status"],
            "createdAt": doc_record["createdAt"]
        }
    )


@router.get("", response_model=ApiResponse)
async def get_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100, alias="pageSize"),
    status: Optional[DocumentStatus] = None,
    keyword: Optional[str] = None
):
    """获取文档列表"""
    # 过滤文档
    filtered_docs = list(documents_db.values())
    
    if status:
        filtered_docs = [d for d in filtered_docs if d["status"] == status]
    
    if keyword:
        filtered_docs = [
            d for d in filtered_docs 
            if keyword.lower() in d["fileName"].lower()
        ]
    
    # 排序
    filtered_docs.sort(key=lambda x: x["createdAt"], reverse=True)
    
    # 分页
    total = len(filtered_docs)
    start = (page - 1) * page_size
    end = start + page_size
    items = filtered_docs[start:end]
    
    return ApiResponse(
        code=100000,
        message="success",
        data=build_pagination_response(items, total, page, page_size)
    )


@router.get("/{document_id}", response_model=ApiResponse)
async def get_document(document_id: str):
    """获取文档详情"""
    if document_id not in documents_db:
        raise DocumentNotFoundError(document_id)
    
    doc = documents_db[document_id]
    
    return ApiResponse(
        code=100000,
        message="success",
        data=doc
    )


@router.delete("/{document_id}", response_model=ApiResponse)
async def delete_document(
    document_id: str,
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """删除文档"""
    if document_id not in documents_db:
        raise DocumentNotFoundError(document_id)
    
    # 删除向量
    await embedding_service.delete_document_chunks(document_id)
    
    # 删除文件（需要查找匹配的文件）
    doc = documents_db[document_id]
    upload_dir = Path("./data/documents")
    
    # 查找包含document_id的文件
    for file_path in upload_dir.glob(f"*{document_id}*"):
        if file_path.is_file():
            file_path.unlink()
            break
    
    # 删除记录
    del documents_db[document_id]
    if document_id in processing_status:
        del processing_status[document_id]
    
    logger.info(f"文档删除成功: {document_id}")
    
    return ApiResponse(
        code=100000,
        message="删除成功",
        data=None
    )


@router.get("/{document_id}/status", response_model=ApiResponse)
async def get_document_status(document_id: str):
    """获取文档处理状态"""
    if document_id not in documents_db:
        raise DocumentNotFoundError(document_id)
    
    status = processing_status.get(document_id, {
        "status": DocumentStatus.COMPLETED,
        "progress": 100,
        "currentStep": "完成",
        "message": "处理完成"
    })
    
    return ApiResponse(
        code=100000,
        message="success",
        data={
            "documentId": document_id,
            **status
        }
    )

