# DocQA Evidence Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve PDF/TXT document QA quality by optimizing evidence construction and answer formatting without changing LoRA weights.

**Architecture:** Normalize long TXT into structured markdown sections, build finer-grained and reranked evidence blocks from normalized TXT/PDF markdown, and tighten the inference prompt/output length so the current LoRA model sees shorter and more relevant context. Preserve the existing annotation and evaluation workflow so the optimized pipeline can be measured on the current 36-sample benchmark.

**Tech Stack:** Python, pytest, FastAPI repo utilities, local training scripts, PEFT/Transformers inference script

---

### Task 1: Add failing tests for TXT structural chunking

**Files:**
- Modify: `D:/vsCode/cursor/work/multimodal-docqa/backend/tests/unit/test_docqa_local_corpus.py`
- Modify: `D:/vsCode/cursor/work/multimodal-docqa/backend/scripts/training/prepare_local_corpus.py`

**Step 1: Write the failing test**

Add tests covering:

- `诡舍`-style chapter headings becoming multiple markdown sections
- long plain text without chapter headings falling back to multiple sections instead of one giant body

**Step 2: Run test to verify it fails**

Run: `conda run -n multimodal-docqa python -m pytest backend/tests/unit/test_docqa_local_corpus.py -q`

Expected: FAIL because section-aware normalization does not exist yet.

**Step 3: Write minimal implementation**

Implement helper functions in `prepare_local_corpus.py` for:

- chapter/title detection
- paragraph grouping
- structured markdown emission for plain text files

**Step 4: Run test to verify it passes**

Run: `conda run -n multimodal-docqa python -m pytest backend/tests/unit/test_docqa_local_corpus.py -q`

Expected: PASS for the new TXT normalization tests.

**Step 5: Commit**

Skipped in this session unless explicitly requested by the user.

### Task 2: Add failing tests for evidence block extraction and rerank

**Files:**
- Modify: `D:/vsCode/cursor/work/multimodal-docqa/backend/tests/unit/test_docqa_local_corpus.py`
- Modify: `D:/vsCode/cursor/work/multimodal-docqa/backend/scripts/training/build_qlora_dataset.py`

**Step 1: Write the failing test**

Add tests covering:

- noisy PDF page content being split into smaller blocks
- low-information blocks being excluded
- question-matched blocks being ranked above unrelated blocks
- fallback behavior when no ranked block is strong enough

**Step 2: Run test to verify it fails**

Run: `conda run -n multimodal-docqa python -m pytest backend/tests/unit/test_docqa_local_corpus.py -q`

Expected: FAIL because evidence ranking helpers are not implemented yet.

**Step 3: Write minimal implementation**

Implement helpers in `build_qlora_dataset.py` for:

- extracting candidate evidence blocks from markdown sections
- scoring blocks against the question
- selecting top evidence blocks with optional adjacent context

**Step 4: Run test to verify it passes**

Run: `conda run -n multimodal-docqa python -m pytest backend/tests/unit/test_docqa_local_corpus.py -q`

Expected: PASS for the new evidence-selection tests.

**Step 5: Commit**

Skipped in this session unless explicitly requested by the user.

### Task 3: Add failing tests for prompt tightening

**Files:**
- Modify: `D:/vsCode/cursor/work/multimodal-docqa/backend/tests/unit/test_document_processor.py`
- Modify: `D:/vsCode/cursor/work/multimodal-docqa/backend/scripts/training/run_lora_inference.py`

**Step 1: Write the failing test**

Add tests covering:

- the short-answer instruction being present in the prompt
- the refusal instruction staying strict
- evaluation defaults using shorter completion length

**Step 2: Run test to verify it fails**

Run: `conda run -n multimodal-docqa python -m pytest backend/tests/unit/test_document_processor.py backend/tests/unit/test_docqa_local_corpus.py -q`

Expected: FAIL because the current prompt/output defaults are broader.

**Step 3: Write minimal implementation**

Implement a tighter system/user prompt contract and adjust evaluation-oriented generation defaults in `run_lora_inference.py`.

**Step 4: Run test to verify it passes**

Run: `conda run -n multimodal-docqa python -m pytest backend/tests/unit/test_document_processor.py backend/tests/unit/test_docqa_local_corpus.py -q`

Expected: PASS for the prompt contract tests.

**Step 5: Commit**

Skipped in this session unless explicitly requested by the user.

### Task 4: Verify integrated pipeline behavior

