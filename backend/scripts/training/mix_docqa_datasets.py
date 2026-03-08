from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any

from scripts.training.docqa_workspace import default_workspace_root, ensure_docqa_workspace


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def write_jsonl(records: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def split_local_docqa_records(
    records: list[dict[str, Any]],
    validation_ratio: float = 0.1,
    test_ratio: float = 0.1,
    seed: int = 42,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)

    validation_count = int(round(len(shuffled) * validation_ratio))
    test_count = int(round(len(shuffled) * test_ratio))
    if len(shuffled) >= 10:
        validation_count = max(validation_count, 1)
        test_count = max(test_count, 1)

    validation_records = shuffled[:validation_count]
    test_records = shuffled[validation_count : validation_count + test_count]
    train_records = shuffled[validation_count + test_count :]
    return train_records, validation_records, test_records


def ensure_source_dataset(record: dict[str, Any], source_dataset: str) -> dict[str, Any]:
    normalized = dict(record)
    normalized.setdefault("source_dataset", source_dataset)
    return normalized


def repeat_records_to_target(records: list[dict[str, Any]], target_size: int, max_repeat: int = 3) -> list[dict[str, Any]]:
    if not records:
        raise ValueError("Cannot repeat an empty record list.")
    if target_size > len(records) * max_repeat:
        raise ValueError(
            f"Target size {target_size} exceeds repeat limit {max_repeat}x for {len(records)} records "
            f"(max {len(records) * max_repeat})."
        )

    repeated: list[dict[str, Any]] = []
    repeat_index = 0
    while len(repeated) < target_size:
        for record in records:
            if len(repeated) >= target_size:
                break
            item = dict(record)
            if repeat_index > 0:
                item["id"] = f"{item['id']}__dup{repeat_index}"
            repeated.append(item)
        repeat_index += 1
    return repeated


def sample_records(records: list[dict[str, Any]], target_size: int, seed: int) -> list[dict[str, Any]]:
    if len(records) < target_size:
        raise ValueError(f"Not enough records to sample {target_size} items.")
    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)
    return shuffled[:target_size]


def _count_local_split_sizes(
    record_count: int,
    validation_ratio: float = 0.1,
    test_ratio: float = 0.1,
) -> tuple[int, int, int]:
    validation_count = int(round(record_count * validation_ratio))
    test_count = int(round(record_count * test_ratio))
    if record_count >= 10:
        validation_count = max(validation_count, 1)
        test_count = max(test_count, 1)

    train_count = max(record_count - validation_count - test_count, 0)
    return train_count, validation_count, test_count


def minimum_local_records_for_target(
    local_target: int,
    *,
    max_repeat: int = 3,
    validation_ratio: float = 0.1,
    test_ratio: float = 0.1,
) -> int:
    minimum_guess = max(1, math.ceil(local_target / max_repeat))
    total_records = minimum_guess
    while True:
        train_count, _, _ = _count_local_split_sizes(
            total_records,
            validation_ratio=validation_ratio,
            test_ratio=test_ratio,
        )
        if train_count * max_repeat >= local_target:
            return total_records
        total_records += 1


def validate_local_target_capacity(
    total_local_records: int,
    train_local_records: int,
    local_target: int,
    *,
    max_repeat: int = 3,
    validation_ratio: float = 0.1,
    test_ratio: float = 0.1,
) -> None:
    max_feasible_local_target = train_local_records * max_repeat
    if local_target <= max_feasible_local_target:
        return

    minimum_required_total = minimum_local_records_for_target(
        local_target,
        max_repeat=max_repeat,
        validation_ratio=validation_ratio,
        test_ratio=test_ratio,
    )
    raise ValueError(
        "Local grounded dataset is too small for the configured local target: "
        f"{total_local_records} total records -> {train_local_records} train records after local split; "
        f"with repeat limit {max_repeat}x, max feasible local target is {max_feasible_local_target}. "
        f"Add more local grounded samples until you reach at least {minimum_required_total} total local records, "
        f"or rerun a smoke build with --local-target {max_feasible_local_target}."
    )


