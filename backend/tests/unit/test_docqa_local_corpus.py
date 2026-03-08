from scripts.training.prepare_local_corpus import (
    build_seed_annotation_records,
    render_processed_document_as_markdown,
)


def test_render_processed_document_as_markdown_groups_chunks_by_page():
    processed = {
        "text_chunks": [
            {"page": 1, "type": "text", "content": "第一页正文"},
            {"page": 1, "type": "ocr", "content": "第一页图片文字"},
            {"page": 2, "type": "text", "content": "第二页正文"},
        ],
        "page_count": 2,
        "metadata": {"extract_method": "pdf_text_and_ocr", "ocr_used": True},
    }

    markdown = render_processed_document_as_markdown("manual.pdf", processed)

    assert markdown.startswith("# manual")
    assert "## Page 1" in markdown
    assert "第一页正文" in markdown
    assert "### OCR Notes" in markdown
    assert "## Page 2" in markdown
    assert "第二页正文" in markdown


def test_build_seed_annotation_records_prefills_section_evidence_and_rejectable_template():
    documents = {
        "manual.md": "# Product Manual\n\n## Installation\n\n安装说明\n\n## Usage\n\n使用说明"
    }

    records = build_seed_annotation_records(documents, answerable_limit_per_doc=2)

    assert len(records) == 3
    assert records[0]["target_documents"] == ["manual.md"]
    assert records[0]["expected_evidence"] == ["manual.md#Installation"]
    assert records[0]["question"] == ""
    assert records[0]["allow_no_answer"] is False
    assert records[-1]["expected_evidence"] == []
    assert records[-1]["allow_no_answer"] is True
