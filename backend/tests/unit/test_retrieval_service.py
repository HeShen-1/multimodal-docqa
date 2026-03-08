from types import SimpleNamespace

import pytest

from app.services.retrieval_service import RetrievalService


@pytest.mark.asyncio
async def test_retrieve_context_returns_diagnostics_and_explainable_fields(monkeypatch):
    service = RetrievalService(embedding_service=SimpleNamespace())

    async def fake_vector(query, top_k, document_ids=None):
        assert query == "费用 报销"
        assert top_k == 4
        assert document_ids == ["doc-1"]
        return [
            {
                "id": "doc-1_chunk_0",
                "content": "费用报销标准与住宿上限。",
                "metadata": {
                    "document_id": "doc-1",
                    "document_name": "policy.md",
                    "page": 3,
                    "parent_chunk_index": 0,
                    "source_type": "text",
                    "extract_method": "pdf_text",
                },
                "distance": 0.15,
            }
        ]

    async def fake_bm25(query, top_k, document_ids=None):
        assert query == "费用 报销"
        return [
            {
                "id": "doc-1_chunk_0",
                "content": "费用报销标准与住宿上限。",
                "metadata": {
                    "document_id": "doc-1",
                    "document_name": "policy.md",
                    "page": 3,
                    "parent_chunk_index": 0,
                    "source_type": "text",
                    "extract_method": "pdf_text",
                },
                "score": 2.4,
            }
        ]

    async def fake_expand(results, top_k):
        assert top_k == 4
        return [
            {
                "id": "doc-1_parent_0",
                "content": "费用报销标准与住宿上限。",
                "metadata": {
                    "document_id": "doc-1",
                    "document_name": "policy.md",
                    "page": 3,
                    "parent_chunk_index": 0,
                    "matched_content": "费用报销标准与住宿上限。",
                    "matched_contents": ["费用报销标准与住宿上限。"],
                    "source_type": "text",
                    "extract_method": "pdf_text",
                },
                "score": 0.85,
            }
        ]

    monkeypatch.setattr(service, "_vector_search", fake_vector)
    monkeypatch.setattr(service, "_bm25_search", fake_bm25)
    monkeypatch.setattr(service, "_expand_to_parent_context", fake_expand)

    context = await service.retrieve_context("  费用   报销  ", top_k=2, document_ids=["doc-1"])

    assert context["rewritten_query"] == "费用 报销"
    assert context["strategy"] == "hybrid"
    assert context["diagnostics"]["retrieved_chunks"] == 1
    assert context["diagnostics"]["top_score"] == pytest.approx(0.85)
    assert context["diagnostics"]["citation_count"] == 1
    assert context["diagnostics"]["fallback_reason"] is None
    result = context["results"][0]
    assert result["document_id"] == "doc-1"
    assert result["page_no"] == 3
    assert result["chunk_id"] == "doc-1_parent_0"
    assert result["source_type"] == "text"
    assert result["score"] == pytest.approx(0.85)
    assert result["rerank_score"] is None


def test_should_ground_no_answer_when_retrieval_score_is_too_low():
    service = RetrievalService(embedding_service=SimpleNamespace())

    decision = service.should_ground_no_answer(
        [
            {
                "score": 0.04,
                "metadata": {
                    "document_id": "doc-1",
                    "matched_contents": ["只有一小段证据"],
                },
            }
        ],
        has_document_scope=True,
    )

    assert decision["should_ground"] is True
    assert decision["reason"] == "low_retrieval_score"
    assert decision["top_score"] == pytest.approx(0.04)
