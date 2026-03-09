import json
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.schemas.conversation import MessageCreate
from app.services.conversation_message_service import ConversationMessageService


def _parse_sse(payload: str) -> dict:
    assert payload.startswith("data: ")
    return json.loads(payload[len("data: ") :].strip())


class _FakeLLMService:
    def parse_thinking_chain(self, response: str) -> dict:
        del response
        return {
            "thinking": [{"step": "证据分析", "content": "先看命中的证据片段。"}],
            "answer": "这是最终答案。",
        }

    def resolve_model(self, model=None):
        return SimpleNamespace(provider="local_lora", model_name=model or "docqa-lora")

    async def generate_answer(self, **kwargs):
        del kwargs

        async def _stream():
            yield "<thinking>先看命中的证据片段。</thinking>"
            yield "<answer>这是最终答案。</answer>"

        return _stream()

    async def generate_general_answer(self, **kwargs):
        del kwargs

        async def _stream():
            yield "通用回答"

        return _stream()


class _FakeRetrievalService:
    async def retrieve_context(self, query: str, top_k: int, document_ids=None):
        assert query == "报销标准是什么？"
        assert top_k == 3
        assert document_ids == ["doc-1"]
        return {
            "strategy": "hybrid",
            "rewritten_query": "报销标准是什么？",
            "results": [
                {
                    "id": "doc-1_parent_0",
                    "content": "费用报销标准与住宿上限。",
                    "document_id": "doc-1",
                    "page_no": 3,
                    "chunk_id": "doc-1_parent_0",
                    "source_type": "text",
                    "score": 0.82,
                    "rerank_score": None,
                    "metadata": {
                        "document_id": "doc-1",
                        "document_name": "policy.md",
                        "page": 3,
                        "matched_contents": ["费用报销标准与住宿上限。"],
                        "source_type": "text",
                        "extract_method": "pdf_text",
                    },
                }
            ],
            "diagnostics": {
                "retrieved_chunks": 1,
                "citation_count": 1,
                "fallback_reason": None,
                "top_score": 0.82,
                "evidence_coverage": 0.58,
                "rerank_applied": False,
            },
        }

    def should_ground_no_answer(self, results, has_document_scope: bool):
        assert has_document_scope is True
        assert len(results) == 1
        return {
            "should_ground": False,
            "reason": None,
            "top_score": 0.82,
            "evidence_coverage": 0.58,
        }


@pytest.mark.asyncio
async def test_stream_message_events_emits_done_metadata_and_persists_extra_data(monkeypatch):
    from app.services import conversation_message_service as message_service_module
    from app.services import conversation_service as conversation_service_module

    add_calls = []

    async def fake_add_message(**kwargs):
        add_calls.append(kwargs)
        return SimpleNamespace(
            id=uuid4(),
            conversation_id=kwargs["conversation_id"],
            role=kwargs["role"],
            content=kwargs["content"],
            thinking=kwargs.get("thinking"),
            sources=kwargs.get("sources"),
            extra_data=kwargs.get("extra_data") or {},
            created_at=datetime.utcnow(),
        )

    async def fake_get_conversation(db, conversation_id, user_id):
        del db, conversation_id, user_id
        return SimpleNamespace(document_ids=["doc-1"])

    async def fake_execute(service_name, operation_name, operation, timeout_seconds, enable_retry):
        del service_name, operation_name, timeout_seconds, enable_retry
        return await operation()

    monkeypatch.setattr(conversation_service_module.ConversationService, "add_message", fake_add_message)
    monkeypatch.setattr(conversation_service_module.ConversationService, "get_conversation", fake_get_conversation)
    monkeypatch.setattr(message_service_module.resilience_manager, "evaluate_degradation", lambda: {"flags": {}})
    monkeypatch.setattr(message_service_module.resilience_manager, "execute", fake_execute)
    monkeypatch.setattr(message_service_module.resilience_manager.degradation, "try_acquire_query_slot", lambda: True)
    monkeypatch.setattr(message_service_module.resilience_manager.degradation, "release_query_slot", lambda: None)

    events = []
    async for payload in ConversationMessageService.stream_message_events(
        conversation_id=uuid4(),
        data=MessageCreate(content="报销标准是什么？", top_k=3, enable_thinking=True, model="docqa-lora"),
        current_user={"user_id": uuid4()},
        db=SimpleNamespace(),
        retrieval_service=_FakeRetrievalService(),
        llm_service=_FakeLLMService(),
    ):
        events.append(_parse_sse(payload))

    done_event = next(event for event in events if event["type"] == "done")
    assert done_event["model_name"] == "docqa-lora"
    assert done_event["latency_ms"] >= 0
    assert done_event["retrieved_chunks"] == 1
    assert done_event["citation_count"] == 1
    assert done_event["fallback_reason"] is None
    assert done_event["retrieval_strategy"] == "hybrid"
    assert done_event["rewritten_query"] == "报销标准是什么？"

    assistant_call = add_calls[-1]
    assert assistant_call["role"] == "assistant"
    assert assistant_call["extra_data"]["model_name"] == "docqa-lora"
    assert assistant_call["extra_data"]["retrieved_chunks"] == 1
    assert assistant_call["extra_data"]["citation_count"] == 1
    assert assistant_call["extra_data"]["retrieval_strategy"] == "hybrid"
    assert assistant_call["extra_data"]["fallback_reason"] is None
