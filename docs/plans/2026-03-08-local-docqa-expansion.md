# Local DocQA Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refresh local normalized documents, expand grounded local DocQA annotations, and rebuild enough local samples to support the default mixed-training command.

**Architecture:** Reuse the existing local corpus pipeline instead of introducing new data paths. First refresh normalized source documents from the workspace drop folder, then expand `local_docqa_seed_v1.json` with additional grounded QA annotations, regenerate the local grounded JSONL, and finally verify that the default dataset mixer succeeds without lowering `--local-target`.

**Tech Stack:** Python 3.11, existing repository training scripts, JSON/JSONL workspace artifacts

---

### Task 1: Refresh local normalized documents

**Files:**
- Modify: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\local_norm_docs\*`
- Modify: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\annotations\local_corpus_manifest.jsonl`

**Step 1: Run the existing local corpus preparation script**

Run: `python -m scripts.training.prepare_local_corpus`

**Step 2: Verify new source docs are normalized**

Run: inspect `backend/scripts/training/data/docqa_workspace/local_norm_docs/`
Expected: newly added local Markdown files appear as normalized Markdown outputs.

### Task 2: Expand grounded local annotations

**Files:**
- Modify: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\annotations\local_docqa_seed_v1.json`

**Step 1: Inspect normalized docs and current annotations**

Run: compare normalized docs against the current annotation coverage.
Expected: identify newly added documents and under-covered existing documents.

**Step 2: Add grounded QA annotations**

Add answerable and rejectable samples per document, prioritizing definition, listing, process, comparison, condition, and refusal questions.

**Step 3: Validate annotation completeness**

Check that every answerable record has `expected_evidence` and `expected_answer_points`, and every rejectable record has `allow_no_answer=true`.

### Task 3: Rebuild grounded local training samples

**Files:**
- Modify: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\prepared\local_docqa_grounded.jsonl`

**Step 1: Run the grounded dataset builder path already used in this repo**

Run the existing local grounded generation command or helper script used for `local_docqa_grounded.jsonl`.

**Step 2: Verify record count**

Expected: at least `374` total local grounded samples.

### Task 4: Verify default mixed dataset command

**Files:**
- Modify: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\prepared\train_mixed.jsonl`
- Modify: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\prepared\validation_local_docqa.jsonl`
- Modify: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\prepared\test_local_docqa.jsonl`

**Step 1: Run default mix command**

Run: `python -m scripts.training.mix_docqa_datasets`

**Step 2: Confirm output files are produced**

Expected: default mix completes successfully and writes mixed train/validation/test outputs.
