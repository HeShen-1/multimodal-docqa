"""测试配置"""
import pytest
import asyncio
import warnings
import sys
import os


@pytest.fixture(scope="module")
def event_loop():
    """为整个测试模块创建一个事件循环"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    
    # 在关闭事件循环前，先清理数据库引擎
    import app.dependencies as deps
    if deps._engine is not None:
        try:
            # 强制关闭所有连接
            loop.run_until_complete(deps._engine.dispose())
        except Exception:
            pass  # 忽略清理时的错误
        finally:
            deps._engine = None
            deps._async_session_maker = None
    
    # 取消所有待处理的任务
    try:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        # 等待所有任务取消完成
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except Exception:
        pass
    
    # 最后关闭事件循环
    loop.close()


# 过滤 SQLAlchemy 连接池清理时的异常输出
@pytest.fixture(scope="session", autouse=True)
def suppress_cleanup_errors():
    """抑制测试清理时的无害错误输出"""
    import logging
    
    # 降低 SQLAlchemy 连接池的日志级别
    logging.getLogger('sqlalchemy.pool').setLevel(logging.CRITICAL)
    
    # 抑制 SQLAlchemy 的 SAWarning
    warnings.filterwarnings("ignore", category=Warning, module="sqlalchemy")
    
    # 设置环境变量来抑制 asyncpg 的警告
    os.environ['PYTHONWARNINGS'] = 'ignore::Warning'
    
    yield


@pytest.fixture
def test_settings():
    """测试配置"""
    from app.config import Settings
    return Settings(
        debug=True,
        ollama_base_url="http://localhost:11434",
        chroma_persist_dir="./data/test_vector_db"
    )

