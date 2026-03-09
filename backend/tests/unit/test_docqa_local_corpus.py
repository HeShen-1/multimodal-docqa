import pytest

from scripts.training.build_qlora_dataset import build_evidence_text
from scripts.training.prepare_local_corpus import (
    build_seed_annotation_records,
    normalize_text_source,
    prepare_local_corpus,
    render_processed_document_as_markdown,
)


def test_render_processed_document_as_markdown_groups_chunks_by_page():
    processed = {
        "text_chunks": [
            {"page": 1, "type": "text", "content": "Page one text chunk"},
            {"page": 1, "type": "ocr", "content": "Page one OCR chunk"},
            {"page": 2, "type": "text", "content": "Page two text chunk"},
        ],
        "page_count": 2,
        "metadata": {"extract_method": "pdf_text_and_ocr", "ocr_used": True},
    }

    markdown = render_processed_document_as_markdown("manual.pdf", processed)

    assert markdown.startswith("# manual")
    assert "## Page 1" in markdown
    assert "Page one text chunk" in markdown
    assert "### OCR Notes" in markdown
    assert "## Page 2" in markdown
    assert "Page two text chunk" in markdown


def test_build_seed_annotation_records_prefills_section_evidence_and_rejectable_template():
    documents = {
        "manual.md": "# Product Manual\n\n## Installation\n\nInstall steps\n\n## Usage\n\nUsage steps\n"
    }

    records = build_seed_annotation_records(documents, answerable_limit_per_doc=2)

    assert len(records) == 3
    assert records[0]["target_documents"] == ["manual.md"]
    assert records[0]["expected_evidence"] == ["manual.md#Installation"]
    assert records[0]["question"] == ""
    assert records[0]["allow_no_answer"] is False
    assert records[-1]["expected_evidence"] == []
    assert records[-1]["allow_no_answer"] is True


@pytest.mark.asyncio
async def test_prepare_local_corpus_passes_disable_ocr_to_document_processor(tmp_path, monkeypatch):
    staged = tmp_path / "local_raw_docs"
    staged.mkdir(parents=True)
    (staged / "sample.txt").write_text("hello", encoding="utf-8")

    observed: dict[str, bool] = {}

    class FakeProcessor:
        def __init__(self, *, enable_ocr: bool = True):
            observed["enable_ocr"] = enable_ocr

        async def process_document(self, path):
            return {
                "text_chunks": [{"page": 1, "type": "text", "content": path.read_text(encoding="utf-8")}],
                "page_count": 1,
                "metadata": {"extract_method": "plain_text_copy", "ocr_used": False},
            }

    monkeypatch.setattr("scripts.training.prepare_local_corpus.DocumentProcessor", FakeProcessor)

    result = await prepare_local_corpus(tmp_path, enable_ocr=False)

    assert result["documents_seen"] == 1
    assert observed["enable_ocr"] is False


def test_normalize_text_source_falls_back_for_gb18030_content(tmp_path):
    file_path = tmp_path / "novel.txt"
    file_path.write_bytes("《诡舍》\n第1章 大巴".encode("gb18030"))

    markdown = normalize_text_source(file_path)

    assert markdown.startswith("# novel")
    assert "《诡舍》" in markdown
    assert "第1章 大巴" in markdown


def test_normalize_text_source_prefers_recoverable_gb18030_over_latin1(tmp_path):
    file_path = tmp_path / "novel_with_bad_byte.txt"
    file_path.write_bytes("《诡舍》\n第1章 大巴".encode("gb18030") + b"\x80")

    markdown = normalize_text_source(file_path)

    assert "《诡舍》" in markdown
    assert "第1章 大巴" in markdown


def test_normalize_text_source_splits_long_txt_by_chapter_heading(tmp_path):
    file_path = tmp_path / "novel.txt"
    file_path.write_text(
        "\n".join(
            [
                "《诡舍》",
                "",
                "第1章 大巴",
                "大巴上一共有七个人，三女四男。",
                "",
                "第2章 别墅",
                "众人来到一栋古老别墅外。",
            ]
        ),
        encoding="utf-8",
    )

    markdown = normalize_text_source(file_path)

    assert markdown.startswith("# novel")
    assert "## 第1章 大巴" in markdown
    assert "## 第2章 别墅" in markdown
    assert "大巴上一共有七个人，三女四男。" in markdown


def test_normalize_text_source_splits_long_plain_text_without_explicit_chapters(tmp_path):
    file_path = tmp_path / "long_notes.txt"
    file_path.write_text(
        "\n\n".join(
            [
                "第一部分内容 " + "A" * 450,
                "第二部分内容 " + "B" * 450,
                "第三部分内容 " + "C" * 450,
            ]
        ),
        encoding="utf-8",
    )

    markdown = normalize_text_source(file_path)

    assert markdown.startswith("# long_notes")
    assert markdown.count("## Section ") >= 2
    assert "第一部分内容" in markdown
    assert "第三部分内容" in markdown


