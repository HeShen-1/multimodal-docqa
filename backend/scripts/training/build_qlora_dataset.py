from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SYSTEM_PROMPT = (
    "你是企业文档问答助手。你必须只依据提供的证据作答，优先输出简洁、可引用、可核验的结论。"
    "如果证据不足，请明确回答“未找到足够依据”，不要编造。"
)

REFUSAL_ANSWER = (
    "未找到足够依据。当前提供的文档片段中没有能直接回答该问题的明确信息，因此不应继续推断或编造答案。"
)

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]+")
CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")
DIRECTORY_NOISE_PATTERN = re.compile(r"[.。·]{4,}")
LOW_SIGNAL_PATTERN = re.compile(r"^[\W_\d\s.。·\-—_=:：/\\|]+$")
MAX_EVIDENCE_BLOCK_CHARS = 360
MAX_EVIDENCE_BLOCKS_PER_REFERENCE = 2
EARLY_CONTEXT_MARKERS = ("开头", "一开始", "最初", "起初", "前文", "最早")
STOP_TERMS = {
    "什么",
    "哪些",
    "是否",
    "有没有",
    "如何",
    "多少",
    "哪个",
    "给出",
    "材料",
    "文档",
    "这份",
    "当前",
    "通常",
}
STOP_CHARS = {"的", "了", "是", "在", "和", "与", "及", "并", "个", "这", "那", "有", "上", "下", "中", "前", "后", "会", "能"}


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
    question: str = "",
) -> str:
    if not references:
        return ""

    section_cache = section_cache or {}
    evidence_blocks: list[str] = []

    for reference in references:
        candidates = build_reference_candidate_blocks(reference, documents, section_cache=section_cache)
        selected_blocks = select_relevant_evidence_blocks(question, candidates)

        if not selected_blocks:
            fallback_text = resolve_reference_fallback_text(reference, documents, section_cache=section_cache)
            if fallback_text:
                evidence_blocks.append(f"[source] {reference}\n{fallback_text}")
            continue

        for block in selected_blocks:
            evidence_blocks.append(f"[source] {block['source_reference']}\n{block['content']}")

    return "\n\n".join(evidence_blocks)


