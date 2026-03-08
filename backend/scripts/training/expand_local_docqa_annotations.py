from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from scripts.training.build_qlora_dataset import extract_markdown_sections
from scripts.training.docqa_workspace import default_workspace_root, ensure_docqa_workspace
from scripts.training.prepare_local_corpus import load_normalized_documents

ANSWERABLE_QUESTION_TEMPLATES = (
    "{heading}主要讲了什么？",
    "根据文档，{heading}包含哪些关键要点？",
    "文档如何解释{heading}？",
    "{heading}的核心内容是什么？",
    "围绕{heading}，文档强调了哪些重点？",
)

REJECTABLE_TOPICS = (
    ("官方 GitHub 仓库地址", ("github", "gitlab")),
    ("完整数据集下载链接", ("huggingface", "modelscope", "下载", "链接", "http://", "https://")),
    ("线上 API 默认端口号", ("端口", "port", ":8000", ":8080", "api")),
    ("商业许可证条款", ("license", "许可证", "授权")),
    ("公开 benchmark 分数", ("benchmark", "准确率", "f1", "bleu", "rouge")),
    ("GPU 显存需求数值", ("显存", "gpu", "cuda", "gb")),
    ("作者邮箱联系方式", ("邮箱", "email", "@")),
    ("完整超参数配置表", ("超参数", "learning rate", "batch size", "学习率", "batch")),
)

MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\([^)]+\)")
MARKDOWN_EMPHASIS_PATTERN = re.compile(r"[*_`>#]+")
MULTISPACE_PATTERN = re.compile(r"\s+")
ID_PATTERN = re.compile(r"^(?P<stem>.+)-(?P<kind>answerable|rejectable)-(?P<index>\d+)$")


