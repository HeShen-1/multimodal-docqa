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


@pytest.mark.asyncio
async def test_process_csv(processor, tmp_path):
    file_path = tmp_path / "sample.csv"
    file_path.write_text("name,age\nalice,18\nbob,20\n", encoding="utf-8")
    result = await processor.process_document(file_path)
    assert result["metadata"]["chunk_count"] > 0
    assert result["metadata"]["image_count"] == 0


@pytest.mark.asyncio
async def test_process_json(processor, tmp_path):
    file_path = tmp_path / "sample.json"
    file_path.write_text('{"title":"文档","tags":["a","b"]}', encoding="utf-8")
    result = await processor.process_document(file_path)
    assert result["metadata"]["chunk_count"] > 0
    assert result["metadata"]["image_count"] == 0


@pytest.mark.asyncio
async def test_process_html(processor, tmp_path):
    file_path = tmp_path / "sample.html"
    file_path.write_text("<html><body><h1>标题</h1><p>正文</p></body></html>", encoding="utf-8")
    result = await processor.process_document(file_path)
    assert result["metadata"]["chunk_count"] > 0
    assert result["metadata"]["image_count"] == 0

