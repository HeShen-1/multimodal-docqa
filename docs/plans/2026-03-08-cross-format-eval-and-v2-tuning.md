# Cross-Format Eval and Safe V2 Tuning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a low-risk validation and iteration workflow that proves whether the current LoRA adapter generalizes beyond Markdown-heavy local data, and only run a `v2` fine-tune if it clears explicit regression gates.

**Architecture:** Keep `v1` frozen as the rollback baseline, then evaluate three layers separately: the existing Markdown holdout, a new cross-format holdout, and a short manual review set focused on refusal behavior and long-summary questions. Reuse the current normalization, annotation, dataset mixing, inference, and evaluation scripts so the only new work is data curation, decision logging, and a disciplined `v2` promotion gate.

**Tech Stack:** Python 3.11, existing `backend/scripts/training/*` pipeline, Transformers, PEFT, bitsandbytes, JSONL, Markdown reports

---

### Task 1: Freeze `v1` and define the promotion gate

**Files:**
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\manual_review_v1.md`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\v2_promotion_gate.md`
- Review: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\prepared\outputs\qwen2_5_3b_docqa_lora_v1\run_config.json`
- Review: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\comparison_report.md`

**Step 1: Create the manual review sheet**

Add a Markdown table with these columns:

```md
| sample_id | split | source_type | question_type | base_verdict | v1_verdict | better_model | notes |
|---|---|---|---|---|---|---|---|
```

Pre-fill at least these `15` rows:
- `8` rejectable samples
- `5` highest-gain samples from `comparison_report.md`
- `2` known regression samples

**Step 2: Create the `v2` promotion gate**

Record the current locked baseline:

```md
- Baseline adapter: `prepared/outputs/qwen2_5_3b_docqa_lora_v1`
- Markdown holdout metrics: `no_answer_precision=1.0`, `answer_overlap=0.8539`
- Known regression IDs:
  - `第五章_基于低代码平台的智能体搭建-answerable-007`
  - `第八章_记忆与检索-answerable-002`
```

Set these release rules:
- `v2` must not overwrite `v1`
- `v2` must keep Markdown holdout `no_answer_precision >= 1.0`
- `v2` must keep Markdown holdout `answer_overlap >= 0.83`
- `v2` must not add new hallucination cases in manual review
- `v2` must improve either cross-format behavior or the two known regression questions

**Step 3: Freeze the current artifact set**

Verify these files exist and are treated as read-only baseline inputs:
- `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\prepared\outputs\qwen2_5_3b_docqa_lora_v1\adapter_model.safetensors`
- `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\prepared\outputs\qwen2_5_3b_docqa_lora_v1\adapter_config.json`
- `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\prepared\outputs\qwen2_5_3b_docqa_lora_v1\run_config.json`
- `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\base_eval_summary.json`
- `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\lora_eval_summary.json`

**Step 4: Commit the frozen baseline docs**

Run:

```bash
git add backend/scripts/training/data/docqa_workspace/eval/manual_review_v1.md backend/scripts/training/data/docqa_workspace/eval/v2_promotion_gate.md
git commit -m "docs: freeze docqa lora v1 baseline gate"
```

Expected: a commit that only captures review and gate documents.

### Task 2: Build a representative cross-format raw corpus

**Files:**
- Add: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\local_raw_docs\cross_format\*.pdf`
- Add: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\local_raw_docs\cross_format\*.docx`
- Add: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\local_raw_docs\cross_format\*.txt`
- Add: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\local_raw_docs\cross_format\*.html`
- Add: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\local_raw_docs\cross_format\*.json`
- Add: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\local_raw_docs\cross_format\*.csv`
- Review: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\annotations\local_corpus_manifest.jsonl`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\cross_format_extraction_notes.md`

**Step 1: Add real-distribution source files**

Add `5~10` documents per high-priority type, ordered by business risk:
1. `.pdf`
2. `.docx`
3. `.txt`
4. `.html`
5. `.json` or `.csv`

Selection rules:
- Prefer files that are already seen in your production intake
- Keep subject matter close to the current local Markdown corpus
- Include at least `2` OCR-sensitive or layout-complex files
- Keep filenames stable and descriptive so `doc_id` remains readable

**Step 2: Re-run normalization**

Run from `D:\vsCode\cursor\work\multimodal-docqa\backend`:

```powershell
conda activate multimodal-docqa
python -m scripts.training.prepare_local_corpus
```

Expected:
- New normalized Markdown files in `backend/scripts/training/data/docqa_workspace/local_norm_docs`
- Updated manifest in `backend/scripts/training/data/docqa_workspace/annotations/local_corpus_manifest.jsonl`

