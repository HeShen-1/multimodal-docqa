from pydantic import BaseModel, Field
from typing import Optional, Any, List, Dict
from datetime import datetime


class ApiResponse(BaseModel):
    """统一API响应格式"""
    code: int = Field(..., description="业务状态码")
    message: str = Field(..., description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ErrorDetail(BaseModel):
    """错误详情"""
    field: str = Field(..., description="错误字段")
    message: str = Field(..., description="错误消息")


class ErrorResponse(BaseModel):
    """错误响应"""
    code: int = Field(..., description="错误码")
    message: str = Field(..., description="错误消息")
    errors: Optional[List[ErrorDetail]] = Field(None, description="错误详情列表")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="版本号")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    services: Dict[str, str] = Field(..., description="各服务状态")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class StatsResponse(BaseModel):
    """统计信息响应"""
    total_documents: int = Field(..., alias="totalDocuments", description="文档总数")
    total_queries: int = Field(..., alias="totalQueries", description="查询总数")
    total_chunks: int = Field(..., alias="totalChunks", description="分块总数")
    total_images: int = Field(..., alias="totalImages", description="图像总数")
    avg_processing_time: float = Field(..., alias="avgProcessingTime", description="平均处理时间")
    avg_query_time: float = Field(..., alias="avgQueryTime", description="平均查询时间")
    storage_used: str = Field(..., alias="storageUsed", description="存储使用量")
    uptime: int = Field(..., description="运行时间（秒）")
    
    class Config:
        populate_by_name = True

