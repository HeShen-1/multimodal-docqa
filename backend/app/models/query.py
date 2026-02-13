from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class QueryRequest(BaseModel):
    """查询请求"""
    question: str = Field(..., min_length=1, max_length=500, description="用户问题")
    top_k: int = Field(5, alias="topK", ge=1, le=20, description="检索返回数量")
    enable_thinking: bool = Field(True, alias="enableThinking", description="是否启用推理链")
    document_ids: List[str] = Field(default_factory=list, alias="documentIds", description="指定文档ID列表")
    temperature: float = Field(0.7, ge=0.0, le=1.0, description="生成温度")
    
    class Config:
        populate_by_name = True


class ThinkingStep(BaseModel):
    """推理步骤"""
    step: str = Field(..., description="步骤名称")
    content: str = Field(..., description="步骤内容")


class Source(BaseModel):
    """参考来源"""
    file_name: str = Field(..., alias="fileName", description="文件名")
    page: int = Field(..., description="页码")
    chunk_id: Optional[str] = Field(None, alias="chunkId", description="分块ID")
    content: Optional[str] = Field(None, description="内容片段")
    relevance_score: Optional[float] = Field(None, alias="relevanceScore", description="相关性分数")
    
    class Config:
        populate_by_name = True


class QueryResponse(BaseModel):
    """查询响应"""
    answer: str = Field(..., description="回答内容")
    thinking: Optional[List[ThinkingStep]] = Field(None, description="推理链")
    sources: List[Source] = Field(..., description="参考来源")
    processing_time: float = Field(..., alias="processingTime", description="处理时间（秒）")
    retrieval_stats: Optional[Dict[str, Any]] = Field(None, alias="retrievalStats", description="检索统计")
    
    class Config:
        populate_by_name = True


class QueryHistoryItem(BaseModel):
    """查询历史项"""
    id: str = Field(..., description="查询ID")
    question: str = Field(..., description="问题")
    answer: str = Field(..., description="答案")
    document_ids: List[str] = Field(..., alias="documentIds", description="文档ID列表")
    processing_time: float = Field(..., alias="processingTime", description="处理时间")
    created_at: datetime = Field(..., alias="createdAt", description="创建时间")
    
    class Config:
        populate_by_name = True


class QueryHistoryResponse(BaseModel):
    """查询历史响应"""
    items: List[QueryHistoryItem] = Field(..., description="历史记录列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., alias="pageSize", description="每页数量")
    total_pages: int = Field(..., alias="totalPages", description="总页数")
    
    class Config:
        populate_by_name = True

