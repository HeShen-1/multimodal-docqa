import pytest

from app.services.document_processor import DocumentProcessor


@pytest.fixture
def processor():
    return DocumentProcessor()


def test_chunk_text(processor):
    """娴嬭瘯鏂囨湰鍒嗗潡"""
    text = "杩欐槸涓€娈垫祴璇曟枃鏈€?" * 100
    chunks = processor._chunk_text(text)
    assert len(chunks) > 0
    assert all(len(chunk) <= processor.chunk_size + 100 for chunk in chunks)


def test_chunk_text_makes_forward_progress(processor):
    """娴嬭瘯闀挎枃鏈湪閲嶅彔鍒嗗潡鏃朵笉浼氬崱姝绘垨鏃犻檺澧為暱"""
    processor.chunk_size = 40
    processor.chunk_overlap = 20
    text = ("鐢?" * 18 + "銆?" + "涔?" * 18 + "銆?") * 200

    chunks = processor._chunk_text(text)

    assert len(chunks) > 1
    assert len(chunks) < 2000
    assert all(chunk.strip() for chunk in chunks)
    assert chunks[-1].endswith("銆?")


def test_build_chunks_contains_parent_chunk_index(processor):
    """娴嬭瘯缁撴瀯鍖栧垎鍧椾細鎼哄甫鐖跺潡绱㈠紩"""
    text = (
        "绗竴绔?鎬昏\n"
        + "杩欐槸鎬昏閮ㄥ垎銆?" * 80
        + "\n\n绗簩绔?缁嗚妭\n"
        + "杩欐槸缁嗚妭閮ㄥ垎銆?" * 80
    )

    chunks, parent_count = processor._build_chunks(text=text, page=1, chunk_type="text")

    assert parent_count >= 1
    assert len(chunks) > 0
    assert all("parent_chunk_index" in chunk for chunk in chunks)
    assert min(chunk["parent_chunk_index"] for chunk in chunks) >= 0


@pytest.mark.asyncio
async def test_process_csv(processor, tmp_path):
    file_path = tmp_path / "sample.csv"
    file_path.write_text("name,age\nalice,18\nbob,20\n", encoding="utf-8")
    result = await processor.process_document(file_path)
    assert result["metadata"]["chunk_count"] > 0
    assert result["metadata"]["image_count"] == 0
    assert result["metadata"]["extract_method"] == "table_parse"
    assert result["metadata"]["source_type"] == "table"
    assert result["metadata"]["has_tables"] is True
    assert result["metadata"]["ocr_used"] is False
    assert result["metadata"]["processing_summary"]["chunk_count"] == result["metadata"]["chunk_count"]
    assert all(chunk["type"] == "table" for chunk in result["text_chunks"])
    assert "name: alice" in result["text_chunks"][0]["content"]


@pytest.mark.asyncio
async def test_process_json(processor, tmp_path):
    file_path = tmp_path / "sample.json"
    file_path.write_text('{"title":"鏂囨。","tags":["a","b"]}', encoding="utf-8")
    result = await processor.process_document(file_path)
    assert result["metadata"]["chunk_count"] > 0
    assert result["metadata"]["image_count"] == 0
    assert result["metadata"]["extract_method"] == "structured_text"
    assert result["metadata"]["processing_summary"]["extract_method"] == "structured_text"


@pytest.mark.asyncio
async def test_process_html(processor, tmp_path):
    file_path = tmp_path / "sample.html"
    file_path.write_text("<html><body><h1>鏍囬</h1><p>姝ｆ枃</p></body></html>", encoding="utf-8")
    result = await processor.process_document(file_path)
    assert result["metadata"]["chunk_count"] > 0
    assert result["metadata"]["image_count"] == 0
    assert result["metadata"]["processing_summary"]["source_type"] == "text"


@pytest.mark.asyncio
async def test_ocr_image_returns_empty_when_ocr_disabled():
    processor = DocumentProcessor(enable_ocr=False)

    result = await processor._ocr_image(b"not-an-image")

    assert result == {"text": "", "blocks": []}
