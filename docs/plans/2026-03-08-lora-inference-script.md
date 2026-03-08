# LoRA Inference Script Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a reusable inference script that can run either the base model or a LoRA adapter against the grounded DocQA test set and emit predictions in the evaluation script's expected JSONL format.

**Architecture:** Reuse the existing training stack in `backend/scripts/training/` and keep the inference path simple: load grounded JSONL test records, build prompts from each sample's chat messages, load the base model with optional 4-bit quantization, optionally attach a PEFT adapter, generate answers, and write `{"id","answer"}` prediction records. Keep the implementation generic so it can compare base vs LoRA with the same entrypoint.

**Tech Stack:** Python 3.11, Transformers, PEFT, bitsandbytes, JSONL utilities

---

### Task 1: Add failing unit tests for inference helpers

**Files:**
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\tests\unit\test_lora_inference_script.py`

**Step 1: Write tests for prompt construction**

Assert that the inference script strips assistant answers from chat messages and keeps system + user context.

**Step 2: Write tests for generated text extraction**

Assert that the script can remove the prompt prefix from decoded text and return only the answer body.

**Step 3: Write tests for prediction persistence**

Assert that predictions are written as JSONL records with `id` and `answer`.

### Task 2: Implement the inference script

**Files:**
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\run_lora_inference.py`

**Step 1: Add CLI arguments**

Support `--base-model`, `--adapter-path`, `--input`, `--output`, `--max-new-tokens`, `--temperature`, `--top-p`, and `--no-4bit`.

**Step 2: Implement prompt preparation**

Build generation prompts from the grounded dataset's `messages`, excluding assistant answers and adding a generation prompt.

**Step 3: Implement model loading**

Load the base model with optional 4-bit quantization and attach a PEFT adapter when `--adapter-path` is provided.

**Step 4: Implement generation and JSONL output**

Generate one answer per sample and save `{"id","answer"}` records for downstream evaluation.

### Task 3: Document the evaluation flow

**Files:**
- Modify: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\README.md`

**Step 1: Add LoRA inference command**

Document the exact command to generate `eval/lora_predictions.jsonl`.

**Step 2: Add base-vs-LoRA comparison guidance**

Document how to run the same script with and without `--adapter-path`.
