"""测试配置"""
import pytest


@pytest.fixture
def test_settings():
    """测试配置"""
    from app.config import Settings
    return Settings(
        debug=True,
        ollama_base_url="http://localhost:11434",
        chroma_persist_dir="./data/test_vector_db"
    )

