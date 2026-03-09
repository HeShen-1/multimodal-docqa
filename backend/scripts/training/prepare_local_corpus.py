from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Any

from loguru import logger

from app.services.document_processor import DocumentProcessor
from scripts.training.build_qlora_dataset import extract_markdown_sections
from scripts.training.docqa_workspace import default_workspace_root, ensure_docqa_workspace


SUPPORTED_LOCAL_EXTENSIONS = {
    ".pdf",
    ".md",
    ".docx",
    ".doc",
    ".txt",
    ".log",
    ".ini",
    ".yaml",
    ".yml",
    ".csv",
    ".tsv",
    ".json",
    ".jsonl",
    ".html",
    ".htm",
    ".xml",
}

TEXT_SOURCE_ENCODINGS = ("utf-8", "utf-8-sig", "gb18030")
PLAIN_TEXT_SECTION_TARGET_CHARS = 1200
PLAIN_TEXT_SECTION_TRIGGER_CHARS = 900
PLAIN_TEXT_HEADING_PATTERNS = (
    re.compile(r"^第\s*[0-9零一二三四五六七八九十百千两]+\s*[章节卷篇回部集]\s*.*$"),
    re.compile(r"^(chapter|part)\s+\d+\b.*$", re.IGNORECASE),
    re.compile(r"^\d+(?:\.\d+){0,2}[、.．]\s*\S.*$"),
)


def slugify_document_name(path: Path) -> str:
    stem = path.stem.strip() or "document"
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", stem)
    return slug.strip("_") or "document"


def read_text_source(path: Path) -> str:
    for encoding in TEXT_SOURCE_ENCODINGS:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    try:
        return path.read_text(encoding="gb18030", errors="replace")
    except UnicodeDecodeError:
        pass
    return path.read_text(encoding="latin-1")


def normalize_plain_text_content(content: str, title: str) -> str:
    normalized = normalize_plain_text_body(content)
    if not normalized:
        return f"# {title}\n"

    paragraphs = split_plain_text_paragraphs(normalized)
    sections = build_structured_text_sections(paragraphs)
    if not sections:
        return f"# {title}\n\n{normalized}\n"

    lines = [f"# {title}", ""]
    for heading, body in sections:
        lines.append(f"## {heading}")
        lines.append("")
        lines.append(body)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def normalize_plain_text_body(content: str) -> str:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n").replace("\ufeff", "")
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def split_plain_text_paragraphs(content: str) -> list[str]:
    paragraphs: list[str] = []
    for raw_block in re.split(r"\n\s*\n+", content):
        block = raw_block.strip()
        if not block:
            continue

        current_lines: list[str] = []
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if is_plain_text_heading(line):
                if current_lines:
                    paragraphs.append("\n".join(current_lines).strip())
                    current_lines = []
                paragraphs.append(line)
            else:
                current_lines.append(line)

        if current_lines:
            paragraphs.append("\n".join(current_lines).strip())

    return paragraphs


def build_structured_text_sections(paragraphs: list[str]) -> list[tuple[str, str]]:
    if not paragraphs:
        return []

    explicit_sections = build_explicit_heading_sections(paragraphs)
    if explicit_sections:
        return explicit_sections

    combined_length = sum(len(paragraph) for paragraph in paragraphs)
    if combined_length < PLAIN_TEXT_SECTION_TRIGGER_CHARS:
        return [("Content", "\n\n".join(paragraphs))]

    return build_fallback_length_sections(paragraphs)


def build_explicit_heading_sections(paragraphs: list[str]) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    preface: list[str] = []
    current_heading: str | None = None
    current_paragraphs: list[str] = []

    for paragraph in paragraphs:
        if is_plain_text_heading(paragraph):
            if current_heading and current_paragraphs:
                sections.extend(split_large_text_section(current_heading, current_paragraphs))
            elif current_heading and not current_paragraphs:
                sections.append((current_heading, ""))
            current_heading = paragraph
            current_paragraphs = []
            continue

        if current_heading is None:
            preface.append(paragraph)
        else:
            current_paragraphs.append(paragraph)

    if current_heading and current_paragraphs:
        sections.extend(split_large_text_section(current_heading, current_paragraphs))
    elif current_heading and not current_paragraphs:
        sections.append((current_heading, ""))

    if not sections:
        return []

    if preface:
        first_heading, first_body = sections[0]
        merged = "\n\n".join(preface + ([first_body] if first_body else []))
        sections[0] = (first_heading, merged)

    return [(heading, body.strip()) for heading, body in sections if body.strip()]


