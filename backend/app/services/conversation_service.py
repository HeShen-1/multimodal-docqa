"""
对话管理服务
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from app.models.conversation import Conversation, Message
from app.models.user import User
from app.utils.exceptions import NotFoundException, ValidationException


class ConversationService:
    """对话管理服务"""

    @staticmethod
    async def create_conversation(
        db: AsyncSession,
        user_id: UUID,
        title: Optional[str] = None,
        document_ids: Optional[List[str]] = None
    ) -> Conversation:
        """
        创建新的对话会话
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            title: 对话标题（可选，默认自动生成）
            document_ids: 关联的文档ID列表
            
        Returns:
            创建的对话对象
        """
        # 如果没有提供标题，自动生成
        if not title:
            # 获取用户的对话数量
            result = await db.execute(
                select(func.count(Conversation.id)).where(Conversation.user_id == user_id)
            )
            count = result.scalar() or 0
            title = f"对话 {count + 1}"

        # 创建对话
        conversation = Conversation(
            user_id=user_id,
            title=title,
            document_ids=document_ids or [],
            message_count=0,
            metadata={}
        )
        
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        
        return conversation

    @staticmethod
    async def get_conversation(
        db: AsyncSession,
        conversation_id: UUID,
        user_id: UUID
    ) -> Conversation:
        """
        获取对话详情
        
        Args:
            db: 数据库会话
            conversation_id: 对话ID
            user_id: 用户ID
            
        Returns:
            对话对象
            
        Raises:
            NotFoundException: 对话不存在或无权访问
        """
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id
            )
        )
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            raise NotFoundException("对话不存在或无权访问")
        
        return conversation

    @staticmethod
    async def list_conversations(
        db: AsyncSession,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20
    ) -> tuple[List[Conversation], int]:
        """
        获取用户的对话列表
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            skip: 跳过的记录数
            limit: 返回的最大记录数
            
        Returns:
            (对话列表, 总数)
        """
        # 获取总数
        count_result = await db.execute(
            select(func.count(Conversation.id)).where(Conversation.user_id == user_id)
        )
        total = count_result.scalar() or 0
        
        # 获取对话列表（按更新时间倒序）
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.updated_at))
            .offset(skip)
            .limit(limit)
        )
        conversations = result.scalars().all()
        
        return list(conversations), total

    @staticmethod
    async def add_message(
        db: AsyncSession,
        conversation_id: UUID,
        user_id: UUID,
        role: str,
        content: str,
        thinking: Optional[Dict[str, Any]] = None,
        sources: Optional[List[Dict[str, Any]]] = None
    ) -> Message:
        """
        添加消息到对话
        
        Args:
            db: 数据库会话
            conversation_id: 对话ID
            user_id: 用户ID
            role: 角色（user/assistant）
            content: 消息内容
            thinking: 思考过程（可选）
            sources: 引用来源（可选）
            
        Returns:
            创建的消息对象
            
        Raises:
            NotFoundException: 对话不存在
            ValidationException: 角色无效
        """
        # 验证角色
        if role not in ["user", "assistant"]:
            raise ValidationException("角色必须是 'user' 或 'assistant'")
        
        # 验证对话存在且属于该用户
        conversation = await ConversationService.get_conversation(db, conversation_id, user_id)
        
        # 创建消息
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            thinking=thinking,
            sources=sources,
            metadata={}
        )
        
        db.add(message)
        
        # 更新对话信息
        conversation.message_count += 1
        conversation.last_message = content[:100]  # 保存前100个字符作为预览
        conversation.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(message)
        
        return message

    @staticmethod
    async def get_messages(
        db: AsyncSession,
        conversation_id: UUID,
        user_id: UUID,
        limit: Optional[int] = None
    ) -> List[Message]:
        """
        获取对话的消息列表
        
        Args:
            db: 数据库会话
            conversation_id: 对话ID
            user_id: 用户ID
            limit: 返回的最大消息数（可选）
            
        Returns:
            消息列表
            
        Raises:
            NotFoundException: 对话不存在
        """
        # 验证对话存在且属于该用户
        await ConversationService.get_conversation(db, conversation_id, user_id)
        
        # 获取消息列表
        query = select(Message).where(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at)
        
        if limit:
            query = query.limit(limit)
        
        result = await db.execute(query)
        messages = result.scalars().all()
        
        return list(messages)

    @staticmethod
    async def delete_conversation(
        db: AsyncSession,
        conversation_id: UUID,
        user_id: UUID
    ) -> None:
        """
        删除对话
        
        Args:
            db: 数据库会话
            conversation_id: 对话ID
            user_id: 用户ID
            
        Raises:
            NotFoundException: 对话不存在
        """
        conversation = await ConversationService.get_conversation(db, conversation_id, user_id)
        
        await db.delete(conversation)
        await db.commit()

    @staticmethod
    async def update_conversation_title(
        db: AsyncSession,
        conversation_id: UUID,
        user_id: UUID,
        title: str
    ) -> Conversation:
        """
        更新对话标题
        
        Args:
            db: 数据库会话
            conversation_id: 对话ID
            user_id: 用户ID
            title: 新标题
            
        Returns:
            更新后的对话对象
            
        Raises:
            NotFoundException: 对话不存在
        """
        conversation = await ConversationService.get_conversation(db, conversation_id, user_id)
        
        conversation.title = title
        conversation.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(conversation)
        
        return conversation