**Step 3: Audit extraction quality**

Inspect the manifest and record, per document:
- `source_type`
- `extract_method`
- `ocr_used`
- whether headings survived
- whether tables or lists were flattened badly

Write one note per problematic file in `cross_format_extraction_notes.md` using this format:

```md
## <doc_id>
- source_type:
- extract_method:
- issue:
- severity:
- keep for eval?: yes/no
```

**Step 4: Exclude broken extraction cases from the eval slice**

If a document cannot preserve enough evidence to support grounded QA, mark it as `keep for eval?: no` and do not use it to judge model quality. Treat extraction failures separately from model failures.

### Task 3: Build a cross-format grounded holdout

**Files:**
- Modify: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\annotations\local_docqa_seed_v1.json`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\prepared\cross_format_grounded.jsonl`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\cross_format_holdout.jsonl`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\cross_format_sample_manifest.md`

**Step 1: Expand annotations after normalization**

Run:

```powershell
conda activate multimodal-docqa
python -m scripts.training.expand_local_docqa_annotations
```

Expected: `local_docqa_seed_v1.json` includes records for the newly normalized cross-format documents.

**Step 2: Manually curate the cross-format subset**

Select `30~50` high-quality records from the expanded annotation file with this balance:
- `60%~70%` answerable
- `30%~40%` rejectable
- at least `5` long-summary or multi-point questions
- at least `1` sample per retained source type

For each selected sample, verify:
- `target_documents` points to exactly one normalized file
- `expected_evidence` points to a real heading
- `expected_answer_points` are short, factual, and evidence-backed

Document the chosen sample IDs in `cross_format_sample_manifest.md` grouped by `source_type`.

**Step 3: Build a grounded JSONL file for the selected subset**

Run:

```powershell
conda activate multimodal-docqa
python -m scripts.training.build_qlora_dataset `
  --dataset scripts/training/data/docqa_workspace/annotations/local_docqa_seed_v1.json `
  --docs-dir scripts/training/data/docqa_workspace/local_norm_docs `
  --output scripts/training/data/docqa_workspace/prepared/cross_format_grounded.jsonl
```

Expected: a grounded JSONL containing all current records.

**Step 4: Export the final holdout subset**

Filter `cross_format_grounded.jsonl` down to the curated sample IDs and save the result as `eval/cross_format_holdout.jsonl`.

Use this one-off Python command from `backend/`:

```powershell
@'
import json
from pathlib import Path

base = Path("scripts/training/data/docqa_workspace")
selected_ids = {
    # paste curated sample IDs here
}

records = []
with (base / "prepared/cross_format_grounded.jsonl").open("r", encoding="utf-8") as handle:
    for line in handle:
        if not line.strip():
            continue
        row = json.loads(line)
        if row["id"] in selected_ids:
            records.append(row)

with (base / "eval/cross_format_holdout.jsonl").open("w", encoding="utf-8") as handle:
    for row in records:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")

print({"selected": len(records)})
'@ | python -
```

Expected: `selected` matches the number of curated IDs in `cross_format_sample_manifest.md`.

### Task 4: Run the cross-format evaluation matrix

**Files:**
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\cross_format_base_predictions.jsonl`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\cross_format_lora_v1_predictions_128.jsonl`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\cross_format_lora_v1_predictions_96.jsonl`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\cross_format_base_eval_summary.json`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\cross_format_lora_v1_eval_summary_128.json`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\cross_format_lora_v1_eval_summary_96.json`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\cross_format_comparison_report.md`

**Step 1: Run the base model on the cross-format holdout**

Run:

```powershell
conda activate multimodal-docqa
python -m scripts.training.run_lora_inference `
  --base-model H:\hf_models\Qwen2.5-3B-Instruct `
  --base-only `
  --input scripts/training/data/docqa_workspace/eval/cross_format_holdout.jsonl `
  --output scripts/training/data/docqa_workspace/eval/cross_format_base_predictions.jsonl `
  --max-new-tokens 128
```

**Step 2: Run `v1` with tighter decoding**

Run:

```powershell
conda activate multimodal-docqa
python -m scripts.training.run_lora_inference `
  --base-model H:\hf_models\Qwen2.5-3B-Instruct `
  --adapter-path scripts/training/data/docqa_workspace/prepared/outputs/qwen2_5_3b_docqa_lora_v1 `
  --input scripts/training/data/docqa_workspace/eval/cross_format_holdout.jsonl `
  --output scripts/training/data/docqa_workspace/eval/cross_format_lora_v1_predictions_128.jsonl `
  --max-new-tokens 128
```

