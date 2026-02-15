"""
对话管理数据库模型
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.models.base import Base


class Conversation(Base):
    """对话会话模型"""
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    document_ids = Column(ARRAY(String), default=list, nullable=False)  # 关联的文档ID列表
    message_count = Column(Integer, default=0, nullable=False)
    last_message = Column(Text, nullable=True)  # 最后一条消息预览
    extra_data = Column(JSONB, default=dict, nullable=False)  # 扩展元数据
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)

    # 关系
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    user = relationship("User", back_populates="conversations")

    def __repr__(self):
        return f"<Conversation(id={self.id}, title={self.title}, messages={self.message_count})>"


class Message(Base):
    """对话消息模型"""
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user 或 assistant
    content = Column(Text, nullable=False)
    thinking = Column(JSONB, nullable=True)  # 思考过程（仅assistant）
    sources = Column(JSONB, nullable=True)  # 引用来源（仅assistant）
    extra_data = Column(JSONB, default=dict, nullable=False)  # 扩展元数据
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # 关系
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role}, conversation_id={self.conversation_id})>"

