import asyncio
from typing import Any, Dict, List, Tuple

import jieba
from loguru import logger
from rank_bm25 import BM25Okapi

from app.config import settings
from app.services.cache_service import cache_result
from app.services.embedding_service import EmbeddingService
from app.utils.exceptions import RetrievalError


class RetrievalService:
    """混合检索服务"""

    def __init__(self, embedding_service: EmbeddingService = None):
        self.embedding_service = embedding_service or EmbeddingService()
        self.bm25_index = None
        self.bm25_documents: List[Dict[str, Any]] = []
        self._bm25_cache_key: Tuple[str, ...] | None = None

    @cache_result(prefix="query", expire=settings.cache_query_expire)
    async def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        document_ids: List[str] = None,
    ) -> List[Dict[str, Any]]:
        try:
            vector_results, bm25_results = await asyncio.gather(
                self._vector_search(query, top_k * 2, document_ids),
                self._bm25_search(query, top_k * 2, document_ids),
            )

            logger.info(f"向量检索: {len(vector_results)} 条, BM25检索: {len(bm25_results)} 条")

            fused_results = self._rrf_fusion([vector_results, bm25_results], top_k * 2)
            expanded_results = await self._expand_to_parent_context(fused_results, top_k)
            return expanded_results
        except Exception as exc:
            logger.error(f"混合检索失败: {exc}")
            raise RetrievalError(str(exc))

    async def retrieve(
        self,
        question: str,
        document_id: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        results = await self.hybrid_search(
            query=question,
            top_k=top_k,
            document_ids=[document_id],
        )

        normalized_results = []
        for item in results:
            metadata = item.get("metadata", {}) or {}
            distance = item.get("distance")
            score = item.get("score")
            if score is None and isinstance(distance, (float, int)):
                score = max(0.0, 1.0 - float(distance))
            if score is None:
                score = 0.0

            normalized_results.append(
                {
                    "content": item.get("content", ""),
                    "score": float(score),
                    "document_name": metadata.get("document_name", document_id),
                    "page": metadata.get("page"),
                    "chunk_id": item.get("id", ""),
                    "metadata": metadata,
                }
            )

        return normalized_results

    async def _vector_search(
        self,
        query: str,
        top_k: int,
        document_ids: List[str] = None,
    ) -> List[Dict[str, Any]]:
        return await self.embedding_service.search_similar(
            query=query,
            top_k=top_k,
            document_ids=document_ids,
        )

    async def _bm25_search(
        self,
        query: str,
        top_k: int,
        document_ids: List[str] = None,
    ) -> List[Dict[str, Any]]:
        await self._ensure_bm25_index(document_ids)
        if not self.bm25_index or not self.bm25_documents:
            logger.warning("BM25索引未构建")
            return []

        query_tokens = list(jieba.cut(query))
        scores = self.bm25_index.get_scores(query_tokens)

        top_indices = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True,
        )[:top_k]

        results = []
        for index in top_indices:
            if scores[index] <= 0:
                continue

            document = self.bm25_documents[index]
            metadata = document.get("metadata", {}) or {}
            if document_ids and metadata.get("document_id") not in document_ids:
                continue

            results.append(
                {
                    "id": document["id"],
                    "content": document["content"],
                    "metadata": metadata,
                    "score": float(scores[index]),
                }
            )

        return results

    async def _ensure_bm25_index(self, document_ids: List[str] | None = None) -> None:
        cache_key = tuple(sorted(document_ids)) if document_ids else ("__all__",)
        if self.bm25_index is not None and self._bm25_cache_key == cache_key and self.bm25_documents:
            return

        documents = await self.embedding_service.list_text_chunks(document_ids)
        if not documents:
            self.bm25_index = None
            self.bm25_documents = []
            self._bm25_cache_key = cache_key
            return

        await self.build_bm25_index(documents)
        self._bm25_cache_key = cache_key

    async def _expand_to_parent_context(
        self,
        results: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        if not results:
            return []

        document_ids = sorted(
            {
                str((result.get("metadata", {}) or {}).get("document_id", "")).strip()
                for result in results
                if (result.get("metadata", {}) or {}).get("document_id")
            }
        )
        document_chunks_map = {
            document_id: await self.embedding_service.get_document_chunks(document_id)
            for document_id in document_ids
        }

        expanded_map: Dict[str, Dict[str, Any]] = {}
        for result in results:
            metadata = result.get("metadata", {}) or {}
            document_id = str(metadata.get("document_id", "")).strip()
            parent_chunk_index = metadata.get("parent_chunk_index", -1)
            try:
                parent_chunk_index = int(parent_chunk_index)
            except (TypeError, ValueError):
                parent_chunk_index = -1

            child_content = str(result.get("content", "") or "")
            if not document_id or parent_chunk_index < 0:
                expanded_key = str(result.get("id", ""))
                expanded_map[expanded_key] = {
                    **result,
                    "metadata": {
                        **metadata,
                        "matched_content": child_content,
                    },
                }
                continue

            sibling_chunks = [
                chunk
                for chunk in document_chunks_map.get(document_id, [])
                if chunk.get("parentChunkIndex") == parent_chunk_index
            ]
            if not sibling_chunks:
                expanded_key = str(result.get("id", ""))
                expanded_map[expanded_key] = {
                    **result,
                    "metadata": {
                        **metadata,
                        "matched_content": child_content,
                    },
                }
                continue

            parent_content = self._merge_chunk_texts([chunk["content"] for chunk in sibling_chunks])
            page = min(int(chunk.get("page", 1)) for chunk in sibling_chunks)
            expanded_key = f"{document_id}_parent_{parent_chunk_index}"
            score = result.get("score")
            if score is None:
                distance = result.get("distance")
                score = max(0.0, 1.0 - float(distance)) if isinstance(distance, (float, int)) else 0.0

            existing = expanded_map.get(expanded_key)
            matched_contents = []
            if existing:
                matched_contents.extend(existing["metadata"].get("matched_contents", []))
            matched_contents.append(child_content)

            expanded_map[expanded_key] = {
                "id": expanded_key,
                "content": parent_content,
                "metadata": {
                    **metadata,
                    "page": page,
                    "parent_chunk_index": parent_chunk_index,
                    "matched_content": child_content,
                    "matched_contents": matched_contents,
                },
                "score": max(float(score), float(existing.get("score", 0.0)) if existing else 0.0),
            }

        ordered = sorted(expanded_map.values(), key=lambda item: item.get("score", 0.0), reverse=True)
        return ordered[:top_k]

    def _merge_chunk_texts(self, texts: List[str]) -> str:
        merged = ""
        for text in texts:
            segment = str(text or "").strip()
            if not segment:
                continue

            if not merged:
                merged = segment
                continue

            overlap = self._find_overlap_suffix_prefix(merged, segment)
            if overlap > 0:
                merged = f"{merged}{segment[overlap:]}"
            else:
                merged = f"{merged}\n\n{segment}"

        return merged.strip()

    def _find_overlap_suffix_prefix(self, left: str, right: str, max_window: int = 240) -> int:
        window = min(len(left), len(right), max_window)
        for size in range(window, 16, -1):
            if left[-size:] == right[:size]:
                return size
        return 0

    def _rrf_fusion(
        self,
        results_list: List[List[Dict[str, Any]]],
        top_k: int,
        k: int = 60,
    ) -> List[Dict[str, Any]]:
        doc_scores: Dict[str, Dict[str, Any]] = {}

        for results in results_list:
            for rank, document in enumerate(results, start=1):
                document_id = document["id"]
                score = 1.0 / (k + rank)

                if document_id in doc_scores:
                    doc_scores[document_id]["score"] += score
                else:
                    doc_scores[document_id] = {
                        "doc": document,
                        "score": score,
                    }

        sorted_docs = sorted(doc_scores.values(), key=lambda item: item["score"], reverse=True)
        return [item["doc"] for item in sorted_docs[:top_k]]

    async def build_bm25_index(self, documents: List[Dict[str, Any]]):
        if not documents:
            self.bm25_index = None
            self.bm25_documents = []
            return

        logger.info(f"开始构建BM25索引，文档数: {len(documents)}")
        tokenized_docs = [list(jieba.cut(document["content"])) for document in documents]
        self.bm25_index = BM25Okapi(tokenized_docs)
        self.bm25_documents = documents
        logger.info("BM25索引构建完成")
