from __future__ import annotations

import asyncio
import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator, ClassVar, Dict, List, Optional, Union

import aiohttp
import requests
from loguru import logger

from app.config import Settings, get_settings
from app.prompts import PROMPT_VERSION, SIMPLE_QA_PROMPT, THINKING_PROMPT
from app.services.clients import OllamaClient
from app.services.resilience_service import CircuitBreakerOpenError, resilience_manager
from app.utils.exceptions import LLMProviderError, OllamaConnectionError


@dataclass(frozen=True)
class ResolvedModel:
    provider: str
    requested_model: str
    api_model: str

    @property
    def model_name(self) -> str:
        return self.requested_model or self.api_model


@dataclass(frozen=True)
class LocalLoraRuntime:
    model: Any
    tokenizer: Any


class LLMService:
    """统一的 LLM 调用服务。"""

    DEEPSEEK_ALIAS = "deepseek"
    QWEN_ALIAS = "qwen"
    LOCAL_LORA_PROVIDER = "local_lora"
    _local_lora_runtime: ClassVar[LocalLoraRuntime | None] = None
    _local_lora_runtime_key: ClassVar[tuple[str, str, str] | None] = None
    _local_lora_runtime_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, settings: Settings | None = None, default_model: str | None = None):
        self.settings = settings or get_settings()
        self.ollama_client = OllamaClient(self.settings.ollama_base_url)
        self.ollama_base_url = self.ollama_client.base_url
        self.ollama_model = self.settings.ollama_llm_model
        self.deepseek_base_url = self.settings.deepseek_base_url.rstrip("/")
        self.deepseek_api_key = self.settings.deepseek_api_key
        self.deepseek_model = self.settings.deepseek_model
        self.local_lora_enabled = self.settings.local_lora_enabled
        self.local_lora_model_alias = (self.settings.local_lora_model_alias or "docqa-lora").strip() or "docqa-lora"
        self.local_lora_base_model_path = self.settings.local_lora_base_model_path.strip()
        self.local_lora_adapter_path = self.settings.local_lora_adapter_path.strip()
        self.local_lora_device = (self.settings.local_lora_device or "auto").strip() or "auto"
        self.local_lora_max_input_length = self.settings.local_lora_max_input_length
        self.local_lora_max_new_tokens = self.settings.local_lora_max_new_tokens
        self.local_lora_temperature = self.settings.local_lora_temperature
        self.default_model = default_model
        logger.info("LLMService 初始化完成")

    async def generate_answer(
        self,
        query: str,
        context: List[Dict],
        stream: bool = False,
        enable_thinking: bool = True,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        prompt = self._build_prompt(query, context, enable_thinking)
        resolved = self.resolve_model(model)
        if stream:
            return self._stream_from_prompt(prompt, temperature=temperature, resolved=resolved)

        response_text = await self._complete_from_prompt(
            prompt,
            temperature=temperature,
            resolved=resolved,
            max_tokens=1024,
        )
        if enable_thinking:
            return self.parse_thinking_chain(response_text)
        return {"thinking": [], "answer": response_text}

    async def generate_general_answer(
        self,
        query: str,
        temperature: float = 0.7,
        stream: bool = False,
        model: Optional[str] = None,
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        prompt = (
            f"你是一个智能助手。用户问题：{query}\n\n"
            "请判断：\n"
            "- 如果是日常问候、通用知识、技术问题，直接回答\n"
            "- 如果需要查看特定文档才能回答，礼貌告知用户需要上传文档\n\n"
            "回答："
        )
        resolved = self.resolve_model(model)

        try:
            if stream:
                return self._stream_from_prompt(prompt, temperature=temperature, resolved=resolved)

            logger.info(f"发送通用对话请求，问题: {query}")
            answer = await self._complete_from_prompt(
                prompt,
                temperature=temperature,
                resolved=resolved,
                max_tokens=512,
            )
            if not answer:
                answer = "抱歉，我暂时无法回答您的问题。请先上传相关文档，或稍后再试。"
            logger.info(f"通用对话生成完成，返回长度: {len(answer)}")
            return {"thinking": [], "answer": answer}
        except CircuitBreakerOpenError:
            logger.error(f"{resolved.provider} 熔断开启，通用对话降级")
            if stream:

                async def error_generator() -> AsyncGenerator[str, None]:
                    yield "抱歉，服务暂时繁忙，请稍后重试。"

                return error_generator()
            return {"thinking": [], "answer": "抱歉，服务暂时繁忙，请稍后重试。"}
        except Exception as exc:
            logger.error(f"通用对话生成失败: {exc}")
            if stream:

                async def error_generator() -> AsyncGenerator[str, None]:
                    yield "抱歉，我暂时无法回答您的问题。"

                return error_generator()
            return {
                "thinking": [],
                "answer": "抱歉，我暂时无法回答您的问题。请先上传相关文档，或稍后再试。",
            }

    def resolve_model(self, model: Optional[str] = None) -> ResolvedModel:
        requested_model = (model or self.default_model or "").strip()
        normalized = requested_model.lower()
        local_alias = self.local_lora_model_alias.lower()

        if normalized == local_alias:
            self._ensure_local_lora_selection_available()
            return ResolvedModel(self.LOCAL_LORA_PROVIDER, self.local_lora_model_alias, self.local_lora_model_alias)

        if not requested_model or requested_model == self.ollama_model or normalized in {"ollama", self.QWEN_ALIAS}:
            api_model = self.ollama_model if normalized in {"", "ollama", self.QWEN_ALIAS} else requested_model
            return ResolvedModel("ollama", requested_model or self.ollama_model, api_model)

        if requested_model == self.deepseek_model or normalized in {self.DEEPSEEK_ALIAS, "deepseek-chat"}:
            return ResolvedModel("deepseek", requested_model or self.deepseek_model, self.deepseek_model)

        if normalized.startswith("deepseek-"):
            return ResolvedModel("deepseek", requested_model, requested_model)

        return ResolvedModel("ollama", requested_model, requested_model)

    def _build_prompt(self, query: str, context: List[Dict], enable_thinking: bool = True) -> str:
        if not context:
            return (
                f"你是智能助手。用户问题：{query}\n\n"
                "判断：如果是日常问候或通用知识，直接回答；"
                "如果需要特定文档，请告知用户需要上传文档。\n\n"
                "回答："
            )

        context_text = "\n\n".join(
            [
                (
                    f"[来源: {ctx.get('metadata', {}).get('document_id', 'unknown')}, "
                    f"第 {ctx.get('metadata', {}).get('page', 1)} 页]\n{ctx['content']}"
                )
                for ctx in context
            ]
        )
        template = THINKING_PROMPT if enable_thinking else SIMPLE_QA_PROMPT
        return template.format(
            context=context_text,
            question=query,
            prompt_version=PROMPT_VERSION,
        )

    async def _complete_from_prompt(
        self,
        prompt: str,
        temperature: float,
        resolved: ResolvedModel,
        max_tokens: int,
    ) -> str:
        if resolved.provider == self.LOCAL_LORA_PROVIDER:
            return await self._local_lora_complete(
                prompt,
                temperature=temperature,
                resolved=resolved,
                max_tokens=max_tokens,
            )
        if resolved.provider == "deepseek":
            return await self._deepseek_complete(prompt, temperature=temperature, resolved=resolved, max_tokens=max_tokens)
        return await self._ollama_complete(prompt, temperature=temperature, resolved=resolved, max_tokens=max_tokens)

    def _stream_from_prompt(
        self,
        prompt: str,
        temperature: float,
        resolved: ResolvedModel,
    ) -> AsyncGenerator[str, None]:
        if resolved.provider == self.LOCAL_LORA_PROVIDER:
            return self._local_lora_stream(prompt, temperature=temperature, resolved=resolved)
        if resolved.provider == "deepseek":
            return self._deepseek_stream(prompt, temperature=temperature, resolved=resolved)
        return self._ollama_stream(prompt, temperature=temperature, resolved=resolved)

    def _ensure_local_lora_selection_available(self) -> None:
        if not self.local_lora_enabled:
            raise LLMProviderError(
                f"本地 LoRA 模型 `{self.local_lora_model_alias}` 未启用，请先设置 LOCAL_LORA_ENABLED=true"
            )

        missing_env_keys = []
        if not self.local_lora_base_model_path:
            missing_env_keys.append("LOCAL_LORA_BASE_MODEL_PATH")
        if not self.local_lora_adapter_path:
            missing_env_keys.append("LOCAL_LORA_ADAPTER_PATH")
        if missing_env_keys:
            raise LLMProviderError(
                f"本地 LoRA 模型 `{self.local_lora_model_alias}` 缺少配置：{', '.join(missing_env_keys)}"
            )

    def _local_lora_cache_key(self) -> tuple[str, str, str]:
        return (
            self.local_lora_base_model_path,
            self.local_lora_adapter_path,
            self.local_lora_device.lower(),
        )

    def _get_local_lora_runtime(self) -> LocalLoraRuntime:
        self._ensure_local_lora_selection_available()
        cache_key = self._local_lora_cache_key()
        cls = type(self)

        if cls._local_lora_runtime is not None and cls._local_lora_runtime_key == cache_key:
            return cls._local_lora_runtime

        with cls._local_lora_runtime_lock:
            if cls._local_lora_runtime is not None and cls._local_lora_runtime_key == cache_key:
                return cls._local_lora_runtime

            runtime = self._build_local_lora_runtime()
            cls._local_lora_runtime = runtime
            cls._local_lora_runtime_key = cache_key
            return runtime

    def _build_local_lora_runtime(self) -> LocalLoraRuntime:
        self._ensure_local_lora_selection_available()

        base_model_path = Path(self.local_lora_base_model_path)
        adapter_path = Path(self.local_lora_adapter_path)
        if not base_model_path.exists():
            raise LLMProviderError(f"LOCAL_LORA_BASE_MODEL_PATH 不存在：{base_model_path}")
        if not adapter_path.exists():
            raise LLMProviderError(f"LOCAL_LORA_ADAPTER_PATH 不存在：{adapter_path}")

        try:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise LLMProviderError(
                "本地 LoRA 推理依赖缺失，请在 `multimodal-docqa` 环境安装 torch 与 peft"
            ) from exc

        runtime_device = self._resolve_local_lora_runtime_device(torch)
        tokenizer_source = adapter_path if (adapter_path / "tokenizer_config.json").exists() else base_model_path
        tokenizer = AutoTokenizer.from_pretrained(
            str(tokenizer_source),
            use_fast=False,
            trust_remote_code=True,
        )
        if tokenizer.pad_token is None and tokenizer.eos_token is not None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            str(base_model_path),
            trust_remote_code=True,
            low_cpu_mem_usage=True,
            torch_dtype=self._resolve_local_lora_torch_dtype(torch, runtime_device),
        )
        model = PeftModel.from_pretrained(model, str(adapter_path))
        model = model.to(runtime_device)
        model.eval()
        logger.info(f"本地 LoRA 运行时加载完成: alias={self.local_lora_model_alias}, device={runtime_device}")
        return LocalLoraRuntime(model=model, tokenizer=tokenizer)

    def _resolve_local_lora_runtime_device(self, torch_module: Any) -> str:
        requested_device = self.local_lora_device.lower()
        if requested_device == "auto":
            return "cuda" if torch_module.cuda.is_available() else "cpu"
        if requested_device.startswith("cuda") and not torch_module.cuda.is_available():
            raise LLMProviderError("LOCAL_LORA_DEVICE 配置为 CUDA，但当前环境未检测到可用 GPU")
        return requested_device

    @staticmethod
    def _resolve_local_lora_torch_dtype(torch_module: Any, runtime_device: str) -> Any:
        if runtime_device.startswith("cuda"):
            return torch_module.float16
        return torch_module.float32

    async def _local_lora_complete(
        self,
        prompt: str,
        temperature: float,
        resolved: ResolvedModel,
        max_tokens: int,
    ) -> str:
        del resolved
        answer = await asyncio.to_thread(
            self._run_local_lora_generation,
            prompt,
            temperature,
            max_tokens,
        )
        return answer.strip()

    async def _local_lora_stream(
        self,
        prompt: str,
        temperature: float,
        resolved: ResolvedModel,
    ) -> AsyncGenerator[str, None]:
        response_text = await self._local_lora_complete(
            prompt,
            temperature=temperature,
            resolved=resolved,
            max_tokens=self.local_lora_max_new_tokens,
        )
        chunk_size = 12
        for start in range(0, len(response_text), chunk_size):
            yield response_text[start : start + chunk_size]

    def _run_local_lora_generation(self, prompt: str, temperature: float, max_tokens: int) -> str:
        runtime = self._get_local_lora_runtime()

        try:
            import torch
        except ImportError as exc:
            raise LLMProviderError("本地 LoRA 推理依赖缺失，请在 `multimodal-docqa` 环境安装 torch") from exc

        tokenizer = runtime.tokenizer
        prompt_text = prompt
        if hasattr(tokenizer, "apply_chat_template"):
            prompt_text = tokenizer.apply_chat_template(
                self._build_chat_messages(prompt),
                tokenize=False,
                add_generation_prompt=True,
            )

        inputs = tokenizer(
            prompt_text,
            return_tensors="pt",
            truncation=True,
            max_length=self.local_lora_max_input_length,
        )
        inputs = self._move_inputs_to_model_device(inputs, runtime.model)

        generation_kwargs: Dict[str, Any] = {
            "max_new_tokens": max(1, min(max_tokens, self.local_lora_max_new_tokens)),
            "pad_token_id": tokenizer.pad_token_id,
            "eos_token_id": tokenizer.eos_token_id,
            "do_sample": temperature > 0,
        }
        if temperature > 0:
            generation_kwargs["temperature"] = temperature
            generation_kwargs["top_p"] = 0.9

        with torch.no_grad():
            output_ids = runtime.model.generate(**inputs, **generation_kwargs)

        input_length = inputs["input_ids"].shape[-1]
        generated_ids = output_ids[0][input_length:]
        answer = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
        if answer:
            return answer

        decoded_full_text = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
        if decoded_full_text.startswith(prompt_text):
            return decoded_full_text[len(prompt_text) :].strip()
        return decoded_full_text

    @staticmethod
    def _move_inputs_to_model_device(inputs: Dict[str, Any], model: Any) -> Dict[str, Any]:
        try:
            device = next(model.parameters()).device
        except (AttributeError, StopIteration, TypeError):
            device = getattr(model, "device", None)

        if device is None:
            return inputs

        return {
            key: value.to(device) if hasattr(value, "to") else value
            for key, value in inputs.items()
        }

    async def _ollama_complete(
        self,
        prompt: str,
        temperature: float,
        resolved: ResolvedModel,
        max_tokens: int,
    ) -> str:
        payload = {
            "temperature": temperature,
            "top_p": 0.9,
            "num_predict": max_tokens,
        }

        async def _generate_once():
            return await self.ollama_client.generate(
                model=resolved.api_model,
                prompt=prompt,
                temperature=temperature,
                options=payload,
                timeout=120,
            )

        try:
            response = await resilience_manager.execute(
                service_name="ollama_llm",
                operation_name="llm_generate_once",
                operation=_generate_once,
                timeout_seconds=120,
                enable_retry=True,
            )
        except CircuitBreakerOpenError:
            logger.error("Ollama 熔断开启，拒绝本次请求")
            raise OllamaConnectionError()

        return (response.get("response") or "").strip()

    async def _deepseek_complete(
        self,
        prompt: str,
        temperature: float,
        resolved: ResolvedModel,
        max_tokens: int,
    ) -> str:
        self._ensure_deepseek_config()
        payload = {
            "model": resolved.api_model,
            "messages": self._build_chat_messages(prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        def _sync_request():
            return requests.post(
                f"{self.deepseek_base_url}/chat/completions",
                headers=self._deepseek_headers(),
                json=payload,
                timeout=120,
            )

        try:
            response = await resilience_manager.execute(
                service_name="deepseek_llm",
                operation_name="llm_generate_once",
                operation=_sync_request,
                timeout_seconds=120,
                enable_retry=True,
            )
        except CircuitBreakerOpenError:
            logger.error("DeepSeek 熔断开启，拒绝本次请求")
            raise LLMProviderError("DeepSeek 服务暂时不可用")
        except requests.RequestException as exc:
            logger.error(f"DeepSeek 请求失败: {exc}")
            raise LLMProviderError("无法连接到 DeepSeek 服务") from exc

        if response.status_code != 200:
            logger.error(f"DeepSeek 生成失败: {response.text}")
            raise LLMProviderError("DeepSeek 模型调用失败")

        return self._extract_deepseek_text(response.json()).strip()

    async def _ollama_stream(
        self,
        prompt: str,
        temperature: float,
        resolved: ResolvedModel,
    ) -> AsyncGenerator[str, None]:
        async for token in self.ollama_client.stream_generate(
            model=resolved.api_model,
            prompt=prompt,
            temperature=temperature,
            options={
                "temperature": temperature,
                "top_p": 0.9,
                "num_predict": 1024,
            },
            timeout=120,
        ):
            yield token

    async def _deepseek_stream(
        self,
        prompt: str,
        temperature: float,
        resolved: ResolvedModel,
    ) -> AsyncGenerator[str, None]:
        self._ensure_deepseek_config()
        payload = {
            "model": resolved.api_model,
            "messages": self._build_chat_messages(prompt),
            "temperature": temperature,
            "max_tokens": 1024,
            "stream": True,
        }

        try:
            async with aiohttp.ClientSession(headers=self._deepseek_headers()) as session:
                async with session.post(
                    f"{self.deepseek_base_url}/chat/completions",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as response:
                    if response.status != 200:
                        logger.error(f"DeepSeek 流式生成失败: {await response.text()}")
                        raise LLMProviderError("DeepSeek 模型调用失败")

                    async for raw_line in response.content:
                        if not raw_line:
                            continue
                        decoded = raw_line.decode("utf-8", errors="ignore")
                        for line in decoded.splitlines():
                            line = line.strip()
                            if not line or not line.startswith("data:"):
                                continue
                            event_payload = line[5:].strip()
                            if event_payload == "[DONE]":
                                return
                            try:
                                event = json.loads(event_payload)
                            except json.JSONDecodeError:
                                logger.warning(f"解析 DeepSeek 流式响应失败: {event_payload[:120]}")
                                continue

                            delta = ((event.get("choices") or [{}])[0].get("delta") or {})
                            token = delta.get("content") or ""
                            if token:
                                yield token
        except aiohttp.ClientError as exc:
            logger.error(f"无法连接到 DeepSeek 服务: {exc}")
            raise LLMProviderError("无法连接到 DeepSeek 服务") from exc

    def _deepseek_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json",
        }

    def _ensure_deepseek_config(self) -> None:
        if not self.deepseek_api_key:
            raise LLMProviderError("DeepSeek API Key 未配置，请先在 backend/.env 中设置 DEEPSEEK_API_KEY")

    def _raise_ollama_error(self, status_code: int, response_text: str, model_name: str) -> None:
        lowered = (response_text or "").lower()
        if "not found" in lowered and model_name:
            raise LLMProviderError(
                f"Ollama 模型 `{model_name}` 未安装，请先执行 `ollama pull {model_name}`",
                status_code=503,
            )
        raise LLMProviderError("Ollama 模型调用失败", status_code=status_code if status_code >= 400 else 503)

    def _build_chat_messages(self, prompt: str) -> List[Dict[str, str]]:
        return [
            {"role": "system", "content": "You are a helpful document analysis assistant."},
            {"role": "user", "content": prompt},
        ]

    def _extract_deepseek_text(self, payload: Dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            return ""
        message = (choices[0] or {}).get("message") or {}
        reasoning = (message.get("reasoning_content") or "").strip()
        content = (message.get("content") or "").strip()
        if reasoning and content:
            return f"<thinking>{reasoning}</thinking>\n<answer>{content}</answer>"
        return content or reasoning

    def parse_thinking_chain(self, response: str) -> Dict[str, Any]:
        thinking_match = re.search(r"<thinking>(.*?)</thinking>", response, re.DOTALL)
        answer_match = re.search(r"<answer>(.*?)</answer>", response, re.DOTALL)

        thinking_steps = []
        if thinking_match:
            thinking_text = thinking_match.group(1)
            steps = re.findall(r"\d+\.\s*([^:\n：]+)\s*[:：]\s*([^\n]+)", thinking_text)
            thinking_steps = [
                {"step": step.strip(), "content": content.strip()}
                for step, content in steps
            ]

        answer = answer_match.group(1).strip() if answer_match else response.strip()
        return {"thinking": thinking_steps, "answer": answer}

    async def close(self):
        return None

    @staticmethod
    def _normalize_ollama_base_url(base_url: str) -> str:
        return OllamaClient.normalize_base_url(base_url)