def test_build_evidence_text_reranks_pdf_blocks_and_drops_directory_noise():
    documents = {
        "manual.md": (
            "# 手册\n\n"
            "## Page 1\n\n"
            "1. ........ 10\n\n"
            "2. ........ 11\n\n"
            "智能客服可以处理订单查询、退货流程和售后政策说明。\n\n"
            "这是与问题无关的其他介绍。\n"
        )
    }

    evidence = build_evidence_text(
        ["manual.md#Page 1"],
        documents,
        question="智能客服通常处理哪些重复性问题？",
    )

    assert "订单查询" in evidence
    assert "退货流程" in evidence
    assert "........" not in evidence


def test_build_evidence_text_uses_ranked_chapter_blocks_for_root_txt_reference():
    documents = {
        "novel.md": (
            "# novel\n\n"
            "## 第1章 大巴\n\n"
            "大巴上一共有七个人，三女四男。\n\n"
            "## 第2章 别墅\n\n"
            "众人来到一栋古老别墅外。\n"
        )
    }

    evidence = build_evidence_text(
        ["novel.md#novel"],
        documents,
        question="大巴上一共有几个人，男女分别多少？",
    )

    assert "七个人" in evidence
    assert "三女四男" in evidence
    assert "别墅外" not in evidence


def test_build_evidence_text_falls_back_when_question_terms_do_not_match():
    documents = {
        "notes.md": "# notes\n\n## Section 1\n\n系统支持离线部署和权限隔离。\n"
    }

    evidence = build_evidence_text(
        ["notes.md#Section 1"],
        documents,
        question="这份材料有没有给出 GPU 型号？",
    )

    assert "离线部署" in evidence
    assert "权限隔离" in evidence


def test_build_evidence_text_prefers_early_sections_for_root_reference_questions():
    documents = {
        "novel.md": (
            "# novel\n\n"
            "## 第1章 大巴\n\n"
            "大巴上一共有七个人，三女四男，而且车辆没有司机。\n\n"
            "## 第2章 别墅\n\n"
            "众人来到一栋古老别墅外。\n\n"
            "## 第55章 鬼影\n\n"
            "他们后来又提到大巴上一共有八个人，这让众人更加恐惧。\n"
        )
    }

    evidence = build_evidence_text(
        ["novel.md#novel"],
        documents,
        question="《诡舍》开头的大巴上一共有几人？",
    )

    assert "七个人" in evidence
    assert "第55章" not in evidence


def test_build_evidence_text_packs_adjacent_short_paragraphs_from_same_section():
    documents = {
        "novel.md": (
            "# novel\n\n"
            "## 第1章 大巴\n\n"
            "雾很大。\n\n"
            "大巴上一共有七个人，三女四男。\n\n"
            "他们都很恐惧。\n\n"
            "## 第55章 鬼影\n\n"
            "后来有人又提到大巴上一共有八个人。\n"
        )
    }

    evidence = build_evidence_text(
        ["novel.md#novel"],
        documents,
        question="《诡舍》开头的大巴上一共有几人，男女分别多少？",
    )

    assert "七个人" in evidence
    assert "三女四男" in evidence
    assert "八个人" not in evidence


def test_build_evidence_text_prefers_gender_count_block_over_later_numeric_drift():
    documents = {
        "novel.md": (
            "# novel\n\n"
            "## 第1章 大巴\n\n"
            "大巴上一共有七个人，三女四男。\n\n"
            "后来有人误以为大巴上一共有八个人。\n"
        )
    }

    evidence = build_evidence_text(
        ["novel.md#novel"],
        documents,
        question="《诡舍》开头的大巴上一共有几人，男女分别多少？",
    )

    assert "七个人" in evidence
    assert "三女四男" in evidence
    assert "八个人" not in evidence


def test_build_evidence_text_prefers_first_chapter_for_long_root_reference():
    documents = {
        "novel.md": (
            "# novel\n\n"
            "## 第1章 大巴（续1）\n\n"
            "众人之所以害怕，是因为这辆大巴根本没有司机，驾驶位空空如也。\n\n"
            "## 第2章 别墅\n\n"
            "众人来到一栋古老别墅外。\n\n"
            "## 第355章 鬼影（续2）\n\n"
            "她也不知道为什么会对这个瘦弱的男人感到恐惧。\n"
        )
    }

    evidence = build_evidence_text(
        ["novel.md#novel"],
        documents,
        question="众人为什么会对这辆大巴感到恐惧？",
    )

    assert "没有司机" in evidence
    assert "驾驶位空空如也" in evidence
    assert "瘦弱的男人" not in evidence
