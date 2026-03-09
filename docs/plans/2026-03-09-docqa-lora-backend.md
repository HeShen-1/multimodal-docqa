# DocQA LoRA Backend Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate the local LoRA model into the backend as an optional selectable model within the existing conversation/document-QA chain.

**Architecture:** Extend `LLMService` to resolve a `docqa-lora` alias to a local provider, lazily load the local HF/PEFT runtime, reuse the existing retrieval and prompt flow, and expose the result through the same synchronous and SSE endpoints without changing the API contract.

**Tech Stack:** FastAPI, Pydantic settings, Transformers, PEFT, existing backend conversation services, pytest

---

### Task 1: Add failing tests for local model resolution

**Files:**
- Create: `D:/vsCode/cursor/work/multimodal-docqa/backend/tests/unit/test_llm_service_local_lora.py`
- Modify: `D:/vsCode/cursor/work/multimodal-docqa/backend/app/services/llm_service.py`
- Modify: `D:/vsCode/cursor/work/multimodal-docqa/backend/app/config.py`

**Step 1: Write the failing test**

Add tests covering:

- `docqa-lora` alias resolves to a local provider
- disabled local provider raises a clear error
- missing path configuration raises a clear error

**Step 2: Run test to verify it fails**

Run: `conda run -n multimodal-docqa python -m pytest backend/tests/unit/test_llm_service_local_lora.py -q`

Expected: FAIL because the local provider does not exist yet.

**Step 3: Write minimal implementation**

Implement config fields and `resolve_model()` support for the local alias.

**Step 4: Run test to verify it passes**

Run: `conda run -n multimodal-docqa python -m pytest backend/tests/unit/test_llm_service_local_lora.py -q`

Expected: PASS for alias resolution tests.

**Step 5: Commit**

Skipped in this session unless explicitly requested by the user.

### Task 2: Add failing tests for local runtime generation and pseudo-streaming

**Files:**
- Modify: `D:/vsCode/cursor/work/multimodal-docqa/backend/tests/unit/test_llm_service_local_lora.py`
- Modify: `D:/vsCode/cursor/work/multimodal-docqa/backend/app/services/llm_service.py`

**Step 1: Write the failing test**

Add tests covering:

- local non-streaming generation returns parsed answer payload
- local streaming path emits chunked text from a fully generated answer
- runtime loading is cached and not recreated for every call

**Step 2: Run test to verify it fails**

Run: `conda run -n multimodal-docqa python -m pytest backend/tests/unit/test_llm_service_local_lora.py -q`

Expected: FAIL because local generation helpers do not exist yet.

**Step 3: Write minimal implementation**

Implement:

- lazy runtime acquisition
- local generation helper
- pseudo-stream helper

**Step 4: Run test to verify it passes**

Run: `conda run -n multimodal-docqa python -m pytest backend/tests/unit/test_llm_service_local_lora.py -q`

Expected: PASS for local generation tests.

**Step 5: Commit**

Skipped in this session unless explicitly requested by the user.

### Task 3: Add failing tests for conversation-chain compatibility

**Files:**
- Modify: `D:/vsCode/cursor/work/multimodal-docqa/backend/tests/unit/test_conversation_message_service.py`
- Modify: `D:/vsCode/cursor/work/multimodal-docqa/backend/app/services/conversation_message_service.py`
- Modify: `D:/vsCode/cursor/work/multimodal-docqa/backend/app/services/llm_service.py`

**Step 1: Write the failing test**

Add tests covering:

- sending `model="docqa-lora"` preserves response metadata
- SSE `done` event reports the selected model alias correctly

**Step 2: Run test to verify it fails**

Run: `conda run -n multimodal-docqa python -m pytest backend/tests/unit/test_conversation_message_service.py backend/tests/unit/test_llm_service_local_lora.py -q`

Expected: FAIL because the new provider path is not fully wired yet.

**Step 3: Write minimal implementation**

Finish provider wiring so conversation services handle the local provider identically to existing providers.

**Step 4: Run test to verify it passes**

Run: `conda run -n multimodal-docqa python -m pytest backend/tests/unit/test_conversation_message_service.py backend/tests/unit/test_llm_service_local_lora.py -q`

Expected: PASS.

**Step 5: Commit**

Skipped in this session unless explicitly requested by the user.

### Task 4: Validate the integrated backend path

**Files:**
- Modify: `D:/vsCode/cursor/work/multimodal-docqa/backend/app/config.py`
- Modify: `D:/vsCode/cursor/work/multimodal-docqa/backend/app/services/llm_service.py`
- Test: `D:/vsCode/cursor/work/multimodal-docqa/backend/tests/unit/test_llm_service_local_lora.py`
- Test: `D:/vsCode/cursor/work/multimodal-docqa/backend/tests/unit/test_conversation_message_service.py`

**Step 1: Run focused tests**

Run: `conda run -n multimodal-docqa python -m pytest backend/tests/unit/test_llm_service_local_lora.py backend/tests/unit/test_conversation_message_service.py -q`

Expected: PASS.

**Step 2: Run broader touched test set**

Run: `conda run -n multimodal-docqa python -m pytest backend/tests/unit/test_document_processor.py backend/tests/unit/test_docqa_local_corpus.py backend/tests/unit/test_run_lora_inference.py backend/tests/unit/test_llm_service_local_lora.py backend/tests/unit/test_conversation_message_service.py -q`

Expected: PASS.

**Step 3: Run compile verification**

Run: `conda run -n multimodal-docqa python -m compileall backend/app`

Expected: PASS.

**Step 4: Manual usage note**

Verify that a request with:

- `model: "docqa-lora"`

now routes to the local LoRA runtime without changing the existing endpoint path.

**Step 5: Commit**

Skipped in this session unless explicitly requested by the user.