**Step 3: Run `v1` with a shorter answer budget**

Only if `128` tokens is still verbose:

```powershell
conda activate multimodal-docqa
python -m scripts.training.run_lora_inference `
  --base-model H:\hf_models\Qwen2.5-3B-Instruct `
  --adapter-path scripts/training/data/docqa_workspace/prepared/outputs/qwen2_5_3b_docqa_lora_v1 `
  --input scripts/training/data/docqa_workspace/eval/cross_format_holdout.jsonl `
  --output scripts/training/data/docqa_workspace/eval/cross_format_lora_v1_predictions_96.jsonl `
  --max-new-tokens 96
```

**Step 4: Score each prediction set**

Run:

```powershell
conda activate multimodal-docqa
python -m scripts.training.evaluate_docqa_predictions `
  --ground-truth scripts/training/data/docqa_workspace/eval/cross_format_holdout.jsonl `
  --predictions scripts/training/data/docqa_workspace/eval/cross_format_base_predictions.jsonl `
  --output scripts/training/data/docqa_workspace/eval/cross_format_base_eval_summary.json

python -m scripts.training.evaluate_docqa_predictions `
  --ground-truth scripts/training/data/docqa_workspace/eval/cross_format_holdout.jsonl `
  --predictions scripts/training/data/docqa_workspace/eval/cross_format_lora_v1_predictions_128.jsonl `
  --output scripts/training/data/docqa_workspace/eval/cross_format_lora_v1_eval_summary_128.json
```

If the `96`-token run exists, also score it:

```powershell
python -m scripts.training.evaluate_docqa_predictions `
  --ground-truth scripts/training/data/docqa_workspace/eval/cross_format_holdout.jsonl `
  --predictions scripts/training/data/docqa_workspace/eval/cross_format_lora_v1_predictions_96.jsonl `
  --output scripts/training/data/docqa_workspace/eval/cross_format_lora_v1_eval_summary_96.json
```

**Step 5: Write the cross-format comparison report**

Summarize:
- per-format wins and losses
- extraction-caused false negatives
- refusal quality
- answer-length trade-offs between `128` and `96`
- whether `v1` is already good enough for rollout

Use this report template:

```md
# Cross-Format Comparison Report

## Summary
- base:
- v1@128:
- v1@96:

## By Source Type
### pdf
- outcome:
- extraction issues:

### docx
- outcome:
- extraction issues:

## Decision
- Keep `v1` as-is / proceed to `v2`
- Why:
```

### Task 5: Build a minimal `v2` delta only if the gate fails

**Files:**
- Modify: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\annotations\local_docqa_seed_v1.json`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\prepared\local_docqa_grounded_v2_delta.jsonl`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\prepared\train_mixed_v2.jsonl`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\prepared\v2_delta_notes.md`

**Step 1: Add only high-value correction samples**

Append `10~30` new records that target one of these buckets:
- long-summary compression
- multi-point aggregation
- short, direct answer style
- rejectable questions with tempting but unsupported distractors
- cross-format evidence where extraction is good but `v1` still underperforms

Do not bulk-rewrite existing good samples.

**Step 2: Rebuild the local grounded dataset**

Run:

```powershell
conda activate multimodal-docqa
python -m scripts.training.build_qlora_dataset `
  --dataset scripts/training/data/docqa_workspace/annotations/local_docqa_seed_v1.json `
  --docs-dir scripts/training/data/docqa_workspace/local_norm_docs `
  --output scripts/training/data/docqa_workspace/prepared/local_docqa_grounded_v2_delta.jsonl
```

Expected: a new grounded JSONL with the augmented annotations.

**Step 3: Mix a conservative training set**

Start from the current ratio and only change `local_target` if needed:

```powershell
conda activate multimodal-docqa
python -m scripts.training.mix_docqa_datasets `
  --local-grounded-path scripts/training/data/docqa_workspace/prepared/local_docqa_grounded_v2_delta.jsonl `
  --local-target 900 `
  --hc3-target 900 `
  --coig-target 600
```

Then copy the generated `prepared/train_mixed.jsonl` to `prepared/train_mixed_v2.jsonl` so the `v2` run has a stable input snapshot.

**Step 4: Write down exactly what changed**

In `v2_delta_notes.md`, record:
- new sample IDs
- why each sample was added
- whether it targets Markdown, cross-format, or both
- the specific failure case it is meant to fix

### Task 6: Train `v2` from base, not from `v1`

**Files:**
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\prepared\outputs\qwen2_5_3b_docqa_lora_v2\`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\prepared\outputs\qwen2_5_3b_docqa_lora_v2\run_config.json`

