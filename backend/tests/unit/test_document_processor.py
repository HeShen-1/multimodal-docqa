import pytest
from app.services.document_processor import DocumentProcessor


@pytest.fixture
def processor():
    return DocumentProcessor()


def test_chunk_text(processor):
    """测试文本分块"""
    text = "这是一段测试文本。" * 100
    chunks = processor._chunk_text(text)
    assert len(chunks) > 0
    assert all(len(chunk) <= processor.chunk_size + 100 for chunk in chunks)

