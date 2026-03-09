from __future__ import annotations

import asyncio
import csv
import io
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

import fitz
from docx import Document as DocxDocument
from loguru import logger
from PIL import Image

from app.config import get_settings

if TYPE_CHECKING:
    from paddleocr import PaddleOCR


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._fragments: List[str] = []

    def handle_data(self, data: str):
        text = data.strip()
        if text:
            self._fragments.append(text)

    def get_text(self) -> str:
        return "\n".join(self._fragments)


class DocumentProcessor:
    """文档处理服务"""

    def __init__(self, *, enable_ocr: bool = True):
        self.settings = get_settings()
        self.chunk_size = self.settings.chunk_size
        self.chunk_overlap = self.settings.chunk_overlap
        self.enable_ocr = enable_ocr
        self._ocr: PaddleOCR | None = None

    @property
    def ocr(self) -> PaddleOCR:
        if self._ocr is None:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        return self._ocr

    @property
    def parent_chunk_size(self) -> int:
        return max(self.chunk_size * 3, min(1200, self.chunk_size * 4))

    @property
    def parent_chunk_overlap(self) -> int:
        return max(self.chunk_overlap * 3, min(180, max(40, self.chunk_overlap * 4)))

    async def process_document(self, file_path: Path) -> Dict[str, Any]:
        file_ext = file_path.suffix.lower()
        logger.info(f"开始处理文档: {file_path.name}, 类型: {file_ext}")

        if file_ext == ".pdf":
            return await self._process_pdf(file_path)
        if file_ext in [".docx", ".doc"]:
            return await self._process_docx(file_path)
        if file_ext in [".txt", ".md", ".log", ".ini", ".yaml", ".yml"]:
            return await self._process_plain_text(file_path)
        if file_ext in [".csv", ".tsv"]:
            return await self._process_csv(file_path)
        if file_ext in [".json", ".jsonl"]:
            return await self._process_json(file_path)
        if file_ext in [".html", ".htm"]:
            return await self._process_html(file_path)
        if file_ext == ".xml":
            return await self._process_xml(file_path)
        raise ValueError(f"不支持的文件格式: {file_ext}")

    async def _process_pdf(self, file_path: Path) -> Dict[str, Any]:
        text_chunks: List[Dict[str, Any]] = []
        images: List[Dict[str, Any]] = []
        parent_chunk_offset = 0
        ocr_used = False

        with fitz.open(file_path) as doc:
            page_count = len(doc)
            logger.info(f"PDF 文档共 {page_count} 页")

            raw_page_texts = [doc[page_index].get_text() for page_index in range(page_count)]
            repeated_lines = self._detect_repeated_short_lines(raw_page_texts)

            for page_index in range(page_count):
                page = doc[page_index]
                text = self._filter_repeated_lines(raw_page_texts[page_index], repeated_lines)
                page_chunks, parent_count = self._build_chunks(
                    text=text,
                    page=page_index + 1,
                    chunk_type="text",
                    chunk_index_offset=len(text_chunks),
                    parent_chunk_offset=parent_chunk_offset,
                    metadata_overrides={
                        "source_type": "text",
                        "extract_method": "pdf_text",
                    },
                )
                text_chunks.extend(page_chunks)
                parent_chunk_offset += parent_count

                for image_index, image in enumerate(page.get_images()):
                    try:
                        xref = image[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        ocr_payload = await self._ocr_image(image_bytes)
                        ocr_text = ocr_payload["text"]
                        if ocr_text.strip():
                            ocr_used = True
                            ocr_chunks, ocr_parent_count = self._build_chunks(
                                text=ocr_text,
                                page=page_index + 1,
                                chunk_type="ocr",
                                chunk_index_offset=len(text_chunks),
                                parent_chunk_offset=parent_chunk_offset,
                                metadata_overrides={
                                    "source_type": "ocr",
                                    "extract_method": "ocr",
                                    "image_index": image_index,
                                    "ocr_block_count": len(ocr_payload["blocks"]),
                                },
                            )
                            text_chunks.extend(ocr_chunks)
                            parent_chunk_offset += ocr_parent_count
                        images.append(
                            {
                                "page": page_index + 1,
                                "image_index": image_index,
                                "ocr_text": ocr_text,
                                "ocr_blocks": ocr_payload["blocks"],
                            }
                        )
                    except Exception as exc:
                        logger.warning(f"提取图像失败 (页 {page_index + 1}, 图 {image_index}): {exc}")

        logger.info(f"处理完成: {len(text_chunks)} 个文本块, {len(images)} 张图像")
        return {
            "text_chunks": text_chunks,
            "images": images,
            "page_count": page_count,
            "metadata": self._build_processing_metadata(
                chunk_count=len(text_chunks),
                image_count=len(images),
                parent_chunk_count=parent_chunk_offset,
                page_count=page_count,
                extract_method="pdf_text_and_ocr" if ocr_used else "pdf_text",
                ocr_used=ocr_used,
                has_tables=False,
                source_type="mixed" if ocr_used else "text",
            ),
        }

    async def _process_docx(self, file_path: Path) -> Dict[str, Any]:
        text_chunks: List[Dict[str, Any]] = []
        images: List[Dict[str, Any]] = []
        parent_chunk_offset = 0
        ocr_used = False

        doc = DocxDocument(file_path)
        paragraphs = [paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()]
        full_text = "\n\n".join(paragraphs)
        body_chunks, parent_count = self._build_chunks(
            text=full_text,
            page=1,
            chunk_type="text",
            chunk_index_offset=0,
            parent_chunk_offset=parent_chunk_offset,
            metadata_overrides={
                "source_type": "text",
                "extract_method": "structured_text",
            },
        )
        text_chunks.extend(body_chunks)
        parent_chunk_offset += parent_count

        for image_index, relation in enumerate(doc.part.rels.values()):
            if "image" not in relation.target_ref:
                continue
            try:
                image_data = relation.target_part.blob
                ocr_payload = await self._ocr_image(image_data)
                ocr_text = ocr_payload["text"]
                if ocr_text.strip():
                    ocr_used = True
                    ocr_chunks, ocr_parent_count = self._build_chunks(
                        text=ocr_text,
                        page=1,
                        chunk_type="ocr",
                        chunk_index_offset=len(text_chunks),
                        parent_chunk_offset=parent_chunk_offset,
                        metadata_overrides={
                            "source_type": "ocr",
                            "extract_method": "ocr",
                            "image_index": image_index,
                            "ocr_block_count": len(ocr_payload["blocks"]),
                        },
                    )
                    text_chunks.extend(ocr_chunks)
                    parent_chunk_offset += ocr_parent_count
                images.append(
                    {
                        "page": 1,
                        "image_index": image_index,
                        "ocr_text": ocr_text,
                        "ocr_blocks": ocr_payload["blocks"],
                    }
                )
            except Exception as exc:
                logger.warning(f"提取 DOCX 图像失败 (图 {image_index}): {exc}")

        logger.info(f"处理完成: {len(text_chunks)} 个文本块, {len(images)} 张图像")
        return {
            "text_chunks": text_chunks,
            "images": images,
            "page_count": 1,
            "metadata": self._build_processing_metadata(
                chunk_count=len(text_chunks),
                image_count=len(images),
                parent_chunk_count=parent_chunk_offset,
                page_count=1,
                extract_method="structured_text_and_ocr" if ocr_used else "structured_text",
                ocr_used=ocr_used,
                has_tables=False,
                source_type="mixed" if ocr_used else "text",
            ),
        }

    async def _process_plain_text(self, file_path: Path) -> Dict[str, Any]:
        content = self._read_text_file(file_path)
        return self._build_text_result(
            content,
            file_kind=file_path.suffix.upper().lstrip("."),
            extract_method="structured_text" if file_path.suffix.lower() == ".md" else "plain_text",
            source_type="text",
            chunk_type="text",
            has_tables=False,
        )

    async def _process_csv(self, file_path: Path) -> Dict[str, Any]:
        delimiter = "\t" if file_path.suffix.lower() == ".tsv" else ","
        rows: List[str] = []
        headers: List[str] = []
        with file_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            for row_index, row in enumerate(reader):
                cleaned = [cell.strip() for cell in row]
                if row_index == 0:
                    headers = [cell for cell in cleaned if cell]
                    if headers:
                        rows.append(f"[表头] {' | '.join(headers)}")
                    continue
                if headers:
                    pairs = [f"{header}: {value}" for header, value in zip(headers, cleaned) if header and value]
                    if pairs:
                        rows.append(" | ".join(pairs))
                else:
                    rows.append(" | ".join(cell for cell in cleaned if cell))
        return self._build_text_result(
            "\n".join(row for row in rows if row),
            file_kind="CSV",
            extract_method="table_parse",
            source_type="table",
            chunk_type="table",
            has_tables=True,
        )

    async def _process_json(self, file_path: Path) -> Dict[str, Any]:
        raw = self._read_text_file(file_path)
        if file_path.suffix.lower() == ".jsonl":
            lines = [line.strip() for line in raw.splitlines() if line.strip()]
            normalized = "\n".join(lines)
        else:
            parsed = json.loads(raw)
            normalized = json.dumps(parsed, ensure_ascii=False, indent=2)
        return self._build_text_result(
            normalized,
            file_kind="JSON",
            extract_method="structured_text",
            source_type="text",
            chunk_type="text",
            has_tables=False,
        )

    async def _process_html(self, file_path: Path) -> Dict[str, Any]:
        content = self._read_text_file(file_path)
        parser = _HTMLTextExtractor()
        parser.feed(content)
        normalized = parser.get_text()
        if not normalized:
            normalized = re.sub(r"<[^>]+>", " ", content)
            normalized = re.sub(r"\s+", " ", normalized).strip()
        return self._build_text_result(
            normalized,
            file_kind="HTML",
            extract_method="structured_text",
            source_type="text",
            chunk_type="text",
            has_tables=False,
        )

    async def _process_xml(self, file_path: Path) -> Dict[str, Any]:
        content = self._read_text_file(file_path)
        try:
            root = ET.fromstring(content)
            normalized = "\n".join(text.strip() for text in root.itertext() if text and text.strip())
        except ET.ParseError:
            normalized = content
        return self._build_text_result(
            normalized,
            file_kind="XML",
            extract_method="structured_text",
            source_type="text",
            chunk_type="text",
            has_tables=False,
        )

    def _read_text_file(self, file_path: Path) -> str:
        for encoding in ["utf-8", "utf-8-sig", "gb18030", "latin-1"]:
            try:
                return file_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("文本文件读取失败")

    def _build_text_result(
        self,
        content: str,
        file_kind: str,
        extract_method: str,
        source_type: str,
        chunk_type: str,
        has_tables: bool,
    ) -> Dict[str, Any]:
        text_chunks, parent_count = self._build_chunks(
            text=content,
            page=1,
            chunk_type=chunk_type,
            metadata_overrides={
                "source_type": source_type,
                "extract_method": extract_method,
            },
        )
        logger.info(f"{file_kind} 处理完成: {len(text_chunks)} 个文本块")
        return {
            "text_chunks": text_chunks,
            "images": [],
            "page_count": 1,
            "metadata": self._build_processing_metadata(
                chunk_count=len(text_chunks),
                image_count=0,
                parent_chunk_count=parent_count,
                page_count=1,
                extract_method=extract_method,
                ocr_used=False,
                has_tables=has_tables,
                source_type=source_type,
            ),
        }

    def _build_chunks(
        self,
        text: str,
        page: int,
        chunk_type: str,
        chunk_index_offset: int = 0,
        parent_chunk_offset: int = 0,
        metadata_overrides: Dict[str, Any] | None = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        normalized = self._normalize_text(text)
        if not normalized:
            return [], 0

        parent_chunks = self._chunk_text(
            normalized,
            target_size=self.parent_chunk_size,
            overlap=self.parent_chunk_overlap,
        )
        results: List[Dict[str, Any]] = []
        next_chunk_index = chunk_index_offset

        for local_parent_index, parent_text in enumerate(parent_chunks):
            child_chunks = self._chunk_text(
                parent_text,
                target_size=self.chunk_size,
                overlap=self.chunk_overlap,
            )
            parent_chunk_index = parent_chunk_offset + local_parent_index
            for child_text in child_chunks:
                results.append(
                    {
                        "content": child_text,
                        "page": page,
                        "chunk_index": next_chunk_index,
                        "type": chunk_type,
                        "parent_chunk_index": parent_chunk_index,
                        **(metadata_overrides or {}),
                    }
                )
                next_chunk_index += 1

        return results, len(parent_chunks)

    def _build_processing_metadata(
        self,
        chunk_count: int,
        image_count: int,
        parent_chunk_count: int,
        page_count: int,
        extract_method: str,
        ocr_used: bool,
        has_tables: bool,
        source_type: str,
    ) -> Dict[str, Any]:
        metadata = {
            "chunk_count": chunk_count,
            "image_count": image_count,
            "parent_chunk_count": parent_chunk_count,
            "page_count": page_count,
            "extract_method": extract_method,
            "ocr_used": ocr_used,
            "has_tables": has_tables,
            "has_images": image_count > 0,
            "source_type": source_type,
        }
        metadata["processing_summary"] = {
            "extract_method": extract_method,
            "ocr_used": ocr_used,
            "page_count": page_count,
            "chunk_count": chunk_count,
            "has_tables": has_tables,
            "has_images": image_count > 0,
            "source_type": source_type,
        }
        return metadata

    def _chunk_text(
        self,
        text: str,
        target_size: int | None = None,
        overlap: int | None = None,
    ) -> List[str]:
        clean_text = self._normalize_text(text)
        if not clean_text:
            return []

        size = max(50, target_size or self.chunk_size)
        chunk_overlap = max(0, min(overlap if overlap is not None else self.chunk_overlap, size // 2))
        blocks = self._split_text_blocks(clean_text)
        return self._pack_blocks(blocks, size, chunk_overlap)

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""

        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = normalized.replace("\u00a0", " ").replace("\ufeff", "")
        normalized = re.sub(r"[\u200b-\u200f\u2060]", "", normalized)
        normalized = re.sub(r"[ \t]+", " ", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        normalized = normalized.strip()
        return normalized

    def _split_text_blocks(self, text: str) -> List[str]:
        lines = [line.strip() for line in text.splitlines()]
        blocks: List[str] = []
        current_lines: List[str] = []

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                self._flush_block(current_lines, blocks)
                continue

            if self._should_drop_line(line):
                continue

            if self._is_heading_line(line) or self._is_list_item(line):
                self._flush_block(current_lines, blocks)
                blocks.append(line)
                continue

            current_lines.append(line)

        self._flush_block(current_lines, blocks)
        return [block for block in blocks if block]

    def _flush_block(self, current_lines: List[str], blocks: List[str]) -> None:
        if not current_lines:
            return

        merged = self._join_lines(current_lines)
        if merged:
            blocks.append(merged)
        current_lines.clear()

    def _join_lines(self, lines: List[str]) -> str:
        merged = lines[0]
        for line in lines[1:]:
            if merged.endswith(("-", "—", "/", "（", "(", "[", "【", "：", ":")):
                merged = f"{merged}{line}"
            elif line.startswith(("）", ")", "]", "】", "、", "，", ",", "。", ".", "；", ";", "：", ":")):
                merged = f"{merged}{line}"
            else:
                merged = f"{merged}\n{line}"
        return merged.strip()

    def _should_drop_line(self, line: str) -> bool:
        if re.fullmatch(r"\d{1,4}", line):
            return True
        if re.fullmatch(r"第?\s*\d+\s*页", line):
            return True
        return False

    def _is_heading_line(self, line: str) -> bool:
        if not line:
            return False
        if line.startswith("#"):
            return True
        if re.match(r"^(第[一二三四五六七八九十百零\d]+[章节部分篇]|[一二三四五六七八九十]+[、.）)]|\d+(\.\d+){0,3}[、.）)])", line):
            return True
        if len(line) <= 28 and not re.search(r"[。！？!?；;，,]$", line):
            return True
        return False

    def _is_list_item(self, line: str) -> bool:
        return bool(re.match(r"^([-*•●▪▶]|(\d+|[A-Za-z])[.)、])", line))

    def _pack_blocks(self, blocks: List[str], target_size: int, overlap: int) -> List[str]:
        if not blocks:
            return []

        prepared_blocks: List[str] = []
        for block in blocks:
            if len(block) <= target_size:
                prepared_blocks.append(block)
            else:
                prepared_blocks.extend(self._split_long_block(block, target_size, overlap))

        chunks: List[str] = []
        current_blocks: List[str] = []

        for block in prepared_blocks:
            tentative_blocks = current_blocks + [block]
            if current_blocks and len("\n\n".join(tentative_blocks)) > target_size:
                chunks.append("\n\n".join(current_blocks).strip())
                current_blocks = self._select_overlap_blocks(current_blocks, overlap)

                while current_blocks and len("\n\n".join(current_blocks + [block])) > target_size:
                    current_blocks = current_blocks[1:]

            current_blocks.append(block)

        if current_blocks:
            chunks.append("\n\n".join(current_blocks).strip())

        return [chunk for chunk in chunks if chunk]

    def _select_overlap_blocks(self, blocks: List[str], overlap: int) -> List[str]:
        if not blocks or overlap <= 0:
            return []

        selected: List[str] = []
        total_length = 0
        for block in reversed(blocks):
            selected.insert(0, block)
            total_length += len(block)
            if total_length >= overlap:
                break
        return selected

    def _split_long_block(self, block: str, target_size: int, overlap: int) -> List[str]:
        separators = ["\n\n", "\n", "。", "！", "？", ".", "!", "?", "；", ";", "，", ",", " "]
        chunks: List[str] = []
        start = 0
        text_length = len(block)
        search_floor = max(overlap + 1, target_size // 2)

        while start < text_length:
            target_end = min(start + target_size, text_length)
            end = target_end

            if target_end < text_length:
                candidate_end = -1
                search_start = min(target_end, start + search_floor)
                for separator in separators:
                    position = block.rfind(separator, search_start, target_end)
                    if position == -1:
                        continue
                    separator_end = position + len(separator)
                    if separator_end > candidate_end:
                        candidate_end = separator_end
                if candidate_end > start:
                    end = candidate_end

            chunk = block[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= text_length:
                break

            next_start = end - overlap
            if next_start <= start:
                next_start = end
            start = next_start

        return chunks

    def _detect_repeated_short_lines(self, page_texts: List[str]) -> set[str]:
        if len(page_texts) < 3:
            return set()

        counter: Counter[str] = Counter()
        for text in page_texts:
            seen_on_page = set()
            for line in text.splitlines():
                normalized = line.strip()
                if not normalized or len(normalized) > 40:
                    continue
                if self._is_heading_line(normalized):
                    continue
                seen_on_page.add(normalized)
            counter.update(seen_on_page)

        threshold = max(3, len(page_texts) // 3)
        return {
            line
            for line, count in counter.items()
            if count >= threshold and not re.search(r"[。！？!?]", line)
        }

    def _filter_repeated_lines(self, text: str, repeated_lines: set[str]) -> str:
        if not repeated_lines:
            return text
        filtered_lines = [
            line
            for line in text.splitlines()
            if line.strip() not in repeated_lines
        ]
        return "\n".join(filtered_lines)

    async def _ocr_image(self, image_bytes: bytes) -> Dict[str, Any]:
        if not self.enable_ocr:
            return {"text": "", "blocks": []}
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._run_ocr, image_bytes)
        except Exception as exc:
            logger.warning(f"OCR 识别失败: {exc}")
            return {"text": "", "blocks": []}

    def _run_ocr(self, image_bytes: bytes) -> Dict[str, Any]:
        try:
            Image.open(io.BytesIO(image_bytes))
            result = self.ocr.ocr(image_bytes, cls=True)
            if result and result[0]:
                blocks = []
                for index, line in enumerate(result[0]):
                    bbox = line[0] if len(line) > 0 else []
                    payload = line[1] if len(line) > 1 else ("", 0.0)
                    blocks.append(
                        {
                            "index": index,
                            "text": payload[0],
                            "confidence": float(payload[1]) if len(payload) > 1 else 0.0,
                            "bbox": bbox,
                        }
                    )
                texts = [block["text"] for block in blocks if block["text"]]
                return {"text": " ".join(texts), "blocks": blocks}
            return {"text": "", "blocks": []}
        except Exception as exc:
            logger.warning(f"OCR 处理失败: {exc}")
            return {"text": "", "blocks": []}