def is_plain_text_heading(paragraph: str) -> bool:
    text = paragraph.strip()
    if not text or "\n" in text or len(text) > 80:
        return False
    return any(pattern.match(text) for pattern in PLAIN_TEXT_HEADING_PATTERNS)


def split_large_text_section(heading: str, paragraphs: list[str]) -> list[tuple[str, str]]:
    grouped_paragraphs = group_paragraphs_by_length(paragraphs, target_chars=PLAIN_TEXT_SECTION_TARGET_CHARS)
    sections: list[tuple[str, str]] = []
    for index, group in enumerate(grouped_paragraphs, start=1):
        if len(grouped_paragraphs) == 1:
            title = heading
        else:
            title = f"{heading}（续{index}）"
        sections.append((title, "\n\n".join(group).strip()))
    return sections


def build_fallback_length_sections(paragraphs: list[str]) -> list[tuple[str, str]]:
    groups = group_paragraphs_by_length(paragraphs, target_chars=PLAIN_TEXT_SECTION_TARGET_CHARS)
    return [(f"Section {index}", "\n\n".join(group).strip()) for index, group in enumerate(groups, start=1)]


def group_paragraphs_by_length(paragraphs: list[str], *, target_chars: int) -> list[list[str]]:
    groups: list[list[str]] = []
    current_group: list[str] = []
    current_length = 0

    for paragraph in paragraphs:
        paragraph_length = len(paragraph)
        if current_group and current_length + paragraph_length > target_chars:
            groups.append(current_group)
            current_group = []
            current_length = 0
        current_group.append(paragraph)
        current_length += paragraph_length

    if current_group:
        groups.append(current_group)

    return groups


def render_processed_document_as_markdown(source_name: str, processed: dict[str, Any]) -> str:
    title = Path(source_name).stem or "document"
    page_buckets: dict[int, dict[str, list[str]]] = {}
    for chunk in processed.get("text_chunks", []):
        page_number = int(chunk.get("page", 1) or 1)
        page_buckets.setdefault(page_number, {"text": [], "ocr": [], "other": []})
        bucket_key = chunk.get("type", "other")
        if bucket_key not in page_buckets[page_number]:
            bucket_key = "other"
        content = str(chunk.get("content", "")).strip()
        if content:
            page_buckets[page_number][bucket_key].append(content)

    lines = [f"# {title}", "", f"> Source: {source_name}", ""]
    for page_number in sorted(page_buckets):
        buckets = page_buckets[page_number]
        lines.append(f"## Page {page_number}")
        lines.append("")
        if buckets["text"]:
            lines.append("\n\n".join(buckets["text"]))
            lines.append("")
        if buckets["ocr"]:
            lines.append("### OCR Notes")
            lines.append("")
            lines.append("\n\n".join(buckets["ocr"]))
            lines.append("")
        if buckets["other"]:
            lines.append("### Extra Content")
            lines.append("")
            lines.append("\n\n".join(buckets["other"]))
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def normalize_markdown_source(path: Path) -> str:
    content = read_text_source(path)
    return content if content.lstrip().startswith("#") else f"# {path.stem}\n\n{content.strip()}\n"


def normalize_text_source(path: Path) -> str:
    content = read_text_source(path)
    return normalize_plain_text_content(content, path.stem)


