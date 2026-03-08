"""
Phase 5 高级检索功能 - Pydantic Schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class MultiDocQueryRequest(BaseModel):
    """多文档查询请求"""
    question: str = Field(..., min_length=1, max_length=500, description="用户问题")
    document_ids: List[str] = Field(..., min_items=2, max_items=10, description="文档ID列表")
    top_k: int = Field(5, ge=1, le=20, description="每个文档返回结果数")
    fusion_method: str = Field("rrf", description="融合方法：rrf/weighted")
    enable_rerank: bool = Field(False, description="是否启用重排序")
    include_metadata: bool = Field(True, description="是否包含元数据")


class SearchResultSchema(BaseModel):
    """检索结果"""
    content: str = Field(..., description="文本内容")
    score: float = Field(..., description="相关性分数")
    document_id: str = Field(..., alias="documentId", description="文档ID")
    document_name: str = Field(..., alias="documentName", description="文档名称")
    page: Optional[int] = Field(None, description="页码")
    chunk_id: str = Field(..., alias="chunkId", description="块ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    
    class Config:
        populate_by_name = True


class DocumentStatsSchema(BaseModel):
    """文档统计信息"""
    name: str = Field(..., description="文档名称")
    matched_chunks: int = Field(..., alias="matchedChunks", description="匹配块数")
    avg_score: float = Field(..., alias="avgScore", description="平均分数")
    
    class Config:
        populate_by_name = True


class MultiDocQueryResponse(BaseModel):
    """多文档查询响应"""
    results: List[SearchResultSchema] = Field(..., description="检索结果列表")
    total: int = Field(..., description="总结果数")
    fusion_method: str = Field(..., alias="fusionMethod", description="融合方法")
    processing_time: float = Field(..., alias="processingTime", description="处理时间（秒）")
    document_stats: Dict[str, DocumentStatsSchema] = Field(..., alias="documentStats", description="文档统计")
    
    class Config:
        populate_by_name = True


class RerankCandidate(BaseModel):
    """重排序候选结果"""
    content: str = Field(..., description="文本内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class RerankRequest(BaseModel):
    """重排序请求"""
    question: str = Field(..., min_length=1, max_length=500, description="用户问题")
    candidates: List[RerankCandidate] = Field(..., min_items=1, max_items=100, description="候选结果列表")
    top_k: int = Field(5, ge=1, le=50, description="返回结果数")
    model: str = Field("bge-reranker-base", description="Rerank模型")


class RerankResultSchema(BaseModel):
    """重排序结果"""
    content: str = Field(..., description="文本内容")
    score: float = Field(..., description="重排序分数")
    original_rank: int = Field(..., alias="originalRank", description="原始排名")
    new_rank: int = Field(..., alias="newRank", description="新排名")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    
    class Config:
        populate_by_name = True


class RerankResponse(BaseModel):
    """重排序响应"""
    results: List[RerankResultSchema] = Field(..., description="重排序结果")
    total: int = Field(..., description="总结果数")
    model: str = Field(..., description="使用的模型")
    processing_time: float = Field(..., alias="processingTime", description="处理时间（秒）")
    
    class Config:
        populate_by_name = True


class QuestionSuggestion(BaseModel):
    """问题推荐"""
    question: str = Field(..., description="推荐问题")
    similarity: float = Field(..., description="相似度分数")
    query_count: int = Field(..., alias="queryCount", description="查询次数")
    last_queried: Optional[str] = Field(None, alias="lastQueried", description="最后查询时间")
    document_id: Optional[str] = Field(None, alias="documentId", description="关联文档ID")
    document_name: Optional[str] = Field(None, alias="documentName", description="关联文档名称")
    
    class Config:
        populate_by_name = True


class SuggestionsResponse(BaseModel):
    """相似问题推荐响应"""
    suggestions: List[QuestionSuggestion] = Field(..., description="推荐问题列表")
    total: int = Field(..., description="总数")
    processing_time: float = Field(..., alias="processingTime", description="处理时间（秒）")
    
    class Config:
        populate_by_name = True


class SimilarDocument(BaseModel):
    """相似文档"""
    id: str = Field(..., description="文档ID")
    name: str = Field(..., description="文档名称")
    similarity: float = Field(..., description="相似度分数")
    common_topics: List[str] = Field(..., alias="commonTopics", description="共同主题")
    upload_time: str = Field(..., alias="uploadTime", description="上传时间")
    file_size: int = Field(..., alias="fileSize", description="文件大小（字节）")
    page_count: Optional[int] = Field(None, alias="pageCount", description="页数")
    
    class Config:
        populate_by_name = True


class SourceDocument(BaseModel):
    """源文档信息"""
    id: str = Field(..., description="文档ID")
    name: str = Field(..., description="文档名称")
    upload_time: str = Field(..., alias="uploadTime", description="上传时间")
    
    class Config:
        populate_by_name = True


class SimilarDocumentsResponse(BaseModel):
    """相似文档推荐响应"""
    source_document: SourceDocument = Field(..., alias="sourceDocument", description="源文档")
    similar_documents: List[SimilarDocument] = Field(..., alias="similarDocuments", description="相似文档列表")
    total: int = Field(..., description="总数")
    processing_time: float = Field(..., alias="processingTime", description="处理时间（秒）")
    
    class Config:
        populate_by_name = True
