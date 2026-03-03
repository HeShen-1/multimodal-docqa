from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ShareLinkCreate(BaseModel):
    """创建分享链接请求"""
    expires_in_hours: int = Field(24, ge=1, le=168, alias="expiresInHours", description="过期时间（小时），1-168小时")
    password: Optional[str] = Field(None, min_length=4, max_length=20, description="访问密码（可选）")
    allow_download: bool = Field(True, alias="allowDownload", description="是否允许下载")
    max_access_count: Optional[int] = Field(None, ge=1, alias="maxAccessCount", description="最大访问次数（可选）")
    
    class Config:
        populate_by_name = True


class ShareLinkResponse(BaseModel):
    """分享链接响应"""
    id: str = Field(..., description="分享ID")
    document_id: str = Field(..., alias="documentId", description="文档ID")
    token: str = Field(..., description="分享Token")
    share_url: str = Field(..., alias="shareUrl", description="分享链接")
    has_password: bool = Field(..., alias="hasPassword", description="是否设置密码")
    allow_download: bool = Field(..., alias="allowDownload", description="是否允许下载")
    expires_at: datetime = Field(..., alias="expiresAt", description="过期时间")
    access_count: int = Field(..., alias="accessCount", description="访问次数")
    max_access_count: Optional[int] = Field(None, alias="maxAccessCount", description="最大访问次数")
    created_at: datetime = Field(..., alias="createdAt", description="创建时间")
    
    class Config:
        populate_by_name = True
        from_attributes = True


class ShareAccessRequest(BaseModel):
    """访问分享链接请求"""
    password: Optional[str] = Field(None, description="访问密码")


class ShareAccessResponse(BaseModel):
    """访问分享链接响应"""
    document_id: str = Field(..., alias="documentId", description="文档ID")
    file_name: str = Field(..., alias="fileName", description="文件名")
    file_size: int = Field(..., alias="fileSize", description="文件大小")
    allow_download: bool = Field(..., alias="allowDownload", description="是否允许下载")
    
    class Config:
        populate_by_name = True

