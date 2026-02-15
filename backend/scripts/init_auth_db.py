"""
数据库初始化脚本

创建用户认证相关的数据库表
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.models.base import Base
from app.models.user import User, TokenBlacklist


async def init_database():
    """初始化数据库表"""
    settings = get_settings()
    
    # 创建异步引擎
    engine = create_async_engine(
        settings.database_url,
        echo=True
    )
    
    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ 数据库表创建成功！")
    print("📋 已创建的表:")
    print("  - users (用户表)")
    print("  - token_blacklist (Token黑名单表)")
    
    await engine.dispose()


async def drop_tables():
    """删除所有表（谨慎使用）"""
    settings = get_settings()
    
    engine = create_async_engine(
        settings.database_url,
        echo=True
    )
    
    # 删除所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    print("⚠️  数据库表已删除！")
    
    await engine.dispose()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "drop":
        # 删除表
        print("⚠️  警告：即将删除所有表！")
        confirm = input("确认删除？(yes/no): ")
        if confirm.lower() == "yes":
            asyncio.run(drop_tables())
        else:
            print("❌ 操作已取消")
    else:
        # 创建表
        asyncio.run(init_database())

