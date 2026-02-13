from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class DocumentStatus(str, Enum):
    """文档处理状态"""
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentUploadRequest(BaseModel):
    """文档上传请求"""
    description: Optional[str] = Field(None, max_length=500, description="文档描述")


class DocumentResponse(BaseModel):
    """文档响应"""
    id: str = Field(..., description="文档ID")
    file_name: str = Field(..., alias="fileName", description="文件名")
    file_type: str = Field(..., alias="fileType", description="文件类型")
    file_size: int = Field(..., alias="fileSize", description="文件大小（字节）")
    status: DocumentStatus = Field(..., description="处理状态")
    description: Optional[str] = Field(None, description="文档描述")
    page_count: Optional[int] = Field(None, alias="pageCount", description="页数")
    chunk_count: Optional[int] = Field(None, alias="chunkCount", description="分块数量")
    image_count: Optional[int] = Field(None, alias="imageCount", description="图像数量")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    created_at: datetime = Field(..., alias="createdAt", description="创建时间")
    updated_at: datetime = Field(..., alias="updatedAt", description="更新时间")
    
    class Config:
        populate_by_name = True


class DocumentDetailResponse(DocumentResponse):
    """文档详情响应"""
    processing_log: Optional[List[Dict[str, Any]]] = Field(None, alias="processingLog", description="处理日志")


class DocumentStatusResponse(BaseModel):
    """文档处理状态响应"""
    document_id: str = Field(..., alias="documentId", description="文档ID")
    status: DocumentStatus = Field(..., description="处理状态")
    progress: int = Field(..., ge=0, le=100, description="进度百分比")
    current_step: str = Field(..., alias="currentStep", description="当前步骤")
    estimated_time_remaining: Optional[int] = Field(None, alias="estimatedTimeRemaining", description="预计剩余时间（秒）")
    message: str = Field(..., description="状态消息")
    
    class Config:
        populate_by_name = True


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    items: List[DocumentResponse] = Field(..., description="文档列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., alias="pageSize", description="每页数量")
    total_pages: int = Field(..., alias="totalPages", description="总页数")
    
    class Config:
        populate_by_name = True

