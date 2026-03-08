"""
对话管理API路由
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from io import BytesIO

from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationDetail,
    ConversationList,
    MessageCreate,
    MessageResponse,
    ConversationExportRequest,
    ConversationTitleUpdate
)
from app.services.conversation_service import ConversationService
from app.services.conversation_message_service import ConversationMessageService
from app.services.context_manager import ContextManager
from app.services.export_service import ExportService
from app.services.permission_service import get_current_user
from app.models.user import User
from app.dependencies import get_db, get_retrieval_service, get_llm_service
from app.utils.exceptions import NotFoundException, ValidationException

if TYPE_CHECKING:
    from app.services.retrieval_service import RetrievalService
    from app.services.llm_service import LLMService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    data: ConversationCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    创建新的对话会话
    
    - **title**: 对话标题（可选，不提供则自动生成）
    - **document_ids**: 关联的文档ID列表（可选）
    """
    conversation = await ConversationService.create_conversation(
        db=db,
        user_id=current_user["user_id"],
        title=data.title,
        document_ids=data.document_ids
    )
    
    return conversation


@router.get("", response_model=ConversationList)
async def list_conversations(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回的最大记录数"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前用户的对话列表
    
    按最后更新时间倒序排列
    """
    conversations, total = await ConversationService.list_conversations(
        db=db,
        user_id=current_user["user_id"],
        skip=skip,
        limit=limit
    )
    
    return ConversationList(
        total=total,
        conversations=conversations
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取对话详情（包含所有消息）
    """
    conversation = await ConversationService.get_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user["user_id"]
    )
    
    messages = await ConversationService.get_messages(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user["user_id"]
    )
    
    # 构建响应
    response = ConversationDetail(
        id=conversation.id,
        user_id=conversation.user_id,
        title=conversation.title,
        document_ids=conversation.document_ids,
        message_count=conversation.message_count,
        last_message=conversation.last_message,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[MessageResponse.model_validate(msg) for msg in messages]
    )
    
    return response


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: UUID,
    data: MessageCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    llm_service: LLMService = Depends(get_llm_service)
):
    """
    在对话中发送消息并获取AI回复
    
    这个接口会：
    1. 保存用户消息
    2. 检索相关文档内容
    3. 调用LLM生成回复（支持RAG和通用对话）
    4. 保存AI回复（包含thinking和sources）
    5. 返回用户消息和AI回复
    """
    return await ConversationMessageService.send_message(
        conversation_id=conversation_id,
        data=data,
        current_user=current_user,
        db=db,
        retrieval_service=retrieval_service,
        llm_service=llm_service,
    )


@router.post("/{conversation_id}/messages/stream")
async def send_message_stream(
    conversation_id: UUID,
    data: MessageCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    llm_service: LLMService = Depends(get_llm_service)
):
    """
    流式发送消息并获取AI回复
    
    使用Server-Sent Events (SSE)返回流式数据
    
    事件类型：
    - status: 状态信息
    - thinking: 思考步骤
    - answer: 答案内容（逐字返回）
    - source: 引用来源
    - done: 完成信号
    - error: 错误信息
    """
    return StreamingResponse(
        ConversationMessageService.stream_message_events(
            conversation_id=conversation_id,
            data=data,
            current_user=current_user,
            db=db,
            retrieval_service=retrieval_service,
            llm_service=llm_service,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除对话
    
    会同时删除该对话下的所有消息
    """
    await ConversationService.delete_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user["user_id"]
    )
    
    return {"message": "对话已删除"}


@router.patch("/{conversation_id}/title", response_model=ConversationResponse)
async def update_conversation_title(
    conversation_id: UUID,
    data: ConversationTitleUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新对话标题
    
    - **title**: 新的对话标题（1-200字符）
    """
    conversation = await ConversationService.update_conversation_title(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user["user_id"],
        title=data.title
    )
    
    return conversation


@router.get("/{conversation_id}/export")
async def export_conversation(
    conversation_id: UUID,
    format: str = Query("markdown", description="导出格式: markdown, json, pdf"),
    include_thinking: bool = Query(True, description="是否包含思考过程"),
    include_sources: bool = Query(True, description="是否包含引用来源"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    导出对话记录
    
    支持的格式：
    - **markdown**: Markdown格式，适合阅读和分享
    - **json**: JSON格式，适合数据分析
    - **pdf**: PDF格式，适合打印和存档（需要安装reportlab）
    """
    # 验证格式
    if format not in ["markdown", "json", "pdf"]:
        raise ValidationException("不支持的导出格式，请使用 markdown、json 或 pdf")
    
    # 获取对话和消息
    conversation = await ConversationService.get_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user["user_id"]
    )
    
    messages = await ConversationService.get_messages(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user["user_id"]
    )
    
    # 根据格式导出
    if format == "markdown":
        content = ExportService.export_to_markdown(
            conversation, messages, include_thinking, include_sources
        )
        media_type = "text/markdown"
        content_bytes = content.encode('utf-8')
    elif format == "json":
        content = ExportService.export_to_json(
            conversation, messages, include_thinking, include_sources
        )
        media_type = "application/json"
        content_bytes = content.encode('utf-8')
    else:  # pdf
        content_bytes = ExportService.export_to_pdf(
            conversation, messages, include_thinking, include_sources
        )
        media_type = "application/pdf"
    
    # 生成文件名（仅ASCII字符）
    filename = ExportService.get_export_filename(conversation, format)
    
    # 返回文件流
    return StreamingResponse(
        BytesIO(content_bytes),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