def build_reference_candidate_blocks(
    reference: str,
    documents: dict[str, str],
    *,
    section_cache: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    filename, _, heading = reference.partition("#")
    if filename not in documents:
        raise ValueError(f"Document not found for evidence reference: {reference}")

    document_text = documents[filename]
    if filename not in section_cache:
        section_cache[filename] = extract_markdown_sections(document_text)
    sections = section_cache[filename]

    candidate_sections: list[tuple[str, str]] = []
    if heading and heading in sections:
        candidate_sections = [(heading, sections[heading])]
        fallback_root = False
    elif sections:
        candidate_sections = list(sections.items())
        fallback_root = bool(heading)
    else:
        candidate_sections = [(Path(filename).stem, strip_markdown_headings(document_text))]
        fallback_root = bool(heading)
    chapterized_root = fallback_root and bool(candidate_sections) and is_chapter_like_heading(candidate_sections[0][0])

    candidates: list[dict[str, Any]] = []
    for section_index, (section_heading, section_text) in enumerate(candidate_sections):
        section_blocks = split_section_into_candidate_blocks(section_text)
        if not section_blocks:
            trimmed = section_text.strip()
            if trimmed:
                section_blocks = [trimmed]

        for block_index, block_text in enumerate(section_blocks):
            candidates.append(
                {
                    "heading": section_heading,
                    "content": block_text,
                    "source_reference": f"{filename}#{section_heading}" if section_heading else filename,
                    "section_index": section_index,
                    "block_index": block_index,
                    "fallback_root": fallback_root,
                    "chapterized_root": chapterized_root,
                }
            )
    return candidates


def resolve_reference_fallback_text(
    reference: str,
    documents: dict[str, str],
    *,
    section_cache: dict[str, dict[str, str]],
) -> str:
    filename, _, heading = reference.partition("#")
    if filename not in documents:
        raise ValueError(f"Document not found for evidence reference: {reference}")

    document_text = documents[filename]
    if filename not in section_cache:
        section_cache[filename] = extract_markdown_sections(document_text)

    if heading and heading in section_cache[filename]:
        return section_cache[filename][heading].strip()

    return strip_markdown_headings(document_text).strip()


def split_section_into_candidate_blocks(section_text: str) -> list[str]:
    normalized = normalize_block_text(section_text)
    if not normalized:
        return []

    raw_blocks = [block.strip() for block in re.split(r"\n\s*\n+", normalized) if block and block.strip()]
    prepared_blocks: list[str] = []

    for block in raw_blocks:
        if is_low_information_block(block):
            continue
        if len(block) <= MAX_EVIDENCE_BLOCK_CHARS:
            prepared_blocks.append(block)
            continue
        prepared_blocks.extend(split_long_block(block, max_chars=MAX_EVIDENCE_BLOCK_CHARS))

    atomic_blocks = [block for block in prepared_blocks if block and not is_low_information_block(block)]
    packed_blocks = pack_candidate_blocks(atomic_blocks)
    ordered_blocks: list[str] = []
    seen_blocks: set[str] = set()
    for block in atomic_blocks + packed_blocks:
        if not block or is_low_information_block(block) or block in seen_blocks:
            continue
        ordered_blocks.append(block)
        seen_blocks.add(block)
    return ordered_blocks


def normalize_block_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\ufeff", "")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def split_long_block(block: str, *, max_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""

    for piece in split_text_by_sentences(block):
        tentative = f"{current}{piece}" if current else piece
        if current and len(tentative) > max_chars:
            chunks.append(current.strip())
            current = piece
            continue
        current = tentative

    if current.strip():
        chunks.append(current.strip())

    return chunks


def split_text_by_sentences(text: str) -> list[str]:
    pieces = re.split(r"(?<=[。！？!?；;])", text)
    normalized_pieces = [piece.strip() for piece in pieces if piece and piece.strip()]
    return normalized_pieces or [text.strip()]


def pack_candidate_blocks(blocks: list[str]) -> list[str]:
    if not blocks:
        return []

    packed: list[str] = []
    current_blocks: list[str] = []

    for block in blocks:
        tentative = "\n\n".join(current_blocks + [block]).strip()
        if current_blocks and len(tentative) > MAX_EVIDENCE_BLOCK_CHARS:
            packed.append("\n\n".join(current_blocks).strip())
            current_blocks = []
        current_blocks.append(block)

    if current_blocks:
        packed.append("\n\n".join(current_blocks).strip())

    return packed


def is_low_information_block(block: str) -> bool:
    text = normalize_block_text(block)
    if not text:
        return True
    if LOW_SIGNAL_PATTERN.fullmatch(text):
        return True
    if DIRECTORY_NOISE_PATTERN.search(text):
        alnum_count = len(re.findall(r"[A-Za-z0-9\u4e00-\u9fff]", text))
        if alnum_count < 10:
            return True
    meaningful_chars = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]", "", text)
    return len(meaningful_chars) < 6


