from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.document import DocumentStatus


class BatchUploadResponse(BaseModel):
    """批量上传响应"""
    batch_id: str = Field(..., alias="batchId", description="批次ID")
    total_files: int = Field(..., alias="totalFiles", description="总文件数")
    accepted_files: int = Field(..., alias="acceptedFiles", description="接受的文件数")
    rejected_files: List[dict] = Field(..., alias="rejectedFiles", description="拒绝的文件列表")
    document_ids: List[str] = Field(..., alias="documentIds", description="文档ID列表")
    
    class Config:
        populate_by_name = True


class BatchStatusResponse(BaseModel):
    """批量上传状态响应"""
    batch_id: str = Field(..., alias="batchId", description="批次ID")
    total_files: int = Field(..., alias="totalFiles", description="总文件数")
    completed: int = Field(..., description="已完成")
    processing: int = Field(..., description="处理中")
    failed: int = Field(..., description="失败")
    progress: int = Field(..., ge=0, le=100, description="总体进度")
    documents: List[dict] = Field(..., description="文档状态列表")
    
    class Config:
        populate_by_name = True


class DocumentWithTags(BaseModel):
    """带标签的文档响应"""
    id: str = Field(..., description="文档ID")
    file_name: str = Field(..., alias="fileName", description="文件名")
    file_type: str = Field(..., alias="fileType", description="文件类型")
    file_size: int = Field(..., alias="fileSize", description="文件大小")
    status: DocumentStatus = Field(..., description="处理状态")
    description: Optional[str] = Field(None, description="文档描述")
    tags: List[dict] = Field(default_factory=list, description="标签列表")
    created_at: datetime = Field(..., alias="createdAt", description="创建时间")
    updated_at: datetime = Field(..., alias="updatedAt", description="更新时间")
    
    class Config:
        populate_by_name = True
        from_attributes = True

