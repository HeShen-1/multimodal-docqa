from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TagBase(BaseModel):
    """标签基础模型"""
    name: str = Field(..., min_length=1, max_length=50, description="标签名称")
    color: Optional[str] = Field("#3B82F6", pattern="^#[0-9A-Fa-f]{6}$", description="标签颜色")
    description: Optional[str] = Field(None, max_length=200, description="标签描述")


class TagCreate(TagBase):
    """创建标签请求"""
    pass


class TagUpdate(BaseModel):
    """更新标签请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    description: Optional[str] = Field(None, max_length=200)


class TagResponse(TagBase):
    """标签响应"""
    id: str = Field(..., description="标签ID")
    usage_count: int = Field(..., alias="usageCount", description="使用次数")
    created_at: datetime = Field(..., alias="createdAt", description="创建时间")
    updated_at: datetime = Field(..., alias="updatedAt", description="更新时间")
    
    class Config:
        populate_by_name = True
        from_attributes = True


class DocumentTagRequest(BaseModel):
    """文档标签操作请求"""
    tag_ids: list[str] = Field(..., alias="tagIds", description="标签ID列表")
    
    class Config:
        populate_by_name = True

