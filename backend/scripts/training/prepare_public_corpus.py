from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any, Iterable

from loguru import logger

from scripts.training.docqa_workspace import default_workspace_root, ensure_docqa_workspace


class PublicCorpusDependencyError(RuntimeError):
    pass


PUBLIC_SYSTEM_PROMPT = "你是中文问答助手。请提供准确、简洁、克制的回答。"
CREATIVE_KEYWORDS = (
    "写一首诗",
    "诗歌",
    "角色扮演",
    "扮演",
    "小说",
    "故事",
    "剧本",
    "文案",
    "润色",
    "翻译",
    "情书",
    "笑话",
    "poem",
    "roleplay",
    "story",
    "novel",
)
COIG_DISALLOWED_TASK_KEYWORDS = (
    "创作",
    "角色",
    "文学",
    "情感",
    "主观",
    "推荐",
    "闲聊",
    "chat",
)
DEFAULT_COIG_CONFIGS = (
    "chinese_traditional",
    "coig_pc",
    "exam",
    "wiki",
    "zhihu",
    "segmentfault",
    "logi_qa",
)


def clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chinese_ratio(text: str) -> float:
    normalized = clean_text(text)
    if not normalized:
        return 0.0

    meaningful = [char for char in normalized if char.isalpha() or char.isdigit() or "\u4e00" <= char <= "\u9fff"]
    if not meaningful:
        return 0.0

    chinese_chars = [char for char in meaningful if "\u4e00" <= char <= "\u9fff"]
    return len(chinese_chars) / len(meaningful)


def is_mostly_chinese(text: str, threshold: float = 0.7) -> bool:
    return chinese_ratio(text) >= threshold


def contains_disallowed_keywords(text: str, keywords: Iterable[str]) -> bool:
    haystack = clean_text(text).lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def iter_answers(candidate: Any) -> Iterable[str]:
    if isinstance(candidate, str):
        answer = clean_text(candidate)
        if answer:
            yield answer
        return

    if isinstance(candidate, list):
        for item in candidate:
            answer = clean_text(item)
            if answer:
                yield answer


def build_public_record(record_id: str, question: str, answer: str, source_dataset: str, source_split: str) -> dict[str, Any]:
    return {
        "id": record_id,
        "source_dataset": source_dataset,
        "source_split": source_split,
        "messages": [
            {"role": "system", "content": PUBLIC_SYSTEM_PROMPT},
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ],
    }


def normalize_hc3_record(
    sample: dict[str, Any],
    record_id: str,
    max_prompt_chars: int = 512,
    max_answer_chars: int = 256,
) -> dict[str, Any] | None:
    question = clean_text(sample.get("question"))
    if not question or len(question) > max_prompt_chars:
        return None
    if not is_mostly_chinese(question):
        return None
    if contains_disallowed_keywords(question, CREATIVE_KEYWORDS):
        return None

    answer = next(iter_answers(sample.get("human_answers")), "")
    if not answer:
        answer = next(iter_answers(sample.get("chatgpt_answers")), "")
    if not answer or len(answer) > max_answer_chars:
        return None
    if not is_mostly_chinese(answer):
        return None
    if contains_disallowed_keywords(answer, CREATIVE_KEYWORDS):
        return None

    return build_public_record(record_id, question, answer, "HC3-Chinese", clean_text(sample.get("source")) or "train")


def normalize_coig_record(
    sample: dict[str, Any],
    record_id: str,
    max_prompt_chars: int = 512,
    max_answer_chars: int = 256,
) -> dict[str, Any] | None:
    instruction = clean_text(sample.get("instruction"))
    extra_input = clean_text(sample.get("input"))
    answer = clean_text(sample.get("output"))
    if not instruction or not answer:
        return None

    task_type = sample.get("task_type") or {}
    task_summary = " ".join(
        clean_text(task_type.get(key))
        for key in ("major", "minor")
        if clean_text(task_type.get(key))
    )
    domain = clean_text(sample.get("domain"))
    combined_meta = " ".join(part for part in (task_summary, domain, instruction) if part)
    if contains_disallowed_keywords(combined_meta, CREATIVE_KEYWORDS + COIG_DISALLOWED_TASK_KEYWORDS):
        return None

    question = instruction if not extra_input else f"{instruction}\n\n补充信息：\n{extra_input}"
    if len(question) > max_prompt_chars or len(answer) > max_answer_chars:
        return None
    if not is_mostly_chinese(question) or not is_mostly_chinese(answer):
        return None

    return build_public_record(record_id, question, answer, "COIG-CQIA", task_summary or domain or "train")


def dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_signatures: set[tuple[str, str]] = set()

    for record in records:
        user_message = next((item["content"] for item in record["messages"] if item["role"] == "user"), "")
        assistant_message = next((item["content"] for item in record["messages"] if item["role"] == "assistant"), "")
        signature = (user_message, assistant_message)
        if signature in seen_signatures:
            continue
        deduped.append(record)
        seen_signatures.add(signature)

    return deduped


def write_jsonl(records: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_dataset_from_huggingface(dataset_path: str, split: str, name: str | None = None, cache_dir: str | None = None):
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise PublicCorpusDependencyError(
            "Missing optional dependency 'datasets'. Run `pip install -r requirements-train.txt` in `backend/` first."
        ) from exc

    return load_dataset(dataset_path, name=name, split=split, cache_dir=cache_dir)


def _load_json_dataset(path: str, data_files: str, split: str, cache_dir: str | None = None):
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise PublicCorpusDependencyError(
            "Missing optional dependency 'datasets'. Run `pip install -r requirements-train.txt` in `backend/` first."
        ) from exc

    return load_dataset(path, data_files=data_files, split=split, cache_dir=cache_dir)


def _download_hf_dataset_file(repo_id: str, filename: str, cache_dir: str | None = None) -> str:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise PublicCorpusDependencyError(
            "Missing optional dependency 'huggingface_hub'. Run `pip install -r requirements-train.txt` in `backend/` first."
        ) from exc

    return hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        repo_type="dataset",
        cache_dir=cache_dir,
    )


def _list_hf_dataset_files(repo_id: str) -> list[str]:
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise PublicCorpusDependencyError(
            "Missing optional dependency 'huggingface_hub'. Run `pip install -r requirements-train.txt` in `backend/` first."
        ) from exc

    api = HfApi()
    return list(api.list_repo_files(repo_id=repo_id, repo_type="dataset"))


def load_hc3_dataset_from_huggingface_json(cache_dir: str | None = None):
    logger.info("Loading HC3-Chinese JSON export from Hugging Face")
    jsonl_path = _download_hf_dataset_file(
        repo_id="Hello-SimpleAI/HC3-Chinese",
        filename="all.jsonl",
        cache_dir=cache_dir,
    )
    return _load_json_dataset("json", data_files=jsonl_path, split="train", cache_dir=cache_dir)


def load_coig_dataset_from_huggingface_json(config_name: str, cache_dir: str | None = None):
    repo_id = "m-a-p/COIG-CQIA"
    logger.info("Loading COIG-CQIA JSON export from Hugging Face: {}", config_name)
    repo_files = _list_hf_dataset_files(repo_id)
    jsonl_files = sorted(
        filename
        for filename in repo_files
        if filename.startswith(f"{config_name}/") and filename.endswith(".jsonl")
    )
    if not jsonl_files:
        raise RuntimeError(f"No JSONL files found for COIG config: {config_name}")

    downloaded_files = [
        _download_hf_dataset_file(repo_id=repo_id, filename=filename, cache_dir=cache_dir)
        for filename in jsonl_files
    ]
    return _load_json_dataset("json", data_files=downloaded_files, split="train", cache_dir=cache_dir)


def _load_dataset_from_modelscope(dataset_path: str, split: str, name: str | None = None, cache_dir: str | None = None):
    try:
        from modelscope.msdatasets import MsDataset
    except ImportError as exc:
        raise PublicCorpusDependencyError(
            "Missing optional dependency 'modelscope'. Run `pip install -r requirements-train.txt` in `backend/` first."
        ) from exc

    dataset = MsDataset.load(dataset_path, subset_name=name, split=split, cache_dir=cache_dir)
    if hasattr(dataset, "to_hf_dataset"):
        return dataset.to_hf_dataset()
    return dataset