async def normalize_local_document(path: Path, processor: DocumentProcessor) -> tuple[str, dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".md":
        markdown = normalize_markdown_source(path)
        metadata = {
            "page_count": 1,
            "extract_method": "markdown_copy",
            "ocr_used": False,
        }
        return markdown, metadata

    if suffix in {".txt", ".log", ".ini", ".yaml", ".yml"}:
        markdown = normalize_text_source(path)
        metadata = {
            "page_count": 1,
            "extract_method": "plain_text_copy",
            "ocr_used": False,
        }
        return markdown, metadata

    processed = await processor.process_document(path)
    markdown = render_processed_document_as_markdown(path.name, processed)
    metadata = processed.get("metadata", {})
    return markdown, {
        "page_count": processed.get("page_count", 1),
        "extract_method": metadata.get("extract_method", "processed"),
        "ocr_used": bool(metadata.get("ocr_used", False)),
    }


def iter_supported_documents(input_dir: Path) -> list[Path]:
    files = [path for path in sorted(input_dir.rglob("*")) if path.is_file() and path.suffix.lower() in SUPPORTED_LOCAL_EXTENSIONS]
    return files


def write_manifest(entries: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for entry in entries:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")


async def prepare_local_corpus(workspace_root: Path, *, enable_ocr: bool = True) -> dict[str, Any]:
    paths = ensure_docqa_workspace(workspace_root)
    processor = DocumentProcessor(enable_ocr=enable_ocr)
    documents = iter_supported_documents(paths["local_raw_docs"])
    manifest_entries: list[dict[str, Any]] = []

    for source_path in documents:
        doc_id = slugify_document_name(source_path)
        output_path = paths["local_norm_docs"] / f"{doc_id}.md"
        try:
            markdown, metadata = await normalize_local_document(source_path, processor)
            output_path.write_text(markdown, encoding="utf-8")
            manifest_entries.append(
                {
                    "doc_id": doc_id,
                    "source_path": str(source_path),
                    "source_type": source_path.suffix.lower().lstrip("."),
                    "normalized_path": str(output_path),
                    "title": source_path.stem,
                    "page_count": metadata["page_count"],
                    "extract_method": metadata["extract_method"],
                    "ocr_used": metadata["ocr_used"],
                    "status": "ok",
                    "error": "",
                }
            )
        except Exception as exc:
            logger.exception("Failed to normalize {}", source_path)
            manifest_entries.append(
                {
                    "doc_id": doc_id,
                    "source_path": str(source_path),
                    "source_type": source_path.suffix.lower().lstrip("."),
                    "normalized_path": str(output_path),
                    "title": source_path.stem,
                    "page_count": 0,
                    "extract_method": "error",
                    "ocr_used": False,
                    "status": "error",
                    "error": str(exc),
                }
            )

    manifest_path = paths["annotations"] / "local_corpus_manifest.jsonl"
    write_manifest(manifest_entries, manifest_path)
    return {
        "workspace_root": str(workspace_root),
        "documents_seen": len(documents),
        "documents_ok": sum(1 for item in manifest_entries if item["status"] == "ok"),
        "manifest_path": str(manifest_path),
    }


def build_seed_annotation_records(documents: dict[str, str], answerable_limit_per_doc: int = 3) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    for filename, content in sorted(documents.items()):
        sections = extract_markdown_sections(content)
        section_names = list(sections)
        if not section_names:
            section_names = [""]

        for index, section_name in enumerate(section_names[:answerable_limit_per_doc], start=1):
            evidence_ref = filename if not section_name else f"{filename}#{section_name}"
            records.append(
                {
                    "id": f"{Path(filename).stem}-answerable-{index:03d}",
                    "question": "",
                    "target_documents": [filename],
                    "expected_evidence": [evidence_ref],
                    "expected_answer_points": [],
                    "allow_no_answer": False,
                }
            )

        records.append(
            {
                "id": f"{Path(filename).stem}-rejectable-001",
                "question": "",
                "target_documents": [filename],
                "expected_evidence": [],
                "expected_answer_points": [],
                "allow_no_answer": True,
            }
        )

    return records


def load_normalized_documents(directory: Path) -> dict[str, str]:
    documents: dict[str, str] = {}
    for path in sorted(directory.glob("*.md")):
        documents[path.name] = path.read_text(encoding="utf-8")
    return documents


def write_seed_annotations(output_path: Path, records: list[dict[str, Any]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_seed_annotations(workspace_root: Path, answerable_limit_per_doc: int = 3) -> dict[str, Any]:
    paths = ensure_docqa_workspace(workspace_root)
    documents = load_normalized_documents(paths["local_norm_docs"])
    records = build_seed_annotation_records(documents, answerable_limit_per_doc=answerable_limit_per_doc)
    output_path = paths["annotations"] / "local_docqa_seed_v1.json"
    write_seed_annotations(output_path, records)
    return {
        "workspace_root": str(workspace_root),
        "documents": len(documents),
        "records": len(records),
        "output_path": str(output_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize local DocQA source documents into Markdown.")
    parser.add_argument("--workspace-root", default=str(default_workspace_root()))
    parser.add_argument("--seed-output", action="store_true", help="Also generate blank annotation templates after normalization.")
    parser.add_argument("--answerable-limit-per-doc", type=int, default=3)
    parser.add_argument("--disable-ocr", action="store_true", help="Skip OCR for embedded images during normalization.")
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root)
    summary = asyncio.run(prepare_local_corpus(workspace_root, enable_ocr=not args.disable_ocr))
    if args.seed_output:
        summary["seed_annotations"] = generate_seed_annotations(
            workspace_root,
            answerable_limit_per_doc=args.answerable_limit_per_doc,
        )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
