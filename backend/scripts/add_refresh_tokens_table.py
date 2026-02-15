"""
添加 refresh_tokens 表的迁移脚本
"""
import asyncio
import sys
from pathlib import Path

# 添加 backend 目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.dependencies import get_engine
from loguru import logger


async def add_refresh_tokens_table():
    """添加 refresh_tokens 表"""
    engine = get_engine()
    
    async with engine.begin() as conn:
        # 创建 refresh_tokens 表
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token VARCHAR(500) NOT NULL UNIQUE,
                jti VARCHAR(36) NOT NULL UNIQUE,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP WITH TIME ZONE,
                device_info VARCHAR(500),
                ip_address VARCHAR(45),
                is_revoked BOOLEAN DEFAULT FALSE NOT NULL
            );
        """))
        
        # 创建索引
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id 
            ON refresh_tokens(user_id);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token 
            ON refresh_tokens(token);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_jti 
            ON refresh_tokens(jti);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at 
            ON refresh_tokens(expires_at);
        """))
        
        logger.info("✅ refresh_tokens 表创建成功")
    
    await engine.dispose()


if __name__ == "__main__":
    logger.info("开始添加 refresh_tokens 表...")
    asyncio.run(add_refresh_tokens_table())
    logger.info("✅ 迁移完成")