def build_mixed_training_records(
    local_records: list[dict[str, Any]],
    hc3_records: list[dict[str, Any]],
    coig_records: list[dict[str, Any]],
    *,
    local_target: int = 900,
    hc3_target: int = 900,
    coig_target: int = 600,
    seed: int = 42,
) -> list[dict[str, Any]]:
    local_prepared = [ensure_source_dataset(record, "local_docqa") for record in local_records]
    hc3_prepared = [ensure_source_dataset(record, "HC3-Chinese") for record in hc3_records]
    coig_prepared = [ensure_source_dataset(record, "COIG-CQIA") for record in coig_records]

    mixed = []
    mixed.extend(repeat_records_to_target(local_prepared, local_target, max_repeat=3))
    mixed.extend(sample_records(hc3_prepared, hc3_target, seed=seed + 1))
    mixed.extend(sample_records(coig_prepared, coig_target, seed=seed + 2))
    random.Random(seed).shuffle(mixed)
    return mixed


def mix_workspace_datasets(
    workspace_root: Path,
    *,
    local_grounded_path: Path,
    hc3_path: Path,
    coig_path: Path,
    local_target: int = 900,
    hc3_target: int = 900,
    coig_target: int = 600,
    seed: int = 42,
) -> dict[str, Any]:
    paths = ensure_docqa_workspace(workspace_root)

    local_records = [ensure_source_dataset(record, "local_docqa") for record in load_jsonl(local_grounded_path)]
    hc3_records = load_jsonl(hc3_path)
    coig_records = load_jsonl(coig_path)

    local_train, local_validation, local_test = split_local_docqa_records(local_records, seed=seed)
    validate_local_target_capacity(
        total_local_records=len(local_records),
        train_local_records=len(local_train),
        local_target=local_target,
    )
    train_records = build_mixed_training_records(
        local_records=local_train,
        hc3_records=hc3_records,
        coig_records=coig_records,
        local_target=local_target,
        hc3_target=hc3_target,
        coig_target=coig_target,
        seed=seed,
    )

    train_path = paths["prepared"] / "train_mixed.jsonl"
    validation_path = paths["prepared"] / "validation_local_docqa.jsonl"
    test_path = paths["prepared"] / "test_local_docqa.jsonl"
    write_jsonl(train_records, train_path)
    write_jsonl(local_validation, validation_path)
    write_jsonl(local_test, test_path)
    write_jsonl(local_test, paths["eval"] / "local_docqa_holdout.jsonl")

    summary = {
        "workspace_root": str(workspace_root),
        "train_records": len(train_records),
        "validation_records": len(local_validation),
        "test_records": len(local_test),
        "train_path": str(train_path),
        "validation_path": str(validation_path),
        "test_path": str(test_path),
    }
    (paths["prepared"] / "dataset_mix_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Mix local grounded DocQA data with public Chinese QA corpora.")
    parser.add_argument("--workspace-root", default=str(default_workspace_root()))
    parser.add_argument("--local-grounded-path", default="scripts/training/data/docqa_workspace/prepared/local_docqa_grounded.jsonl")
    parser.add_argument("--hc3-path", default="scripts/training/data/docqa_workspace/public_norm/hc3_chinese.jsonl")
    parser.add_argument("--coig-path", default="scripts/training/data/docqa_workspace/public_norm/coig_cqia.jsonl")
    parser.add_argument("--local-target", type=int, default=900)
    parser.add_argument("--hc3-target", type=int, default=900)
    parser.add_argument("--coig-target", type=int, default=600)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    summary = mix_workspace_datasets(
        workspace_root=Path(args.workspace_root),
        local_grounded_path=Path(args.local_grounded_path),
        hc3_path=Path(args.hc3_path),
        coig_path=Path(args.coig_path),
        local_target=args.local_target,
        hc3_target=args.hc3_target,
        coig_target=args.coig_target,
        seed=args.seed,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
