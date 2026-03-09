# DocQA LoRA Backend Integration Design

**Date:** 2026-03-09

**Status:** Approved for implementation

**Scope:** Integrate the evaluated LoRA model into the backend as an optional model selection in the existing conversation/document-QA API chain.

---

## Background

The latest manual evaluation confirms that the local LoRA model outperforms the current base model on the real PDF/TXT document-QA benchmark, especially after evidence optimization. The user wants to connect this LoRA model to the backend, but only as an **optional model** at first, so the current default chain remains unchanged and the risk stays low.

The backend already has:

- a unified conversation API under `/api/v1/conversations`
- a `model` field in `MessageCreate`
- a central `LLMService` that resolves model names and routes requests to provider-specific backends
- both non-streaming and SSE streaming message flows

This makes the current `LLMService` the cleanest insertion point for an optional local LoRA provider.

## Goals

- Add a selectable backend model alias for the local LoRA model.
- Reuse the existing conversation, retrieval, and SSE APIs.
- Keep the current default provider behavior unchanged.
- Use lazy-loading and in-process caching to avoid reloading the model per request.
- Support both standard and streaming responses from the existing endpoints.

## Non-Goals

- No change to LoRA weights.
- No replacement of the current default model.
- No new API route in this phase.
- No multi-worker orchestration or distributed inference service in this phase.

## Recommended Approach

Implement the LoRA integration as a **new provider path inside `LLMService`**.

This is the lowest-risk option because:

- the `model` field already exists in the request schema
- `ConversationMessageService` already records model metadata
- the provider resolution logic is already centralized
- the frontend does not need a protocol change

## Architecture

### 1. Provider model selection

Add a local alias such as `docqa-lora`.

When a request includes:

- `model="docqa-lora"`

the backend resolves to a local provider instead of `ollama` or `deepseek`.

If `model` is not provided:

- preserve the current default behavior

If the alias is selected but the model is not configured:

- return a clear backend error
- do not silently fall back to Ollama

### 2. Local LoRA runtime

The LoRA provider will:

- load the configured base model path
- load the configured adapter path
- build a tokenizer once
- cache model + tokenizer in memory
- generate answers using the same evidence-aware prompt chain already used by the backend

The loading strategy will be:

- lazy load on first request
- reuse the same runtime for later requests

This avoids startup bloat and keeps the default backend fast if the LoRA alias is never selected.

### 3. Prompting

The backend currently formats document-QA prompts using the existing prompt registry. The local LoRA path should not invent a separate conversation contract, but it should use a more concise output style aligned with the recent evaluation improvements.

Therefore:

- keep the existing RAG context assembly
- add a LoRA-specific chat wrapping layer for generation
- instruct the model to answer briefly and evidence-first

This keeps the retrieval layer unified while letting the local model use a more suitable generation format.

### 4. Streaming compatibility

The current backend already supports streaming SSE responses.

For the initial LoRA integration:

- generate the full answer locally
- split it into small chunks
- emit them through the existing SSE path as pseudo-streaming

This keeps the frontend contract unchanged while avoiding the extra complexity of implementing true token streaming from the local HF/PEFT stack in this phase.

### 5. Configuration

Add settings for:

- enable/disable local LoRA
- selectable alias
- base model path
- adapter path
- device / loading behavior
- max input length
- max new tokens
- temperature

This keeps deployment flexible and prevents hard-coding training paths into service logic.

## Files To Change

### `backend/app/config.py`

Add local LoRA settings:

- `local_lora_enabled`
- `local_lora_model_alias`
- `local_lora_base_model_path`
- `local_lora_adapter_path`
- `local_lora_device`
- `local_lora_max_input_length`
- `local_lora_max_new_tokens`
- `local_lora_temperature`

### `backend/app/services/llm_service.py`

Add:

- a local provider alias
- local provider resolution in `resolve_model()`
- lazy runtime loading helpers
- local non-streaming generation
- local pseudo-streaming generation

### `backend/tests/unit/test_conversation_message_service.py`

Adjust/add tests so model metadata and streaming remain correct when the model alias resolves to the local provider.

### New unit test file

Add a dedicated test file for `LLMService` local model resolution and runtime behavior.

## Error Handling

- If `docqa-lora` is requested when disabled, return a clear `LLMProviderError`.
- If the configured base model or adapter path does not exist, return a clear error.
- If model loading fails, log the root cause and fail the request explicitly.
- Do not silently degrade to Ollama for `docqa-lora`, because this would hide evaluation and rollout problems.

## Validation

- Unit tests for `resolve_model()` and local-provider routing
- Unit tests for pseudo-stream generation shape
- Unit tests for conversation service metadata
- `pytest` for the touched unit test set
- `compileall` for backend app and training scripts if touched

## Rollout Recommendation

- Keep the default model unchanged
- Expose `docqa-lora` as an opt-in model name
- Use it first in controlled testing / internal verification
- Only after stable results, consider switching the default

## Notes

- I am not creating commits or branches because the current session instructions forbid that unless explicitly requested.