def load_annotations(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_annotations(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_text(text: str) -> str:
    text = MARKDOWN_LINK_PATTERN.sub(r"\1", text)
    text = MARKDOWN_EMPHASIS_PATTERN.sub(" ", text)
    text = text.replace("|", " ").replace("—", " ").replace("：", "：")
    text = MULTISPACE_PATTERN.sub(" ", text)
    return text.strip(" -\t\r\n")


def split_answer_points(section_text: str, max_points: int = 4) -> list[str]:
    candidates: list[str] = []
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("```", "~~~")):
            continue
        if re.match(r"^[-*+]\s+", line) or re.match(r"^\d+[.)、]\s*", line):
            cleaned = normalize_text(re.sub(r"^([-*+]|\d+[.)、])\s*", "", line))
            if cleaned:
                candidates.append(cleaned)

    if not candidates:
        split_parts = re.split(r"[。！？；;\n]", section_text)
        for part in split_parts:
            cleaned = normalize_text(part)
            if len(cleaned) >= 4:
                candidates.append(cleaned)

    unique_points: list[str] = []
    seen: set[str] = set()
    for point in candidates:
        if len(point) > 80:
            point = point[:80].rstrip("，,;；:： ")
        if point and point not in seen:
            unique_points.append(point)
            seen.add(point)
        if len(unique_points) >= max_points:
            break
    return unique_points


def parse_existing_indexes(records: list[dict[str, Any]], filename: str, kind: str) -> int:
    stem = Path(filename).stem
    indexes = []
    for record in records:
        match = ID_PATTERN.match(str(record.get("id", "")))
        if not match:
            continue
        if match.group("stem") == stem and match.group("kind") == kind:
            indexes.append(int(match.group("index")))
    return max(indexes, default=0)


def choose_rejectable_questions(title: str, content: str, count: int, existing_questions: set[str]) -> list[str]:
    lower_content = content.lower()
    questions: list[str] = []
    for topic, keywords in REJECTABLE_TOPICS:
        if any(keyword in lower_content for keyword in keywords):
            continue
        question = f"文档是否给出了《{title}》相关的{topic}？"
        if question in existing_questions:
            continue
        questions.append(question)
        if len(questions) >= count:
            return questions

    fallback_topics = (
        "官方课程视频链接",
        "完整实验环境下载包",
        "逐项成本预算表",
        "默认线上服务 SLA 指标",
    )
    for topic in fallback_topics:
        question = f"文档是否给出了《{title}》相关的{topic}？"
        if question in existing_questions:
            continue
        questions.append(question)
        if len(questions) >= count:
            break
    return questions


def generate_answerable_records(
    filename: str,
    content: str,
    existing_records: list[dict[str, Any]],
    target_count: int,
) -> list[dict[str, Any]]:
    current_answerable = [record for record in existing_records if not record.get("allow_no_answer", False)]
    missing = target_count - len(current_answerable)
    if missing <= 0:
        return []

    sections = extract_markdown_sections(content)
    used_refs = {
        ref
        for record in current_answerable
        for ref in record.get("expected_evidence", [])
        if isinstance(ref, str) and ref.startswith(f"{filename}#")
    }
    title = next(iter(sections), Path(filename).stem)
    next_index = parse_existing_indexes(existing_records, filename, "answerable") + 1
    generated: list[dict[str, Any]] = []

    fallback_sections: list[tuple[str, list[str]]] = []
    for heading, section_text in sections.items():
        evidence_ref = f"{filename}#{heading}"
        answer_points = split_answer_points(section_text)
        if not answer_points:
            continue
        fallback_sections.append((heading, answer_points))
        if evidence_ref in used_refs:
            continue

        template = ANSWERABLE_QUESTION_TEMPLATES[(next_index - 1) % len(ANSWERABLE_QUESTION_TEMPLATES)]
        question_heading = heading or title
        generated.append(
            {
                "id": f"{Path(filename).stem}-answerable-{next_index:03d}",
                "question": template.format(heading=question_heading),
                "target_documents": [filename],
                "expected_evidence": [evidence_ref],
                "expected_answer_points": answer_points,
                "allow_no_answer": False,
            }
        )
        next_index += 1
        if len(generated) >= missing:
            break

    fallback_index = 0
    while len(generated) < missing and fallback_sections:
        heading, answer_points = fallback_sections[fallback_index % len(fallback_sections)]
        evidence_ref = f"{filename}#{heading}"
        template = ANSWERABLE_QUESTION_TEMPLATES[(next_index - 1) % len(ANSWERABLE_QUESTION_TEMPLATES)]
        generated.append(
            {
                "id": f"{Path(filename).stem}-answerable-{next_index:03d}",
                "question": template.format(heading=heading or title),
                "target_documents": [filename],
                "expected_evidence": [evidence_ref],
                "expected_answer_points": answer_points,
                "allow_no_answer": False,
            }
        )
        next_index += 1
        fallback_index += 1

    return generated


def generate_rejectable_records(
    filename: str,
    content: str,
    existing_records: list[dict[str, Any]],
    target_count: int,
) -> list[dict[str, Any]]:
    current_rejectable = [record for record in existing_records if record.get("allow_no_answer", False)]
    missing = target_count - len(current_rejectable)
    if missing <= 0:
        return []

    sections = extract_markdown_sections(content)
    title = next(iter(sections), Path(filename).stem)
    next_index = parse_existing_indexes(existing_records, filename, "rejectable") + 1
    existing_questions = {str(record.get("question", "")).strip() for record in existing_records}
    questions = choose_rejectable_questions(title=title, content=content, count=missing, existing_questions=existing_questions)

    return [
        {
            "id": f"{Path(filename).stem}-rejectable-{next_index + offset:03d}",
            "question": question,
            "target_documents": [filename],
            "expected_evidence": [],
            "expected_answer_points": [],
            "allow_no_answer": True,
        }
        for offset, question in enumerate(questions)
    ]


def expand_annotations(
    existing_records: list[dict[str, Any]],
    documents: dict[str, str],
    *,
    answerable_target_per_doc: int = 8,
    rejectable_target_per_doc: int = 2,
) -> list[dict[str, Any]]:
    records_by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in existing_records:
        target_documents = record.get("target_documents", [])
        if len(target_documents) != 1:
            continue
        records_by_doc[target_documents[0]].append(record)

    expanded: list[dict[str, Any]] = []
    for filename, content in sorted(documents.items()):
        doc_records = list(records_by_doc.get(filename, []))
        doc_records.extend(
            generate_answerable_records(
                filename=filename,
                content=content,
                existing_records=doc_records,
                target_count=answerable_target_per_doc,
            )
        )
        doc_records.extend(
            generate_rejectable_records(
                filename=filename,
                content=content,
                existing_records=doc_records,
                target_count=rejectable_target_per_doc,
            )
        )
        expanded.extend(sorted(doc_records, key=lambda item: item["id"]))
    return expanded


def main() -> None:
    parser = argparse.ArgumentParser(description="Expand local DocQA annotations from normalized markdown documents.")
    parser.add_argument("--workspace-root", default=str(default_workspace_root()))
    parser.add_argument("--input", help="Input annotation JSON path. Defaults to the workspace seed annotation file.")
    parser.add_argument("--output", help="Output annotation JSON path. Defaults to overwriting the input file.")
    parser.add_argument("--answerable-target-per-doc", type=int, default=8)
    parser.add_argument("--rejectable-target-per-doc", type=int, default=2)
    args = parser.parse_args()

    paths = ensure_docqa_workspace(Path(args.workspace_root))
    input_path = Path(args.input) if args.input else paths["annotations"] / "local_docqa_seed_v1.json"
    output_path = Path(args.output) if args.output else input_path
    documents = load_normalized_documents(paths["local_norm_docs"])
    existing_records = load_annotations(input_path)
    expanded = expand_annotations(
        existing_records=existing_records,
        documents=documents,
        answerable_target_per_doc=args.answerable_target_per_doc,
        rejectable_target_per_doc=args.rejectable_target_per_doc,
    )
    write_annotations(output_path, expanded)
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "documents": len(documents),
                "records": len(expanded),
                "answerable_target_per_doc": args.answerable_target_per_doc,
                "rejectable_target_per_doc": args.rejectable_target_per_doc,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