def load_dataset_with_fallback(
    huggingface_id: str,
    split: str,
    *,
    name: str | None = None,
    cache_dir: str | None = None,
    modelscope_id: str | None = None,
):
    try:
        logger.info("Loading dataset from Hugging Face: {} ({})", huggingface_id, name or split)
        return _load_dataset_from_huggingface(huggingface_id, split=split, name=name, cache_dir=cache_dir)
    except PublicCorpusDependencyError:
        raise
    except Exception as huggingface_error:
        if not modelscope_id:
            raise RuntimeError(f"Failed to load dataset from Hugging Face and no ModelScope fallback is configured: {huggingface_id}") from huggingface_error

        logger.warning("Hugging Face load failed for {}: {}", huggingface_id, huggingface_error)
        try:
            logger.info("Loading dataset from ModelScope: {} ({})", modelscope_id, name or split)
            return _load_dataset_from_modelscope(modelscope_id, split=split, name=name, cache_dir=cache_dir)
        except PublicCorpusDependencyError:
            raise
        except Exception as modelscope_error:
            raise RuntimeError(
                f"Failed to load dataset from both Hugging Face ({huggingface_id}) and ModelScope ({modelscope_id})."
            ) from modelscope_error


def _iter_records(dataset: Any) -> Iterable[dict[str, Any]]:
    for record in dataset:
        yield dict(record)


def export_public_dataset(
    dataset_name: str,
    records: list[dict[str, Any]],
    raw_output_path: Path,
    normalized_output_path: Path,
) -> None:
    write_jsonl(records, normalized_output_path)
    write_jsonl(records, raw_output_path)
    logger.info("Prepared {} records for {}", len(records), dataset_name)


def prepare_hc3_records(cache_dir: str | None, target_size: int) -> list[dict[str, Any]]:
    dataset = load_hc3_dataset_from_huggingface_json(cache_dir=cache_dir)
    normalized: list[dict[str, Any]] = []
    for index, sample in enumerate(_iter_records(dataset)):
        record = normalize_hc3_record(sample, f"hc3-{index:06d}")
        if record is None:
            continue
        normalized.append(record)
        if len(normalized) >= target_size:
            break
    return dedupe_records(normalized)


def prepare_coig_records(cache_dir: str | None, target_size: int) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for config_name in DEFAULT_COIG_CONFIGS:
        try:
            dataset = load_coig_dataset_from_huggingface_json(config_name, cache_dir=cache_dir)
        except (RuntimeError, PublicCorpusDependencyError) as exc:
            logger.warning("Skipping COIG config {}: {}", config_name, exc)
            continue

        for index, sample in enumerate(_iter_records(dataset)):
            record = normalize_coig_record(sample, f"coig-{config_name}-{index:06d}")
            if record is None:
                continue
            normalized.append(record)
            if len(normalized) >= target_size:
                return dedupe_records(normalized)

    return dedupe_records(normalized)


def prepare_public_corpus(workspace_root: Path, max_hc3: int = 900, max_coig: int = 600, cache_dir: str | None = None) -> dict[str, Any]:
    paths = ensure_docqa_workspace(workspace_root)
    hc3_records = prepare_hc3_records(cache_dir=cache_dir, target_size=max_hc3)
    coig_records = prepare_coig_records(cache_dir=cache_dir, target_size=max_coig)

    random.Random(42).shuffle(hc3_records)
    random.Random(43).shuffle(coig_records)

    hc3_output = paths["public_norm"] / "hc3_chinese.jsonl"
    coig_output = paths["public_norm"] / "coig_cqia.jsonl"
    export_public_dataset("HC3-Chinese", hc3_records, paths["public_raw"] / "hc3_chinese.jsonl", hc3_output)
    export_public_dataset("COIG-CQIA", coig_records, paths["public_raw"] / "coig_cqia.jsonl", coig_output)

    summary = {
        "workspace_root": str(workspace_root),
        "hc3_records": len(hc3_records),
        "coig_records": len(coig_records),
        "hc3_output": str(hc3_output),
        "coig_output": str(coig_output),
    }
    (paths["public_raw"] / "public_corpus_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and normalize public Chinese QA datasets for DocQA SFT.")
    parser.add_argument("--workspace-root", default=str(default_workspace_root()))
    parser.add_argument("--cache-dir", help="Optional datasets cache directory.")
    parser.add_argument("--max-hc3", type=int, default=900)
    parser.add_argument("--max-coig", type=int, default=600)
    args = parser.parse_args()

    summary = prepare_public_corpus(
        workspace_root=Path(args.workspace_root),
        max_hc3=args.max_hc3,
        max_coig=args.max_coig,
        cache_dir=args.cache_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