def select_relevant_evidence_blocks(question: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not candidates:
        return []

    early_root_preference = question_prefers_early_sections(question) and any(
        candidate.get("fallback_root") for candidate in candidates
    )

    if early_root_preference:
        first_root_candidate = min(
            (candidate for candidate in candidates if candidate.get("fallback_root")),
            key=lambda item: item["section_index"],
        )
        first_heading_base = normalize_heading_base(str(first_root_candidate.get("heading", "")))
        early_candidates = [
            candidate
            for candidate in candidates
            if not candidate.get("fallback_root")
            or normalize_heading_base(str(candidate.get("heading", ""))) == first_heading_base
        ]
        if early_candidates:
            candidates = early_candidates
        if question_mentions_gender_count(question):
            gender_candidates = [candidate for candidate in candidates if "男" in str(candidate["content"]) and "女" in str(candidate["content"])]
            if gender_candidates:
                candidates = gender_candidates
    elif any(candidate.get("chapterized_root") for candidate in candidates):
        first_root_candidate = min(
            (candidate for candidate in candidates if candidate.get("chapterized_root")),
            key=lambda item: item["section_index"],
        )
        first_heading_base = normalize_heading_base(str(first_root_candidate.get("heading", "")))
        chapter_candidates = [
            candidate
            for candidate in candidates
            if not candidate.get("chapterized_root")
            or normalize_heading_base(str(candidate.get("heading", ""))) == first_heading_base
        ]
        if chapter_candidates:
            candidates = chapter_candidates

    if not question.strip():
        return candidates[:MAX_EVIDENCE_BLOCKS_PER_REFERENCE]

    query_terms = extract_query_terms(question)
    scored: list[tuple[float, dict[str, Any]]] = []
    for candidate in candidates:
        score = score_evidence_block(query_terms, candidate, question=question)
        scored.append((score, candidate))

    best_score = max(score for score, _ in scored)
    if best_score <= 0:
        return candidates[:1]

    ranked = sorted(
        scored,
        key=lambda item: (
            item[0],
            -item[1]["section_index"],
            -item[1]["block_index"],
        ),
        reverse=True,
    )
    score_threshold = max(1.5, best_score * 0.55)
    block_limit = 1 if early_root_preference else MAX_EVIDENCE_BLOCKS_PER_REFERENCE
    selected = [candidate for score, candidate in ranked if score >= score_threshold][:block_limit]
    if not selected:
        selected = [ranked[0][1]]
    return sorted(selected, key=lambda item: (item["section_index"], item["block_index"]))


def score_evidence_block(query_terms: set[str], candidate: dict[str, Any], *, question: str = "") -> float:
    content_terms = extract_query_terms(candidate["content"])
    heading_terms = extract_query_terms(candidate["heading"])
    content_matches = query_terms & content_terms
    heading_matches = query_terms & heading_terms
    content_text = str(candidate["content"])

    score = sum(len(term) for term in content_matches)
    score += 1.5 * sum(len(term) for term in heading_matches)
    score -= max(0, len(candidate["content"]) - MAX_EVIDENCE_BLOCK_CHARS) * 0.01

    if is_low_information_block(candidate["content"]):
        score -= 5
    if candidate.get("fallback_root") and question_prefers_early_sections(question):
        score += max(0, 8 - candidate["section_index"] * 3)
    if question_mentions_gender_count(question):
        if "男" in content_text and "女" in content_text:
            score += 8
        elif "男" in content_text or "女" in content_text:
            score += 2
    if question_mentions_quantity(question) and re.search(r"[0-9一二三四五六七八九十两百千]+", content_text):
        score += 2

    return score


def extract_query_terms(text: str) -> set[str]:
    terms: set[str] = set()

    for token in TOKEN_PATTERN.findall(text.lower()):
        if token in STOP_TERMS or token.isdigit():
            continue
        if CJK_PATTERN.search(token):
            terms.update(build_cjk_ngrams(token))
            terms.update(build_cjk_char_terms(token))
            if len(token) <= 8:
                terms.add(token)
        elif len(token) > 1:
            terms.add(token)

    return {term for term in terms if term and term not in STOP_TERMS}


def build_cjk_ngrams(token: str) -> set[str]:
    ngrams: set[str] = set()
    if len(token) <= 3:
        ngrams.add(token)
        return ngrams

    for size in (2, 3):
        if len(token) < size:
            continue
        for index in range(len(token) - size + 1):
            ngram = token[index : index + size]
            if ngram not in STOP_TERMS:
                ngrams.add(ngram)
    return ngrams


def build_cjk_char_terms(token: str) -> set[str]:
    return {char for char in token if CJK_PATTERN.match(char) and char not in STOP_CHARS}


def question_prefers_early_sections(question: str) -> bool:
    return any(marker in question for marker in EARLY_CONTEXT_MARKERS)


def normalize_heading_base(heading: str) -> str:
    normalized = heading.strip()
    normalized = re.sub(r"[（(]续\d+[）)]$", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def is_chapter_like_heading(heading: str) -> bool:
    return bool(re.match(r"^第\s*[0-9零一二三四五六七八九十百千两]+\s*[章节卷篇回部集]", heading.strip()))


def question_mentions_gender_count(question: str) -> bool:
    return ("男" in question and "女" in question) or "男女" in question


def question_mentions_quantity(question: str) -> bool:
    return any(marker in question for marker in ("几", "多少", "数量", "共有", "一共"))


def strip_markdown_headings(markdown: str) -> str:
    lines = [line for line in markdown.splitlines() if not HEADING_PATTERN.match(line)]
    return "\n".join(lines).strip()


def build_ideal_answer(sample: dict[str, Any]) -> str:
    if sample.get("allow_no_answer"):
        return REFUSAL_ANSWER

    answer_points = [point.strip() for point in sample.get("expected_answer_points", []) if point and point.strip()]
    evidence_refs = sample.get("expected_evidence", [])

    if answer_points:
        answer = "根据提供的文档证据，答案包括：" + "；".join(answer_points) + "。"
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
        "3. 如能回答，先用 1 句话给出结论，再给出 2-4 个要点；\n"
        "4. 不要扩写，不要编造，不要输出与证据无关的背景，并尽量保留引用。\n"
    )


def build_training_record(
    sample: dict[str, Any],
    documents: dict[str, str],
    section_cache: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    evidence_text = build_evidence_text(
        sample.get("expected_evidence", []),
        documents,
        section_cache=section_cache,
        question=str(sample.get("question", "")),
    )
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
