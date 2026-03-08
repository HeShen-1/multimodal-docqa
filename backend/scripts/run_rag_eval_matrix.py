from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_rag_eval_baseline import evaluate, load_json


def render_markdown(rows: list[dict]) -> str:
    header = [
        "# RAG Experiment Matrix",
        "",
        "| 实验组 | 文档命中率 | 引用准确率 | 拒答准确率 | 主观相关性 | 平均时延(ms) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    body = [
        "| {experiment} | {document_hit_rate:.4f} | {citation_precision:.4f} | {no_answer_precision:.4f} | {avg_manual_relevance:.4f} | {avg_latency_ms:.2f} |".format(
            **row
        )
        for row in rows
    ]
    return "\n".join(header + body + [""])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a comparison matrix from multiple RAG result files.")
    parser.add_argument("--dataset", default="scripts/evaluation/rag_eval_dataset.json")
    parser.add_argument("--matrix", required=True, help="JSON file containing experiment/result file mappings.")
    parser.add_argument("--output", required=True, help="Markdown output path.")
    args = parser.parse_args()

    dataset = load_json(Path(args.dataset))
    matrix_entries = load_json(Path(args.matrix))
    rows = []

    for entry in matrix_entries:
        results = load_json(Path(entry["results"]))
        metrics = evaluate(dataset, results)
        rows.append(
            {
                "experiment": entry["experiment"],
                **metrics,
            }
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(rows), encoding="utf-8")
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
