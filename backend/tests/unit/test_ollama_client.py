import requests
import pytest

from app.services.clients.ollama_client import OllamaClient
from app.utils.exceptions import OllamaConnectionError


class _Response:
    def __init__(self, status_code: int, payload: dict, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or str(payload)

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_embed_posts_to_embed_endpoint(monkeypatch):
    called = {}

    def fake_post(url, json, timeout):
        called["url"] = url
        called["json"] = json
        called["timeout"] = timeout
        return _Response(200, {"embeddings": [[0.1, 0.2, 0.3]]})

    monkeypatch.setattr(requests, "post", fake_post)

    client = OllamaClient(base_url="http://127.0.0.1:11434/api")
    result = await client.embed(model="demo-embed", text="hello")

    assert called["url"] == "http://127.0.0.1:11434/api/embed"
    assert called["json"] == {"model": "demo-embed", "input": "hello"}
    assert called["timeout"] == 60
    assert result == [[0.1, 0.2, 0.3]]


@pytest.mark.asyncio
async def test_generate_maps_connection_error(monkeypatch):
    def fake_post(url, json, timeout):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(requests, "post", fake_post)

    client = OllamaClient(base_url="http://127.0.0.1:11434")

    with pytest.raises(OllamaConnectionError):
        await client.generate(
            model="demo-chat",
            prompt="hello",
            temperature=0.2,
            options={"num_predict": 128},
        )
