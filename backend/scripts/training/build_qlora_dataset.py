from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SYSTEM_PROMPT = (
    "你是企业文档问答助手。你必须仅依据提供的证据回答，优先输出简洁、可引用、"
    "可验证的结论；如果证据不足，明确回答“未找到足够依据”，不要编造。"
)

REFUSAL_ANSWER = (
    "未找到足够依据。当前提供的文档片段中没有能直接回答该问题的明确信息，"
    "因此不应继续推断或编造答案。"
)

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_documents(directory: Path) -> dict[str, str]:
    documents: dict[str, str] = {}
    for path in sorted(directory.glob("*.md")):
        documents[path.name] = path.read_text(encoding="utf-8")
    return documents


def extract_markdown_sections(markdown: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_heading: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current_heading is None:
            return
        content = "\n".join(line.rstrip() for line in buffer).strip()
        if content:
            sections[current_heading] = content

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        match = HEADING_PATTERN.match(line)
        if match:
            flush()
            current_heading = match.group(2).strip()
            buffer = []
            continue
        if current_heading is not None:
            buffer.append(line)

    flush()
    return sections


def build_evidence_text(
    references: list[str],
    documents: dict[str, str],
    section_cache: dict[str, dict[str, str]] | None = None,
) -> str:
    if not references:
        return ""

    section_cache = section_cache or {}
    evidence_blocks: list[str] = []

    for reference in references:
        filename, _, heading = reference.partition("#")
        if filename not in documents:
            raise ValueError(f"Document not found for evidence reference: {reference}")
        if filename not in section_cache:
            section_cache[filename] = extract_markdown_sections(documents[filename])

        if not heading:
            section_text = documents[filename].strip()
        else:
            section_text = section_cache[filename].get(heading)
            if not section_text:
                raise ValueError(f"Heading not found for evidence reference: {reference}")

        evidence_blocks.append(f"[source] {reference}\n{section_text}")

    return "\n\n".join(evidence_blocks)


def build_ideal_answer(sample: dict[str, Any]) -> str:
    if sample.get("allow_no_answer"):
        return REFUSAL_ANSWER

    answer_points = [point.strip() for point in sample.get("expected_answer_points", []) if point and point.strip()]
    evidence_refs = sample.get("expected_evidence", [])

    if answer_points:
        answer = f"根据提供的文档证据，答案包括：{'、'.join(answer_points)}。"
    else:
        answer = "根据提供的文档证据，可以直接从证据片段中组织答案。"

    if evidence_refs:
        answer = f"{answer} 引用：{', '.join(evidence_refs)}。"

    return answer


def build_user_message(question: str, evidence_text: str) -> str:
    evidence_block = evidence_text if evidence_text else "（当前没有可用证据，若无法回答请明确拒答。）"
    return (
        f"问题：{question}\n\n"
        f"证据片段：\n{evidence_block}\n\n"
        "回答要求：\n"
        "1. 只能依据证据回答；\n"
        "2. 如果证据不足，回答“未找到足够依据”；\n"
        "3. 若能回答，请尽量简洁并保留引用。"
    )


def build_training_record(
    sample: dict[str, Any],
    documents: dict[str, str],
    section_cache: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    evidence_text = build_evidence_text(sample.get("expected_evidence", []), documents, section_cache=section_cache)
    ideal_answer = build_ideal_answer(sample)

    return {
        "id": sample["id"],
        "question": sample["question"],
        "target_documents": sample.get("target_documents", []),
        "expected_evidence": sample.get("expected_evidence", []),
        "evidence": evidence_text,
        "ideal_answer": ideal_answer,
        "rejectable": bool(sample.get("allow_no_answer", False)),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(sample["question"], evidence_text)},
            {"role": "assistant", "content": ideal_answer},
        ],
    }


def build_training_records(
    dataset: list[dict[str, Any]],
    documents: dict[str, str],
) -> list[dict[str, Any]]:
    section_cache: dict[str, dict[str, str]] = {}
    return [build_training_record(sample, documents, section_cache=section_cache) for sample in dataset]


def write_jsonl(records: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build lightweight QLoRA SFT dataset from the RAG eval set.")
    parser.add_argument(
        "--dataset",
        default="scripts/evaluation/rag_eval_dataset.json",
        help="Path to the eval dataset JSON.",
    )
    parser.add_argument(
        "--docs-dir",
        default="scripts/evaluation/sample_docs",
        help="Directory containing markdown source documents.",
    )
    parser.add_argument(
        "--output",
        default="scripts/training/data/qlora_train_template.jsonl",
        help="Output JSONL path.",
    )
    args = parser.parse_args()

    dataset = load_json(Path(args.dataset))
    documents = load_documents(Path(args.docs_dir))
    records = build_training_records(dataset, documents)
    write_jsonl(records, Path(args.output))
    print(json.dumps({"records": len(records), "output": args.output}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
