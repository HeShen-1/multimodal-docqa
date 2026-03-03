from sqlalchemy import Column, String, Integer, DateTime, Table, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


# 文档-标签关联表（多对多）
document_tags = Table(
    'document_tags',
    Base.metadata,
    Column('document_id', String, ForeignKey('documents.id', ondelete='CASCADE'), primary_key=True),
    Column('tag_id', String, ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True),
    Column('created_at', DateTime, default=datetime.utcnow)
)


class Tag(Base):
    """标签模型"""
    __tablename__ = "tags"
    
    id = Column(String, primary_key=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    color = Column(String(20), default="#3B82F6")  # 默认蓝色
    description = Column(String(200))
    usage_count = Column(Integer, default=0)  # 使用次数
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    documents = relationship("Document", secondary=document_tags, back_populates="tags")

