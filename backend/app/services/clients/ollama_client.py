from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator, Dict, Optional

import aiohttp
import requests
from loguru import logger

from app.utils.exceptions import LLMProviderError, OllamaConnectionError


class OllamaClient:
    """统一封装 Ollama 的同步/流式调用。"""

    def __init__(self, base_url: str):
        self.base_url = self.normalize_base_url(base_url)

    @staticmethod
    def normalize_base_url(base_url: str) -> str:
        normalized = base_url.rstrip("/")
        if normalized.endswith("/api"):
            normalized = normalized[:-4]
        return normalized

    async def embed(self, model: str, text: str, timeout: int = 60) -> list[list[float]]:
        response = await self._post_json(
            endpoint="/api/embed",
            payload={"model": model, "input": text},
            timeout=timeout,
            operation_name="embed",
        )
        payload = self._decode_json(response, model_name=model, operation_name="embed")
        embeddings = payload.get("embeddings") or payload.get("embedding") or []
        if embeddings and isinstance(embeddings[0], (int, float)):
            return [embeddings]
        return embeddings

    async def generate(
        self,
        model: str,
        prompt: str,
        temperature: float,
        options: Optional[Dict[str, Any]] = None,
        timeout: int = 120,
    ) -> Dict[str, Any]:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": options or {},
        }
        response = await self._post_json(
            endpoint="/api/generate",
            payload=payload,
            timeout=timeout,
            operation_name="generate",
        )
        return self._decode_json(response, model_name=model, operation_name="generate")

    async def stream_generate(
        self,
        model: str,
        prompt: str,
        temperature: float,
        options: Optional[Dict[str, Any]] = None,
        timeout: int = 120,
    ) -> AsyncGenerator[str, None]:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": options or {},
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.post(f"{self.base_url}/api/generate", json=payload) as response:
                    if response.status != 200:
                        response_text = await response.text()
                        logger.error(
                            "Ollama 流式生成失败: model={}, status={}, detail={}",
                            model,
                            response.status,
                            response_text,
                        )
                        self._raise_http_error(
                            status_code=response.status,
                            response_text=response_text,
                            model_name=model,
                            operation_name="generate",
                        )

                    async for raw_line in response.content:
                        if not raw_line:
                            continue
                        line_text = raw_line.decode("utf-8").strip()
                        if not line_text:
                            continue
                        try:
                            data = json.loads(line_text)
                        except json.JSONDecodeError:
                            logger.warning("解析 Ollama 流式响应失败: {}", line_text[:120])
                            continue

                        token = data.get("response") or ""
                        if token:
                            yield token
                        if data.get("done"):
                            break
        except aiohttp.ClientError as exc:
            logger.error("无法连接到 Ollama 服务: {}", exc)
            raise OllamaConnectionError() from exc

    async def _post_json(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        timeout: int,
        operation_name: str,
    ):
        url = f"{self.base_url}{endpoint}"

        def _sync_request():
            return requests.post(url, json=payload, timeout=timeout)

        try:
            return await asyncio.to_thread(_sync_request)
        except requests.ConnectionError as exc:
            logger.error(
                "无法连接到 Ollama 服务: operation={}, endpoint={}, error={}",
                operation_name,
                endpoint,
                exc,
            )
            raise OllamaConnectionError() from exc
        except requests.RequestException as exc:
            logger.error(
                "Ollama 请求失败: operation={}, endpoint={}, error={}",
                operation_name,
                endpoint,
                exc,
            )
            raise LLMProviderError("Ollama 请求失败") from exc

    def _decode_json(self, response, model_name: str, operation_name: str) -> Dict[str, Any]:
        if response.status_code != 200:
            self._raise_http_error(
                status_code=response.status_code,
                response_text=response.text,
                model_name=model_name,
                operation_name=operation_name,
            )
        return response.json()

    def _raise_http_error(
        self,
        status_code: int,
        response_text: str,
        model_name: str,
        operation_name: str,
    ) -> None:
        lowered = (response_text or "").lower()
        if "not found" in lowered and model_name:
            raise LLMProviderError(f"Ollama 模型不存在: {model_name}", status_code=status_code)
        if status_code >= 500:
            raise OllamaConnectionError()
        raise LLMProviderError(
            f"Ollama {operation_name} 调用失败: {response_text or 'unknown error'}",
            status_code=status_code,
        )
