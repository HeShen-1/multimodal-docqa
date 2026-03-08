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


def slugify_document_name(path: Path) -> str:
    stem = path.stem.strip() or "document"
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", stem)
    return slug.strip("_") or "document"


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
    content = path.read_text(encoding="utf-8")
    return content if content.lstrip().startswith("#") else f"# {path.stem}\n\n{content.strip()}\n"


def normalize_text_source(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    return f"# {path.stem}\n\n{content.strip()}\n"


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


async def prepare_local_corpus(workspace_root: Path) -> dict[str, Any]:
    paths = ensure_docqa_workspace(workspace_root)
    processor = DocumentProcessor()
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
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root)
    summary = asyncio.run(prepare_local_corpus(workspace_root))
    if args.seed_output:
        summary["seed_annotations"] = generate_seed_annotations(
            workspace_root,
            answerable_limit_per_doc=args.answerable_limit_per_doc,
        )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
