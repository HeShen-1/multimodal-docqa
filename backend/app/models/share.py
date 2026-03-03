from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class ShareLink(Base):
    """分享链接模型"""
    __tablename__ = "share_links"
    
    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True)
    token = Column(String(64), unique=True, nullable=False, index=True)  # 分享Token
    password = Column(String(100))  # 访问密码（可选，加密存储）
    allow_download = Column(Boolean, default=True)  # 是否允许下载
    expires_at = Column(DateTime, nullable=False, index=True)  # 过期时间
    access_count = Column(Integer, default=0)  # 访问次数
    max_access_count = Column(Integer)  # 最大访问次数（可选）
    created_by = Column(String)  # 创建者ID（暂时不使用外键，避免循环依赖）
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    document = relationship("Document", back_populates="share_links")

