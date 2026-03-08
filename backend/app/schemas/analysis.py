from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


SummaryMethod = Literal["extractive", "generative", "hybrid"]
KeywordMethod = Literal["tfidf", "textrank", "llm", "hybrid"]
SummaryStyle = Literal["简洁", "详细", "concise", "detailed"]


class SummaryRequest(BaseModel):
    """文档摘要请求"""

    document_id: str = Field(..., alias="documentId", min_length=1, description="文档 ID")
    method: SummaryMethod = Field("hybrid", description="摘要方法")
    max_length: int = Field(300, alias="maxLength", ge=50, le=2000, description="摘要最大长度")
    style: SummaryStyle = Field("简洁", description="摘要风格")
    model: str | None = Field(None, description="模型名称，可选 deepseek 或 Ollama 模型名")

    class Config:
        populate_by_name = True


class SummaryResponse(BaseModel):
    """文档摘要响应"""

    document_id: str = Field(..., alias="documentId", description="文档 ID")
    summary: str = Field(..., description="摘要内容")
    method: SummaryMethod = Field(..., description="实际使用的摘要方法")
    style: str = Field(..., description="摘要风格")
    source_length: int = Field(..., alias="sourceLength", description="原文长度")
    compression_ratio: float = Field(..., alias="compressionRatio", description="压缩比")
    fallback_used: bool = Field(False, alias="fallbackUsed", description="是否触发回退")

    class Config:
        populate_by_name = True


class KeywordsRequest(BaseModel):
    """关键词提取请求"""

    document_id: str = Field(..., alias="documentId", min_length=1, description="文档 ID")
    method: KeywordMethod = Field("hybrid", description="关键词提取方法")
    top_k: int = Field(10, alias="topK", ge=1, le=30, description="关键词数量")
    model: str | None = Field(None, description="模型名称，可选 deepseek 或 Ollama 模型名")

    class Config:
        populate_by_name = True


class KeywordItem(BaseModel):
    """关键词项"""

    keyword: str = Field(..., description="关键词")
    score: float = Field(..., description="权重分数")
    frequency: int = Field(..., description="出现频率")


class KeywordsResponse(BaseModel):
    """关键词提取响应"""

    document_id: str = Field(..., alias="documentId", description="文档 ID")
    method: KeywordMethod = Field(..., description="实际使用的方法")
    keywords: List[KeywordItem] = Field(..., description="关键词列表")
    total_words: int = Field(..., alias="totalWords", description="词汇总数")

    class Config:
        populate_by_name = True


class CompareRequest(BaseModel):
    """文档对比请求"""

    document_id_a: str = Field(..., alias="documentIdA", min_length=1, description="文档 A ID")
    document_id_b: str = Field(..., alias="documentIdB", min_length=1, description="文档 B ID")
    top_k: int = Field(10, alias="topK", ge=3, le=30, description="主题提取数量")

    class Config:
        populate_by_name = True


class SimilarDocumentItem(BaseModel):
    """相似文档项"""

    id: str = Field(..., description="文档 ID")
    name: str = Field(..., description="文档名称")
    similarity: float = Field(..., description="综合相似度")
    semantic_similarity: float = Field(..., alias="semanticSimilarity", description="语义相似度")
    keyword_overlap: float = Field(..., alias="keywordOverlap", description="关键词重合度")
    common_topics: List[str] = Field(..., alias="commonTopics", description="共同主题")
    upload_time: str = Field(..., alias="uploadTime", description="上传时间")
    page_count: int = Field(0, alias="pageCount", description="页数")
    file_size: int = Field(0, alias="fileSize", description="文件大小")

    class Config:
        populate_by_name = True


class SimilarDocumentsResponse(BaseModel):
    """相似文档推荐响应"""

    source_document: Dict[str, Any] = Field(..., alias="sourceDocument", description="源文档")
    similar_documents: List[SimilarDocumentItem] = Field(
        ..., alias="similarDocuments", description="相似文档列表"
    )
    total: int = Field(..., description="总数")

    class Config:
        populate_by_name = True
