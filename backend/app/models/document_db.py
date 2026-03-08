from sqlalchemy import Column, String, Integer, DateTime, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base
from app.models.document import DocumentStatus
from app.models.tag import document_tags


class Document(Base):
    """文档数据库模型"""
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)  # 所属用户
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_path = Column(String(500), nullable=False)  # 文件存储路径
    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.PROCESSING, index=True)
    description = Column(String(500))
    page_count = Column(Integer)
    chunk_count = Column(Integer)
    image_count = Column(Integer)
    doc_metadata = Column(JSON, default={})  # 改名为 doc_metadata 避免与 SQLAlchemy 的 metadata 冲突
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    tags = relationship("Tag", secondary=document_tags, back_populates="documents")
    share_links = relationship("ShareLink", back_populates="document", cascade="all, delete-orphan")
    query_histories = relationship("QueryHistory", back_populates="document")


try:
    from app.models import share as _share  # noqa: F401
except Exception:
    _share = None

try:
    from app.models import query_history as _query_history  # noqa: F401
except Exception:
    _query_history = None

