from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload
from loguru import logger

from app.models.tag import Tag, document_tags
from app.models.document_db import Document
from app.schemas.tag import TagCreate, TagUpdate
from app.utils.helpers import generate_uuid


class TagService:
    """标签管理服务"""
    
    async def create_tag(self, db: AsyncSession, tag_data: TagCreate) -> Tag:
        """创建标签"""
        # 检查标签名是否已存在
        result = await db.execute(
            select(Tag).where(Tag.name == tag_data.name)
        )
        existing_tag = result.scalar_one_or_none()
        
        if existing_tag:
            raise ValueError(f"标签 '{tag_data.name}' 已存在")
        
        # 创建新标签
        tag = Tag(
            id=generate_uuid(),
            name=tag_data.name,
            color=tag_data.color or "#3B82F6",
            description=tag_data.description,
            usage_count=0
        )
        
        db.add(tag)
        await db.commit()
        await db.refresh(tag)
        
        logger.info(f"创建标签: {tag.name} ({tag.id})")
        return tag
    
    async def get_tag(self, db: AsyncSession, tag_id: str) -> Optional[Tag]:
        """获取标签"""
        result = await db.execute(
            select(Tag).where(Tag.id == tag_id)
        )
        return result.scalar_one_or_none()
    
    async def get_tag_by_name(self, db: AsyncSession, name: str) -> Optional[Tag]:
        """根据名称获取标签"""
        result = await db.execute(
            select(Tag).where(Tag.name == name)
        )
        return result.scalar_one_or_none()
    
    async def get_tags(
        self, 
        db: AsyncSession, 
        skip: int = 0, 
        limit: int = 100,
        keyword: Optional[str] = None
    ) -> tuple[List[Tag], int]:
        """获取标签列表"""
        query = select(Tag)
        
        # 关键词搜索
        if keyword:
            query = query.where(Tag.name.ilike(f"%{keyword}%"))
        
        # 按使用次数降序
        query = query.order_by(Tag.usage_count.desc(), Tag.created_at.desc())
        
        # 获取总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # 分页
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        tags = result.scalars().all()
        
        return list(tags), total
    
    async def update_tag(
        self, 
        db: AsyncSession, 
        tag_id: str, 
        tag_data: TagUpdate
    ) -> Optional[Tag]:
        """更新标签"""
        tag = await self.get_tag(db, tag_id)
        if not tag:
            return None
        
        # 如果更新名称，检查是否重复
        if tag_data.name and tag_data.name != tag.name:
            existing = await self.get_tag_by_name(db, tag_data.name)
            if existing:
                raise ValueError(f"标签 '{tag_data.name}' 已存在")
            tag.name = tag_data.name
        
        if tag_data.color is not None:
            tag.color = tag_data.color
        
        if tag_data.description is not None:
            tag.description = tag_data.description
        
        await db.commit()
        await db.refresh(tag)
        
        logger.info(f"更新标签: {tag.name} ({tag.id})")
        return tag
    
    async def delete_tag(self, db: AsyncSession, tag_id: str) -> bool:
        """删除标签"""
        tag = await self.get_tag(db, tag_id)
        if not tag:
            return False
        
        await db.delete(tag)
        await db.commit()
        
        logger.info(f"删除标签: {tag.name} ({tag.id})")
        return True
    
    async def add_tags_to_document(
        self, 
        db: AsyncSession, 
        document_id: str, 
        tag_ids: List[str]
    ) -> bool:
        """为文档添加标签"""
        # 获取文档
        result = await db.execute(
            select(Document)
            .options(selectinload(Document.tags))
            .where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise ValueError(f"文档不存在: {document_id}")
        
        # 获取标签
        result = await db.execute(
            select(Tag).where(Tag.id.in_(tag_ids))
        )
        tags = result.scalars().all()
        
        if len(tags) != len(tag_ids):
            raise ValueError("部分标签不存在")
        
        # 添加标签（去重）
        existing_tag_ids = {tag.id for tag in document.tags}
        new_tags = [tag for tag in tags if tag.id not in existing_tag_ids]
        
        for tag in new_tags:
            document.tags.append(tag)
            tag.usage_count += 1
        
        await db.commit()
        
        logger.info(f"为文档 {document_id} 添加 {len(new_tags)} 个标签")
        return True
    
    async def remove_tags_from_document(
        self, 
        db: AsyncSession, 
        document_id: str, 
        tag_ids: List[str]
    ) -> bool:
        """从文档移除标签"""
        # 获取文档
        result = await db.execute(
            select(Document)
            .options(selectinload(Document.tags))
            .where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise ValueError(f"文档不存在: {document_id}")
        
        # 移除标签
        tags_to_remove = [tag for tag in document.tags if tag.id in tag_ids]
        
        for tag in tags_to_remove:
            document.tags.remove(tag)
            tag.usage_count = max(0, tag.usage_count - 1)
        
        await db.commit()
        
        logger.info(f"从文档 {document_id} 移除 {len(tags_to_remove)} 个标签")
        return True
    
    async def get_document_tags(
        self, 
        db: AsyncSession, 
        document_id: str
    ) -> List[Tag]:
        """获取文档的所有标签"""
        result = await db.execute(
            select(Document)
            .options(selectinload(Document.tags))
            .where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        
        if not document:
            return []
        
        return list(document.tags)
    
    async def get_popular_tags(
        self, 
        db: AsyncSession, 
        limit: int = 10
    ) -> List[Tag]:
        """获取热门标签"""
        result = await db.execute(
            select(Tag)
            .where(Tag.usage_count > 0)
            .order_by(Tag.usage_count.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def search_tags(
        self, 
        db: AsyncSession, 
        keyword: str, 
        limit: int = 10
    ) -> List[Tag]:
        """搜索标签（用于自动补全）"""
        result = await db.execute(
            select(Tag)
            .where(Tag.name.ilike(f"%{keyword}%"))
            .order_by(Tag.usage_count.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


# 创建全局实例
tag_service = TagService()

