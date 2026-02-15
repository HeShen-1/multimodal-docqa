"""
数据库连接检查脚本
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings


async def check_database():
    """检查数据库连接"""
    print("=" * 70)
    print("数据库连接检查")
    print("=" * 70)
    
    print(f"\n数据库配置:")
    print(f"  主机: {settings.postgres_host}")
    print(f"  端口: {settings.postgres_port}")
    print(f"  数据库: {settings.postgres_db}")
    print(f"  用户: {settings.postgres_user}")
    print(f"  连接URL: {settings.database_url.replace(settings.postgres_password, '***')}")
    
    print(f"\n正在连接数据库...")
    
    try:
        # 创建引擎
        engine = create_async_engine(settings.database_url, echo=False)
        
        # 测试连接
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✅ 数据库连接成功！")
            print(f"\nPostgreSQL 版本:")
            print(f"  {version}")
        
        # 检查表是否存在
        print(f"\n检查数据库表...")
        async with engine.connect() as conn:
            # 检查 users 表
            result = await conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'users'
                )
            """))
            users_exists = result.scalar()
            
            # 检查 conversations 表
            result = await conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'conversations'
                )
            """))
            conversations_exists = result.scalar()
            
            # 检查 messages 表
            result = await conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'messages'
                )
            """))
            messages_exists = result.scalar()
            
            print(f"  users 表: {'✅ 存在' if users_exists else '❌ 不存在'}")
            print(f"  conversations 表: {'✅ 存在' if conversations_exists else '❌ 不存在'}")
            print(f"  messages 表: {'✅ 存在' if messages_exists else '❌ 不存在'}")
            
            if not (users_exists and conversations_exists and messages_exists):
                print(f"\n⚠️  部分表不存在，请运行初始化脚本：")
                if not users_exists:
                    print(f"  python scripts/init_db.py")
                if not (conversations_exists and messages_exists):
                    print(f"  python scripts/init_conversation_db.py")
        
        await engine.dispose()
        
        print(f"\n" + "=" * 70)
        print("✅ 数据库检查完成！")
        print("=" * 70)
        return 0
        
    except Exception as e:
        print(f"❌ 数据库连接失败: {str(e)}")
        print(f"\n💡 故障排查：")
        print(f"  1. 检查 PostgreSQL 服务是否运行")
        print(f"     - Windows: 打开服务管理器，查找 postgresql-x64-14")
        print(f"     - 或运行: sc query postgresql-x64-14")
        print(f"  ")
        print(f"  2. 检查数据库是否已创建")
        print(f"     - 运行: psql -U postgres -c \"CREATE DATABASE multimodal_docqa;\"")
        print(f"  ")
        print(f"  3. 检查配置文件 .env")
        print(f"     - POSTGRES_HOST={settings.postgres_host}")
        print(f"     - POSTGRES_PORT={settings.postgres_port}")
        print(f"     - POSTGRES_DB={settings.postgres_db}")
        print(f"     - POSTGRES_USER={settings.postgres_user}")
        print(f"     - POSTGRES_PASSWORD=***")
        print(f"  ")
        print(f"  4. 测试连接")
        print(f"     - 运行: psql -h {settings.postgres_host} -p {settings.postgres_port} -U {settings.postgres_user} -d {settings.postgres_db}")
        
        print(f"\n" + "=" * 70)
        print("❌ 数据库检查失败")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(check_database())
    sys.exit(exit_code)

