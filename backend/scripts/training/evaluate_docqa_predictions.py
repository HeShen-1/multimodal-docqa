from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REFUSAL_PHRASES = (
    "未找到足够依据",
    "没有足够依据",
    "暂无足够证据",
    "无法从提供的文档中找到",
    "无法根据当前文档确定",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def infer_predicted_no_answer(answer: str) -> bool:
    normalized = str(answer or "").strip()
    return any(phrase in normalized for phrase in REFUSAL_PHRASES)


def char_overlap_score(reference: str, prediction: str) -> float:
    reference_chars = [char for char in str(reference) if not char.isspace()]
    prediction_chars = [char for char in str(prediction) if not char.isspace()]
    if not reference_chars and not prediction_chars:
        return 1.0
    if not reference_chars or not prediction_chars:
        return 0.0

    matches = 0
    remaining_reference = reference_chars.copy()
    for char in prediction_chars:
        if char in remaining_reference:
            matches += 1
            remaining_reference.remove(char)

    precision = matches / len(prediction_chars)
    recall = matches / len(reference_chars)
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def evaluate_predictions(
    ground_truth_records: list[dict[str, Any]],
    prediction_records: list[dict[str, Any]],
) -> dict[str, Any]:
    prediction_map = {item["id"]: item for item in prediction_records}
    covered = 0
    no_answer_scores: list[float] = []
    answer_overlap_scores: list[float] = []

    for record in ground_truth_records:
        prediction = prediction_map.get(record["id"])
        if not prediction:
            continue
        covered += 1

        answer = str(prediction.get("answer", ""))
        predicted_no_answer = infer_predicted_no_answer(answer)
        rejectable = bool(record.get("rejectable", False))
        no_answer_scores.append(1.0 if predicted_no_answer == rejectable else 0.0)

        if not rejectable:
            answer_overlap_scores.append(char_overlap_score(record.get("ideal_answer", ""), answer))

    return {
        "total_samples": len(ground_truth_records),
        "covered_samples": covered,
        "no_answer_precision": round(sum(no_answer_scores) / len(no_answer_scores), 4) if no_answer_scores else 0.0,
        "answer_overlap": round(sum(answer_overlap_scores) / len(answer_overlap_scores), 4) if answer_overlap_scores else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate local DocQA predictions against grounded references.")
    parser.add_argument("--ground-truth", required=True, help="Path to JSONL with grounded local test samples.")
    parser.add_argument("--predictions", required=True, help="Path to JSONL with model answers.")
    parser.add_argument("--output", help="Optional path to save a JSON summary.")
    args = parser.parse_args()

    metrics = evaluate_predictions(load_jsonl(Path(args.ground_truth)), load_jsonl(Path(args.predictions)))
    print(json.dumps(metrics, ensure_ascii=False, indent=2))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
