from types import SimpleNamespace

import pytest

from app.config import Settings
from app.services.llm_service import LLMService
from app.utils.exceptions import LLMProviderError


def _build_settings(**overrides) -> Settings:
    values = {
        "environment": "development",
        "secret_key": "dev-secret-key-1234567890",
        "ollama_base_url": "http://localhost:11434",
        "local_lora_enabled": True,
        "local_lora_model_alias": "docqa-lora",
        "local_lora_base_model_path": "H:/hf_models/Qwen2.5-3B-Instruct",
        "local_lora_adapter_path": (
            "D:/vsCode/cursor/work/multimodal-docqa/backend/scripts/training/data/"
            "docqa_workspace/prepared/outputs/qwen2_5_3b_docqa_lora_v1"
        ),
        "local_lora_max_input_length": 1536,
        "local_lora_max_new_tokens": 160,
        "local_lora_temperature": 0.1,
    }
    values.update(overrides)
    return Settings(**values)


def _sample_context() -> list[dict]:
    return [
        {
            "content": "差旅制度规定：住宿费可按标准报销。",
            "metadata": {
                "document_id": "doc-1",
                "page": 2,
            },
        }
    ]


def test_resolve_model_supports_local_lora_alias():
    service = LLMService(settings=_build_settings())

    resolved = service.resolve_model("docqa-lora")

    assert resolved.provider == "local_lora"
    assert resolved.requested_model == "docqa-lora"
    assert resolved.api_model == "docqa-lora"
    assert resolved.model_name == "docqa-lora"


def test_resolve_model_rejects_disabled_local_lora_alias():
    service = LLMService(
        settings=_build_settings(
            local_lora_enabled=False,
        )
    )

    with pytest.raises(LLMProviderError) as exc_info:
        service.resolve_model("docqa-lora")

    assert "docqa-lora" in exc_info.value.detail
    assert "LOCAL_LORA_ENABLED" in exc_info.value.detail


def test_resolve_model_rejects_missing_local_lora_paths():
    service = LLMService(
        settings=_build_settings(
            local_lora_base_model_path="",
            local_lora_adapter_path="",
        )
    )

    with pytest.raises(LLMProviderError) as exc_info:
        service.resolve_model("docqa-lora")

    assert "LOCAL_LORA_BASE_MODEL_PATH" in exc_info.value.detail
    assert "LOCAL_LORA_ADAPTER_PATH" in exc_info.value.detail


@pytest.mark.asyncio
async def test_generate_answer_uses_local_lora_provider(monkeypatch):
    service = LLMService(settings=_build_settings())
    calls = []

    def fake_run_local_generation(self, prompt: str, temperature: float, max_tokens: int) -> str:
        calls.append(
            {
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return "<thinking>1. 证据筛选: 找到差旅制度相关条款</thinking>\n<answer>结论：住宿费可按标准报销。</answer>"

    monkeypatch.setattr(LLMService, "_run_local_lora_generation", fake_run_local_generation)

    result = await service.generate_answer(
        query="住宿费能报销吗？",
        context=_sample_context(),
        stream=False,
        enable_thinking=True,
        model="docqa-lora",
    )

    assert calls
    assert calls[0]["temperature"] == 0.7
    assert calls[0]["max_tokens"] == 1024
    assert "住宿费能报销吗？" in calls[0]["prompt"]
    assert result["answer"] == "结论：住宿费可按标准报销。"
    assert result["thinking"] == [{"step": "证据筛选", "content": "找到差旅制度相关条款"}]


@pytest.mark.asyncio
async def test_generate_answer_streams_local_lora_output_in_chunks(monkeypatch):
    service = LLMService(settings=_build_settings())

    def fake_run_local_generation(self, prompt: str, temperature: float, max_tokens: int) -> str:
        del self, prompt, temperature, max_tokens
        return "这是一个用于验证本地 LoRA 伪流式输出的较长回答。"

    monkeypatch.setattr(LLMService, "_run_local_lora_generation", fake_run_local_generation)

    stream = await service.generate_answer(
        query="给出报销说明",
        context=_sample_context(),
        stream=True,
        enable_thinking=False,
        model="docqa-lora",
    )
    chunks = [chunk async for chunk in stream]

    assert "".join(chunks) == "这是一个用于验证本地 LoRA 伪流式输出的较长回答。"
    assert len(chunks) > 1


def test_get_local_lora_runtime_reuses_cached_runtime(monkeypatch):
    monkeypatch.setattr(LLMService, "_local_lora_runtime", None, raising=False)
    monkeypatch.setattr(LLMService, "_local_lora_runtime_key", None, raising=False)

    build_calls = []

    def fake_build_runtime(self):
        build_calls.append(self.settings.local_lora_adapter_path)
        return SimpleNamespace(model="fake-model", tokenizer="fake-tokenizer")

    monkeypatch.setattr(LLMService, "_build_local_lora_runtime", fake_build_runtime)

    service_a = LLMService(settings=_build_settings())
    service_b = LLMService(settings=_build_settings())

    runtime_a = service_a._get_local_lora_runtime()
    runtime_b = service_b._get_local_lora_runtime()

    assert runtime_a is runtime_b
    assert len(build_calls) == 1
