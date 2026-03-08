from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(mean(values), 4)


def markdown_report(experiment: str, metrics: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# RAG Eval Report - {experiment}",
            "",
            f"- total_samples: {metrics['total_samples']}",
            f"- covered_samples: {metrics['covered_samples']}",
            f"- document_hit_rate: {metrics['document_hit_rate']}",
            f"- citation_precision: {metrics['citation_precision']}",
            f"- no_answer_precision: {metrics['no_answer_precision']}",
            f"- avg_manual_relevance: {metrics['avg_manual_relevance']}",
            f"- avg_latency_ms: {metrics['avg_latency_ms']}",
        ]
    )


def evaluate(dataset: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    result_map = {item["id"]: item for item in results}
    doc_hits: list[float] = []
    citation_scores: list[float] = []
    no_answer_scores: list[float] = []
    relevance_scores: list[float] = []
    latencies: list[float] = []
    covered = 0

    for sample in dataset:
        result = result_map.get(sample["id"])
        if not result:
            continue
        covered += 1

        expected_docs = set(sample.get("target_documents", []))
        retrieved_docs = set(result.get("retrieved_documents", []))
        doc_hits.append(1.0 if not expected_docs or expected_docs & retrieved_docs else 0.0)

        citations = result.get("citations", [])
        expected_evidence = set(sample.get("expected_evidence", []))
        if "citation_correct" in result:
            citation_scores.append(float(result["citation_correct"]))
        elif not citations:
            citation_scores.append(1.0 if not expected_evidence else 0.0)
        else:
            matched = sum(1 for citation in citations if citation in expected_evidence)
            citation_scores.append(round(matched / len(citations), 4))

        predicted_no_answer = bool(result.get("predicted_no_answer", False))
        allow_no_answer = bool(sample.get("allow_no_answer", False))
        no_answer_scores.append(1.0 if predicted_no_answer == allow_no_answer else 0.0)

        relevance_scores.append(float(result.get("manual_relevance", 0.0)))
        latencies.append(float(result.get("latency_ms", 0.0)))

    return {
        "total_samples": len(dataset),
        "covered_samples": covered,
        "document_hit_rate": safe_mean(doc_hits),
        "citation_precision": safe_mean(citation_scores),
        "no_answer_precision": safe_mean(no_answer_scores),
        "avg_manual_relevance": safe_mean(relevance_scores),
        "avg_latency_ms": round(mean(latencies), 2) if latencies else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate RAG retrieval experiment metrics from result JSON.")
    parser.add_argument("--dataset", default="scripts/evaluation/rag_eval_dataset.json")
    parser.add_argument("--results", required=True, help="Path to experiment result json.")
    parser.add_argument("--experiment", required=True, help="Experiment name, e.g. vector / hybrid / hybrid_reranker.")
    parser.add_argument("--output", help="Optional path for markdown report.")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    results_path = Path(args.results)
    dataset = load_json(dataset_path)
    results = load_json(results_path)
    metrics = evaluate(dataset, results)

    print(json.dumps({"experiment": args.experiment, "metrics": metrics}, ensure_ascii=False, indent=2))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown_report(args.experiment, metrics), encoding="utf-8")


if __name__ == "__main__":
    main()