**Step 1: Train a fresh adapter**

Run:

```powershell
conda activate multimodal-docqa
python -m scripts.training.run_qlora_sft `
  --model-name H:\hf_models\Qwen2.5-3B-Instruct `
  --dataset-path scripts/training/data/docqa_workspace/prepared/train_mixed_v2.jsonl `
  --output-dir scripts/training/data/docqa_workspace/prepared/outputs/qwen2_5_3b_docqa_lora_v2 `
  --num-train-epochs 2 `
  --learning-rate 2e-4 `
  --max-seq-length 2048 `
  --per-device-train-batch-size 1 `
  --gradient-accumulation-steps 8
```

Expected:
- a new adapter directory
- a new `run_config.json`
- no changes inside the `v1` output directory

**Step 2: Do not resume from or overwrite `v1`**

If GPU time is limited, reduce scope by shrinking `v2` data, not by training in-place on `v1`.

**Step 3: Commit the `v2` configuration snapshot**

Run:

```bash
git add backend/scripts/training/data/docqa_workspace/prepared/v2_delta_notes.md
git commit -m "docs: record docqa v2 delta dataset"
```

Expected: the repo records the reasoning behind `v2`, even if the adapter binary itself is kept outside Git.

### Task 7: Compare `v2` against all gates before promotion

**Files:**
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\v2_predictions_markdown.jsonl`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\v2_eval_summary_markdown.json`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\v2_predictions_cross_format.jsonl`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\v2_eval_summary_cross_format.json`
- Create: `D:\vsCode\cursor\work\multimodal-docqa\backend\scripts\training\data\docqa_workspace\eval\v2_release_decision.md`

**Step 1: Run `v2` on the original Markdown holdout**

Run:

```powershell
conda activate multimodal-docqa
python -m scripts.training.run_lora_inference `
  --base-model H:\hf_models\Qwen2.5-3B-Instruct `
  --adapter-path scripts/training/data/docqa_workspace/prepared/outputs/qwen2_5_3b_docqa_lora_v2 `
  --input scripts/training/data/docqa_workspace/prepared/test_local_docqa.jsonl `
  --output scripts/training/data/docqa_workspace/eval/v2_predictions_markdown.jsonl `
  --max-new-tokens 128

python -m scripts.training.evaluate_docqa_predictions `
  --ground-truth scripts/training/data/docqa_workspace/prepared/test_local_docqa.jsonl `
  --predictions scripts/training/data/docqa_workspace/eval/v2_predictions_markdown.jsonl `
  --output scripts/training/data/docqa_workspace/eval/v2_eval_summary_markdown.json
```

**Step 2: Run `v2` on the cross-format holdout**

Run:

```powershell
conda activate multimodal-docqa
python -m scripts.training.run_lora_inference `
  --base-model H:\hf_models\Qwen2.5-3B-Instruct `
  --adapter-path scripts/training/data/docqa_workspace/prepared/outputs/qwen2_5_3b_docqa_lora_v2 `
  --input scripts/training/data/docqa_workspace/eval/cross_format_holdout.jsonl `
  --output scripts/training/data/docqa_workspace/eval/v2_predictions_cross_format.jsonl `
  --max-new-tokens 128

python -m scripts.training.evaluate_docqa_predictions `
  --ground-truth scripts/training/data/docqa_workspace/eval/cross_format_holdout.jsonl `
  --predictions scripts/training/data/docqa_workspace/eval/v2_predictions_cross_format.jsonl `
  --output scripts/training/data/docqa_workspace/eval/v2_eval_summary_cross_format.json
```

**Step 3: Review the two known regression questions manually**

Open and compare the answers for:
- `第五章_基于低代码平台的智能体搭建-answerable-007`
- `第八章_记忆与检索-answerable-002`

Require a human pass/fail note for both before promotion.

**Step 4: Write the release decision**

In `v2_release_decision.md`, answer:
- Did `v2` pass the Markdown gate?
- Did `v2` improve cross-format behavior?
- Did `v2` fix at least one known regression?
- Is `v2` actually better than `v1` for the product?

Promotion rule:
- If any answer is `no`, keep `v1`
- If all answers are `yes`, promote `v2`

**Step 5: Commit the decision docs**

Run:

```bash
git add backend/scripts/training/data/docqa_workspace/eval/cross_format_comparison_report.md backend/scripts/training/data/docqa_workspace/eval/v2_release_decision.md
git commit -m "docs: record cross-format eval and v2 release decision"
```

Expected: the decision trail is reproducible even if you stop iterating later.
