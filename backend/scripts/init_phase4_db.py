"""
Phase 4 数据库初始化脚本
创建标签、分享链接、文档表
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from loguru import logger

from app.config import get_settings
from app.models.base import Base
from app.models.tag import Tag, document_tags
from app.models.document_db import Document
from app.models.share import ShareLink


async def init_phase4_db():
    """初始化 Phase 4 数据库"""
    settings = get_settings()
    
    logger.info("开始初始化 Phase 4 数据库...")
    
    # 创建异步引擎
    engine = create_async_engine(
        settings.database_url,
        echo=True,
        future=True
    )
    
    try:
        # 创建所有表
        async with engine.begin() as conn:
            # 创建表
            await conn.run_sync(Base.metadata.create_all)
            logger.info("✓ 数据库表创建成功")
        
        # 创建默认标签
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        async with async_session() as session:
            # 检查是否已有标签
            from sqlalchemy import select, func
            result = await session.execute(select(func.count(Tag.id)))
            count = result.scalar()
            
            if count == 0:
                # 创建默认标签
                from app.utils.helpers import generate_uuid
                default_tags = [
                    {"name": "重要", "color": "#EF4444", "description": "重要文档"},
                    {"name": "工作", "color": "#3B82F6", "description": "工作相关"},
                    {"name": "学习", "color": "#10B981", "description": "学习资料"},
                    {"name": "参考", "color": "#F59E0B", "description": "参考文档"},
                    {"name": "归档", "color": "#6B7280", "description": "已归档"},
                ]
                
                for tag_data in default_tags:
                    tag = Tag(
                        id=generate_uuid(),
                        name=tag_data["name"],
                        color=tag_data["color"],
                        description=tag_data["description"],
                        usage_count=0
                    )
                    session.add(tag)
                
                await session.commit()
                logger.info(f"✓ 创建了 {len(default_tags)} 个默认标签")
            else:
                logger.info(f"✓ 数据库中已有 {count} 个标签")
        
        logger.info("✓ Phase 4 数据库初始化完成！")
        
        # 显示表信息
        logger.info("\n创建的表:")
        logger.info("  - tags: 标签表")
        logger.info("  - document_tags: 文档-标签关联表")
        logger.info("  - share_links: 分享链接表")
        logger.info("  - documents: 文档表")
        
    except Exception as e:
        logger.error(f"✗ 数据库初始化失败: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_phase4_db())