**Files:**
- Modify: `D:/vsCode/cursor/work/multimodal-docqa/backend/scripts/training/prepare_local_corpus.py`
- Modify: `D:/vsCode/cursor/work/multimodal-docqa/backend/scripts/training/build_qlora_dataset.py`
- Modify: `D:/vsCode/cursor/work/multimodal-docqa/backend/scripts/training/run_lora_inference.py`
- Test: `D:/vsCode/cursor/work/multimodal-docqa/backend/tests/unit/test_docqa_local_corpus.py`
- Test: `D:/vsCode/cursor/work/multimodal-docqa/backend/tests/unit/test_document_processor.py`

**Step 1: Run focused tests**

Run: `conda run -n multimodal-docqa python -m pytest backend/tests/unit/test_document_processor.py backend/tests/unit/test_docqa_local_corpus.py -q`

Expected: PASS.

**Step 2: Run compile verification**

Run: `conda run -n multimodal-docqa python -m compileall backend/app backend/scripts/training`

Expected: PASS without syntax errors.

**Step 3: Rebuild normalized corpus**

Run: `conda run -n multimodal-docqa python -m backend.scripts.training.prepare_local_corpus --workspace-root backend/scripts/training/data/real_cross_format_manual_eval_workspace --disable-ocr`

Expected: PASS and regenerated normalized markdown reflecting better TXT structure.

**Step 4: Rebuild evaluation ground truth if needed**

Run: `conda run -n multimodal-docqa python -m backend.scripts.training.build_qlora_dataset --dataset backend/scripts/training/data/real_cross_format_manual_eval_workspace/annotations/real_cross_format_manual_eval_36.json --docs-dir backend/scripts/training/data/real_cross_format_manual_eval_workspace/local_norm_docs --output backend/scripts/training/data/real_cross_format_manual_eval_workspace/eval/real_cross_format_manual_eval_36_ground_truth.jsonl`

Expected: PASS and shorter, better-targeted evidence fields.

**Step 5: Commit**

Skipped in this session unless explicitly requested by the user.

### Task 5: Re-run evaluation and compare to current baseline

**Files:**
- Read: `D:/vsCode/cursor/work/multimodal-docqa/backend/scripts/training/data/real_cross_format_manual_eval_workspace/eval/*.json`

**Step 1: Run base inference**

Run: `conda run -n multimodal-docqa python -m backend.scripts.training.run_lora_inference --base-model H:/hf_models/Qwen2.5-3B-Instruct --input backend/scripts/training/data/real_cross_format_manual_eval_workspace/eval/real_cross_format_manual_eval_36_ground_truth.jsonl --output backend/scripts/training/data/real_cross_format_manual_eval_workspace/eval/base_predictions_36_optimized.jsonl --base-only --max-input-length 2048 --temperature 0`

Expected: PASS with shorter answers.

**Step 2: Run LoRA inference**

Run: `conda run -n multimodal-docqa python -m backend.scripts.training.run_lora_inference --base-model H:/hf_models/Qwen2.5-3B-Instruct --adapter-path backend/scripts/training/data/docqa_workspace/prepared/outputs/qwen2_5_3b_docqa_lora_v1 --input backend/scripts/training/data/real_cross_format_manual_eval_workspace/eval/real_cross_format_manual_eval_36_ground_truth.jsonl --output backend/scripts/training/data/real_cross_format_manual_eval_workspace/eval/lora_predictions_36_optimized.jsonl --max-input-length 2048 --temperature 0`

Expected: PASS with better long-TXT/PDF evidence utilization.

**Step 3: Run evaluation**

Run:

- `conda run -n multimodal-docqa python -m backend.scripts.training.evaluate_docqa_predictions --ground-truth backend/scripts/training/data/real_cross_format_manual_eval_workspace/eval/real_cross_format_manual_eval_36_ground_truth.jsonl --predictions backend/scripts/training/data/real_cross_format_manual_eval_workspace/eval/base_predictions_36_optimized.jsonl --output backend/scripts/training/data/real_cross_format_manual_eval_workspace/eval/base_eval_summary_36_optimized.json`
- `conda run -n multimodal-docqa python -m backend.scripts.training.evaluate_docqa_predictions --ground-truth backend/scripts/training/data/real_cross_format_manual_eval_workspace/eval/real_cross_format_manual_eval_36_ground_truth.jsonl --predictions backend/scripts/training/data/real_cross_format_manual_eval_workspace/eval/lora_predictions_36_optimized.jsonl --output backend/scripts/training/data/real_cross_format_manual_eval_workspace/eval/lora_eval_summary_36_optimized.json`

Expected: PASS and measurable improvement on the known weak cases.

**Step 4: Compare metrics and failure cases**

Record:

- overall improvement
- PDF subset improvement
- TXT subset improvement
- whether `novel-answerable-*` improves
- whether refusal precision remains stable

**Step 5: Commit**

Skipped in this session unless explicitly requested by the user.
