from datetime import datetime
from types import SimpleNamespace

import pytest

from app.models.document import DocumentStatus
from app.services import document_route_service


def _build_document(status=DocumentStatus.COMPLETED):
    return SimpleNamespace(
        id="doc-1",
        file_name="demo.pdf",
        file_type=".pdf",
        file_size=1024,
        status=status,
        description="demo",
        page_count=5,
        chunk_count=8,
        image_count=1,
        doc_metadata={
            "source": "unit-test",
            "extract_method": "pdf_text_and_ocr",
            "ocr_used": True,
            "has_tables": False,
            "has_images": True,
            "source_type": "mixed",
        },
        created_at=datetime(2026, 3, 1, 10, 0, 0),
        updated_at=datetime(2026, 3, 1, 10, 5, 0),
    )


def test_serialize_document_record_uses_db_fields():
    payload = document_route_service.serialize_document_record(_build_document())

    assert payload["id"] == "doc-1"
    assert payload["fileName"] == "demo.pdf"
    assert payload["fileType"] == ".pdf"
    assert payload["chunkCount"] == 8
    assert payload["metadata"]["source"] == "unit-test"
    assert payload["processingSummary"] == {
        "extractMethod": "pdf_text_and_ocr",
        "ocrUsed": True,
        "pageCount": 5,
        "chunkCount": 8,
        "hasTables": False,
        "hasImages": True,
        "sourceType": "mixed",
    }


def test_build_document_status_payload_prefers_transient_progress(monkeypatch):
    monkeypatch.setitem(
        document_route_service.processing_status,
        "doc-1",
        {
            "status": DocumentStatus.PROCESSING,
            "progress": 42,
            "currentStep": "向量化",
            "message": "处理中",
        },
    )

    payload = document_route_service.build_document_status_payload(
        _build_document(status=DocumentStatus.PROCESSING)
    )

    assert payload["documentId"] == "doc-1"
    assert payload["progress"] == 42
    assert payload["currentStep"] == "向量化"
    assert payload["status"] == DocumentStatus.PROCESSING


def test_build_document_status_payload_uses_db_state_when_cache_missing():
    payload = document_route_service.build_document_status_payload(
        _build_document(status=DocumentStatus.FAILED)
    )

    assert payload["documentId"] == "doc-1"
    assert payload["status"] == DocumentStatus.FAILED
    assert payload["currentStep"] == "失败"
