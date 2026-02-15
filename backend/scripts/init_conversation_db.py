"""
初始化Phase 2数据库表（对话管理）
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine
from app.config import get_settings
from app.models.base import Base
from app.models.user import User, RefreshToken, TokenBlacklist
from app.models.conversation import Conversation, Message

settings = get_settings()


async def init_conversation_tables():
    """初始化对话管理相关的数据库表"""
    
    # 创建异步引擎
    engine = create_async_engine(
        settings.database_url,
        echo=True,
        future=True
    )
    
    print("开始创建对话管理表...")
    
    async with engine.begin() as conn:
        # 创建conversations和messages表
        await conn.run_sync(Base.metadata.create_all, tables=[
            Conversation.__table__,
            Message.__table__
        ])
    
    print("✅ 对话管理表创建成功！")
    print("\n创建的表：")
    print("  - conversations (对话会话表)")
    print("  - messages (对话消息表)")
    
    await engine.dispose()


async def drop_conversation_tables():
    """删除对话管理相关的数据库表（谨慎使用！）"""
    
    engine = create_async_engine(
        settings.database_url,
        echo=True,
        future=True
    )
    
    print("⚠️  警告：即将删除对话管理表及其所有数据！")
    confirm = input("确认删除？(yes/no): ")
    
    if confirm.lower() != "yes":
        print("操作已取消")
        return
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all, tables=[
            Message.__table__,
            Conversation.__table__
        ])
    
    print("✅ 对话管理表已删除")
    
    await engine.dispose()


async def main():
    """主函数"""
    print("=" * 60)
    print("Phase 2 数据库初始化工具 - 对话管理")
    print("=" * 60)
    print("\n选项：")
    print("1. 创建对话管理表")
    print("2. 删除对话管理表（谨慎使用！）")
    print("3. 退出")
    
    choice = input("\n请选择操作 (1-3): ")
    
    if choice == "1":
        await init_conversation_tables()
    elif choice == "2":
        await drop_conversation_tables()
    elif choice == "3":
        print("退出")
    else:
        print("无效的选择")


if __name__ == "__main__":
    asyncio.run(main())

