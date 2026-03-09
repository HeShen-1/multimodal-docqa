from httpx import ASGITransport, AsyncClient
import pytest

from app.config import Settings
from app.dependencies import get_llm_service
from app.main import app
from app.services.llm_service import LLMService
from app.services.permission_service import get_current_user


def _build_settings(**overrides) -> Settings:
    values = {
        "environment": "development",
        "secret_key": "dev-secret-key-1234567890",
        "ollama_base_url": "http://localhost:11434/api",
        "ollama_llm_model": "qwen3-vl:2b-thinking-q4_K_M",
        "deepseek_base_url": "https://api.deepseek.com",
        "deepseek_api_key": "",
        "deepseek_model": "deepseek-chat",
        "local_lora_enabled": False,
        "local_lora_model_alias": "docqa-lora",
        "local_lora_base_model_path": "",
        "local_lora_adapter_path": "",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture(autouse=True)
def _reset_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_get_available_models_includes_default_ollama_model():
    service = LLMService(settings=_build_settings())

    models = service.get_available_models()

    assert models[0]["value"] == "qwen3-vl:2b-thinking-q4_K_M"
    assert models[0]["provider"] == "ollama"
    assert models[0]["is_default"] is True
    assert models[0]["supports_chat"] is True
    assert models[0]["supports_analysis"] is True


def test_get_available_models_includes_enabled_lora_model():
    service = LLMService(
        settings=_build_settings(
            local_lora_enabled=True,
            local_lora_base_model_path="H:/hf_models/Qwen2.5-3B-Instruct",
            local_lora_adapter_path="D:/models/docqa-lora",
        )
    )

    values = {item["value"] for item in service.get_available_models()}

    assert "docqa-lora" in values


def test_get_available_models_hides_disabled_lora_model():
    service = LLMService(
        settings=_build_settings(
            local_lora_enabled=False,
            local_lora_base_model_path="H:/hf_models/Qwen2.5-3B-Instruct",
            local_lora_adapter_path="D:/models/docqa-lora",
        )
    )

    values = {item["value"] for item in service.get_available_models()}

    assert "docqa-lora" not in values


def test_get_available_models_hides_deepseek_without_api_key():
    service = LLMService(settings=_build_settings(deepseek_api_key=""))

    values = {item["value"] for item in service.get_available_models()}

    assert "deepseek" not in values


def test_get_available_models_includes_deepseek_when_configured():
    service = LLMService(settings=_build_settings(deepseek_api_key="deepseek-test-key"))

    values = {item["value"] for item in service.get_available_models()}

    assert "deepseek" in values


@pytest.mark.asyncio
async def test_get_models_route_returns_api_response_with_enabled_models():
    service = LLMService(
        settings=_build_settings(
            deepseek_api_key="deepseek-test-key",
            local_lora_enabled=False,
        )
    )

    async def _override_current_user():
        return {"user_id": "user-1", "id": "user-1", "username": "tester", "role": "user"}

    def _override_llm_service():
        return service

    app.dependency_overrides[get_current_user] = _override_current_user
    app.dependency_overrides[get_llm_service] = _override_llm_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 100000
    assert payload["data"]["defaultModel"] == "qwen3-vl:2b-thinking-q4_K_M"
    values = {item["value"] for item in payload["data"]["models"]}
    assert "qwen3-vl:2b-thinking-q4_K_M" in values
    assert "deepseek" in values
    assert "docqa-lora" not in values
