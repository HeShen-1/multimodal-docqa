from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ConversationCreate(BaseModel):
    """创建对话请求"""

    title: Optional[str] = Field(None, max_length=200, description="对话标题，不提供则自动生成")
    document_ids: Optional[List[str]] = Field(default_factory=list, description="关联的文档 ID 列表")


class MessageCreate(BaseModel):
    """发送消息请求"""

    content: str = Field(..., min_length=1, max_length=10000, description="消息内容")
    top_k: Optional[int] = Field(5, ge=1, le=20, description="检索返回数量")
    enable_thinking: Optional[bool] = Field(True, description="是否启用思考链")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=1.0, description="生成温度")
    model: Optional[str] = Field(None, max_length=80, description="模型名称，可选 deepseek 或 Ollama 模型名")


class MessageResponse(BaseModel):
    """消息响应"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    role: str
    content: str
    thinking: Optional[List[Dict[str, Any]]] = None
    sources: Optional[List[Dict[str, Any]]] = None
    extra_data: Optional[Dict[str, Any]] = None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime, _info):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        beijing_time = dt.astimezone(ZoneInfo("Asia/Shanghai"))
        return beijing_time.strftime("%Y-%m-%d %H:%M:%S")


class ConversationResponse(BaseModel):
    """对话响应"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    title: str
    document_ids: List[str]
    message_count: int
    last_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, dt: datetime, _info):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        beijing_time = dt.astimezone(ZoneInfo("Asia/Shanghai"))
        return beijing_time.strftime("%Y-%m-%d %H:%M:%S")


class ConversationDetail(ConversationResponse):
    """对话详情"""

    messages: List[MessageResponse] = []


class ConversationList(BaseModel):
    """对话列表响应"""

    total: int
    conversations: List[ConversationResponse]


class ExportFormat(str):
    MARKDOWN = "markdown"
    JSON = "json"
    PDF = "pdf"


class ConversationExportRequest(BaseModel):
    """对话导出请求"""

    format: str = Field(default="markdown", description="导出格式: markdown, json, pdf")
    include_thinking: bool = Field(default=True, description="是否包含思考过程")
    include_sources: bool = Field(default=True, description="是否包含引用来源")


class ConversationTitleUpdate(BaseModel):
    """更新对话标题请求"""

    title: str = Field(..., min_length=1, max_length=200, description="新的对话标题")
