# DocQA Evidence Optimization Design

**Date:** 2026-03-09

**Status:** Approved for implementation

**Scope:** Optimize the local PDF/TXT document QA pipeline without changing LoRA weights.

---

## Background

The latest manually annotated evaluation on the `real_cross_format` sample set shows that the LoRA model is already clearly stronger than the base model for PDF/TXT document QA, but the remaining weak cases are concentrated in the evidence construction and answer formatting pipeline rather than in the model weights:

- Long unstructured TXT files such as `诡舍.txt` are normalized into a single giant section and later truncated at inference time.
- PDF evidence is still page-oriented and contains directory noise, repeated short lines, and other low-signal fragments.
- The current answer template tends to be longer than necessary, which can reduce answer-overlap metrics even when the answer is directionally correct.

This design keeps the current LoRA adapter unchanged and improves the surrounding data path so the same model receives cleaner, shorter, and better-ranked evidence.

## Goals

- Split long TXT files by chapter/title structure before they become evidence.
- Produce finer and cleaner PDF evidence blocks from normalized markdown.
- Add a lightweight rerank step so only the most relevant evidence blocks are injected.
- Tighten answer style and output length to reduce verbose drift.
- Re-run the 36-sample manual evaluation and compare against the current baseline.

## Non-Goals

- No LoRA retraining or adapter modification.
- No backend API integration in this phase.
- No heavy vector index or external retrieval dependency.
- No full redesign of the current training/evaluation data format.

## Constraints

- Must preserve compatibility with the existing workspace layout under `backend/scripts/training/data/...`.
- Must remain runnable in the `multimodal-docqa` conda environment on Windows.
- Must keep changes focused on the training/evaluation pipeline and related unit tests.

## Design Summary

The optimization is split into three coordinated improvements:

1. **TXT structural chunking** at normalization time
2. **PDF finer-grained evidence selection** at dataset-build time
3. **Short-answer prompting** at inference time

This keeps the current normalized-document and annotation workflow intact while improving the quality of the evidence seen by the model.

## Architecture

### 1. TXT structural chunking

Current behavior converts plain text sources into:

- `# <filename>`
- followed by the full raw content

For long files, this yields exactly one top-level section, which makes evidence references too coarse and leads to prompt truncation.

The new behavior will:

- detect chapter/title-like boundaries in plain text
- emit structured markdown with subsection headings
- preserve original reading order
- fall back to paragraph/length grouping if no chapter structure is detected

Planned heading detectors:

- `第X章 / 第X节 / 第X回 / 第X卷 / 第X篇`
- numeric headings such as `1.`, `1.1`, `2、`
- already-structured title-like short lines

For chapterized TXT:

- the normalized markdown will contain `##` section headings
- evidence references can target `filename.md#<section>`
- very long chapters will still be internally split into sub-sections using paragraph grouping

### 2. PDF finer-grained evidence selection

Current behavior preserves PDF pages in markdown as `## Page N`, which is useful for provenance but still too coarse for noisy pages.

The new behavior will keep page traceability but build evidence from **sub-page blocks** rather than from the whole page section.

Approach:

- parse normalized markdown sections into page blocks
- break each page into smaller semantically coherent blocks
- drop low-information blocks such as:
  - directory-like dot leaders
  - repeated short page artifacts
  - blocks dominated by punctuation or isolated tokens
- score blocks against the question using lightweight lexical heuristics
- select top-K blocks and optionally include one adjacent block for continuity

This avoids introducing a full retrieval stack while still improving relevance and reducing prompt waste.

### 3. Short-answer prompting

The current prompt already asks for concise answers but still allows longer completions than needed.

The new prompting behavior will:

- require a short answer with at most 2-4 bullet-like points when answerable
- require a strict refusal when evidence is insufficient
- prefer evidence-grounded wording over explanatory expansion
- reduce default generation length during evaluation

Expected answer shape:

- one direct conclusion sentence
- short enumerated key points
- short citation line if evidence references are available

## Detailed Changes

### `backend/scripts/training/prepare_local_corpus.py`

- Add TXT heading/chapter detection helpers.
- Add paragraph-based fallback sectioning for long plain text.
- Change `normalize_text_source()` to emit structured markdown sections for long TXT.
- Keep encoding fallback behavior already added in the previous pass.

### `backend/scripts/training/build_qlora_dataset.py`

- Extend markdown parsing utilities so evidence can be selected below the top-level section granularity.
- Add PDF/TXT evidence block extraction helpers.
- Add a lightweight block scorer based on:
  - question term overlap
  - heading term overlap
  - source block density / anti-noise heuristics
- Build evidence from top-ranked blocks instead of entire giant sections when appropriate.
- Preserve existing annotation format so current sample JSON remains valid.

### `backend/scripts/training/run_lora_inference.py`

- Tighten system/user instruction text for answer length and refusal discipline.
- Lower default output length for evaluation runs.
- Keep CLI compatibility for base-only and adapter-based runs.

### Tests

Add/extend tests for:

- long TXT chapter splitting
- fallback TXT sectioning without explicit chapters
- PDF block denoising and selection
- rerank behavior returning the most relevant blocks
- prompt rendering and output-length defaults

## Error Handling

- If TXT structure detection is weak, fall back to paragraph grouping instead of failing normalization.
- If evidence block ranking finds no strong candidate, fall back to the original section text trimmed to safe size.
- If PDF page parsing is ambiguous, preserve the current page section behavior as a compatibility fallback.

## Validation Plan

- Unit tests for the new helpers and changed evidence behavior.
- `python -m compileall backend/app backend/scripts/training`
- Rebuild the local normalized corpus in the manual eval workspace.
- Re-run base and LoRA inference on the same 36-sample evaluation set.
- Compare:
  - overall `answer_overlap`
  - PDF subset `answer_overlap`
  - TXT subset `answer_overlap`
  - long-novel failure cases

## Expected Outcome

- Long TXT should stop collapsing into single mega-evidence blocks.
- PDF prompts should contain less directory/header noise.
- LoRA should retain high refusal precision while improving answer overlap on weak samples.
- The optimized pipeline should become a better candidate for later backend integration.

## Notes

- I am intentionally not creating a worktree or git commit as part of this step because the current session instructions explicitly forbid creating branches or commits unless requested.
