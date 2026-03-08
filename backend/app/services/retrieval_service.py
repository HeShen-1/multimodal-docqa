from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

import jieba
from loguru import logger

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover
    BM25Okapi = None

from app.config import Settings, get_settings, settings
from app.services.cache_service import cache_result
from app.utils.exceptions import RetrievalError

if TYPE_CHECKING:
    from app.services.embedding_service import EmbeddingService
    from app.services.reranker_service import RerankerService


class RetrievalService:
    """混合检索服务"""

    def __init__(
        self,
        embedding_service: "EmbeddingService" = None,
        settings_obj: Settings | None = None,
        reranker_service: "RerankerService" | None = None,
    ):
        if embedding_service is None:
            from app.services.embedding_service import EmbeddingService

            embedding_service = EmbeddingService()
        self.embedding_service = embedding_service
        self.settings = settings_obj or get_settings()
        self.reranker_service = reranker_service
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
        context = await self.retrieve_context(query=query, top_k=top_k, document_ids=document_ids)
        return context["results"]

    async def retrieve_context(
        self,
        query: str,
        top_k: int = 5,
        document_ids: List[str] | None = None,
    ) -> Dict[str, Any]:
        try:
            rewritten_query = self._normalize_query(query)
            vector_results, bm25_results = await asyncio.gather(
                self._vector_search(rewritten_query, top_k * 2, document_ids),
                self._bm25_search(rewritten_query, top_k * 2, document_ids),
            )

            logger.info(f"向量检索: {len(vector_results)} 条, BM25检索: {len(bm25_results)} 条")

            fused_results = self._rrf_fusion(
                [
                    self._tag_results(vector_results, "vector"),
                    self._tag_results(bm25_results, "bm25"),
                ],
                top_k * 2,
            )
            expanded_results = await self._expand_to_parent_context(fused_results, top_k * 2)
            reranked_results, rerank_applied = await self._maybe_rerank(
                query=rewritten_query,
                candidates=expanded_results,
                top_k=top_k,
            )
            final_results = [self._enrich_result(item) for item in reranked_results[:top_k]]
            diagnostics = self._build_diagnostics(
                rewritten_query=rewritten_query,
                vector_results=vector_results,
                bm25_results=bm25_results,
                final_results=final_results,
                rerank_applied=rerank_applied,
            )
            return {
                "query": query,
                "rewritten_query": rewritten_query,
                "strategy": "hybrid_rerank" if rerank_applied else "hybrid",
                "results": final_results,
                "diagnostics": diagnostics,
            }
        except Exception as exc:
            logger.error(f"混合检索失败: {exc}")
            raise RetrievalError(str(exc))

    async def retrieve(
        self,
        question: str,
        document_id: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        context = await self.retrieve_context(
            query=question,
            top_k=top_k,
            document_ids=[document_id],
        )

        normalized_results = []
        for item in context["results"]:
            metadata = item.get("metadata", {}) or {}
            normalized_results.append(
                {
                    "content": item.get("content", ""),
                    "score": float(item.get("score", 0.0)),
                    "document_name": metadata.get("document_name", document_id),
                    "page": item.get("page_no", metadata.get("page")),
                    "chunk_id": item.get("chunk_id", item.get("id", "")),
                    "document_id": item.get("document_id", metadata.get("document_id", document_id)),
                    "page_no": item.get("page_no", metadata.get("page")),
                    "source_type": item.get("source_type", metadata.get("source_type", metadata.get("type", "text"))),
                    "rerank_score": item.get("rerank_score"),
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
        if BM25Okapi is None:
            logger.warning("rank_bm25 未安装，跳过 BM25 检索")
            return []

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
                        "matched_contents": [child_content] if child_content else [],
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
                        "matched_contents": [child_content] if child_content else [],
                    },
                }
                continue

            parent_content = self._merge_chunk_texts([chunk["content"] for chunk in sibling_chunks])
            page = min(int(chunk.get("page", 1)) for chunk in sibling_chunks)
            expanded_key = f"{document_id}_parent_{parent_chunk_index}"
            score = self._coerce_score(result)
            existing = expanded_map.get(expanded_key)
            matched_contents = []
            if existing:
                matched_contents.extend(existing["metadata"].get("matched_contents", []))
            if child_content:
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

    def _normalize_query(self, query: str) -> str:
        return re.sub(r"\s+", " ", str(query or "")).strip()

    def _coerce_score(self, item: Dict[str, Any]) -> float:
        score = item.get("score")
        if isinstance(score, (float, int)):
            return float(score)
        distance = item.get("distance")
        if isinstance(distance, (float, int)):
            return max(0.0, 1.0 - float(distance))
        return 0.0

    def _tag_results(self, results: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
        tagged_results: List[Dict[str, Any]] = []
        for item in results:
            metadata = {**(item.get("metadata", {}) or {})}
            retrieval_sources = list(metadata.get("retrieval_sources", []))
            if source not in retrieval_sources:
                retrieval_sources.append(source)
            metadata["retrieval_sources"] = retrieval_sources
            tagged_results.append(
                {
                    **item,
                    "metadata": metadata,
                    "score": self._coerce_score(item),
                }
            )
        return tagged_results

    def _estimate_evidence_coverage(self, results: List[Dict[str, Any]]) -> float:
        if not results:
            return 0.0

        matched_items = 0
        for item in results:
            metadata = item.get("metadata", {}) or {}
            matched_contents = metadata.get("matched_contents") or []
            matched_content = metadata.get("matched_content")
            if matched_contents or matched_content:
                matched_items += 1

        return round(matched_items / len(results), 4)

    def _enrich_result(self, item: Dict[str, Any]) -> Dict[str, Any]:
        metadata = item.get("metadata", {}) or {}
        return {
            **item,
            "score": self._coerce_score(item),
            "rerank_score": item.get("rerank_score"),
            "document_id": metadata.get("document_id"),
            "page_no": metadata.get("page"),
            "chunk_id": item.get("id"),
            "source_type": metadata.get("source_type", metadata.get("type", "text")),
        }

    def _build_diagnostics(
        self,
        rewritten_query: str,
        vector_results: List[Dict[str, Any]],
        bm25_results: List[Dict[str, Any]],
        final_results: List[Dict[str, Any]],
        rerank_applied: bool,
    ) -> Dict[str, Any]:
        top_score = self._coerce_score(final_results[0]) if final_results else 0.0
        citation_count = sum(1 for item in final_results if (item.get("metadata", {}) or {}).get("matched_content"))
        return {
            "rewritten_query": rewritten_query,
            "retrieved_chunks": len(final_results),
            "citation_count": citation_count,
            "top_score": round(top_score, 4),
            "evidence_coverage": self._estimate_evidence_coverage(final_results),
            "vector_hits": len(vector_results),
            "bm25_hits": len(bm25_results),
            "rerank_applied": rerank_applied,
            "fallback_reason": None,
        }

    async def _maybe_rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int,
    ) -> tuple[List[Dict[str, Any]], bool]:
        if not candidates or not self.settings.retrieval_enable_rerank:
            return candidates[:top_k], False

        reranker = self.reranker_service
        if reranker is None:
            from app.services.reranker_service import get_reranker_service

            reranker = get_reranker_service(
                model_name=self.settings.retrieval_rerank_model,
                device=self.settings.retrieval_rerank_device,
            )
            self.reranker_service = reranker

        original_scores = {item.get("id"): self._coerce_score(item) for item in candidates}
        try:
            ranked = await reranker.rerank(question=query, candidates=candidates, top_k=top_k)
        except Exception as exc:
            logger.warning(f"Rerank 执行失败，回退到融合结果: {exc}")
            return candidates[:top_k], False

        normalized: List[Dict[str, Any]] = []
        for item in ranked:
            rerank_score = item.get("score")
            base_score = original_scores.get(item.get("id"), self._coerce_score(item))
            normalized.append(
                {
                    **item,
                    "score": float(base_score),
                    "rerank_score": float(rerank_score) if isinstance(rerank_score, (float, int)) else None,
                }
            )
        return normalized[:top_k], True

    def should_ground_no_answer(
        self,
        results: List[Dict[str, Any]],
        has_document_scope: bool,
    ) -> Dict[str, Any]:
        diagnostics = {
            "should_ground": False,
            "reason": None,
            "top_score": 0.0,
            "evidence_coverage": 0.0,
        }
        if not has_document_scope:
            return diagnostics

        if not results:
            return {
                **diagnostics,
                "should_ground": True,
                "reason": "no_retrieval_results",
            }

        top_score = self._coerce_score(results[0])
        evidence_coverage = self._estimate_evidence_coverage(results)
        if top_score < self.settings.retrieval_min_score:
            return {
                **diagnostics,
                "should_ground": True,
                "reason": "low_retrieval_score",
                "top_score": round(top_score, 4),
                "evidence_coverage": evidence_coverage,
            }
        if evidence_coverage < self.settings.retrieval_min_coverage:
            return {
                **diagnostics,
                "should_ground": True,
                "reason": "low_evidence_coverage",
                "top_score": round(top_score, 4),
                "evidence_coverage": evidence_coverage,
            }
        return {
            **diagnostics,
            "top_score": round(top_score, 4),
            "evidence_coverage": evidence_coverage,
        }

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
                metadata = {**(document.get("metadata", {}) or {})}
                retrieval_sources = set(metadata.get("retrieval_sources", []))

                if document_id in doc_scores:
                    doc_scores[document_id]["score"] += score
                    existing_metadata = doc_scores[document_id]["doc"].setdefault("metadata", {})
                    existing_sources = set(existing_metadata.get("retrieval_sources", []))
                    existing_metadata["retrieval_sources"] = sorted(existing_sources | retrieval_sources)
                else:
                    doc_scores[document_id] = {
                        "doc": {
                            **document,
                            "metadata": metadata,
                        },
                        "score": score,
                    }

        sorted_docs = sorted(doc_scores.values(), key=lambda item: item["score"], reverse=True)
        merged_results: List[Dict[str, Any]] = []
        for item in sorted_docs[:top_k]:
            doc = {**item["doc"], "score": round(float(item["score"]), 4)}
            merged_results.append(doc)
        return merged_results

    async def build_bm25_index(self, documents: List[Dict[str, Any]]):
        if not documents:
            self.bm25_index = None
            self.bm25_documents = []
            return

        if BM25Okapi is None:
            logger.warning("rank_bm25 未安装，无法构建 BM25 索引")
            self.bm25_index = None
            self.bm25_documents = []
            return

        logger.info(f"开始构建BM25索引，文档数: {len(documents)}")
        tokenized_docs = [list(jieba.cut(document["content"])) for document in documents]
        self.bm25_index = BM25Okapi(tokenized_docs)
        self.bm25_documents = documents
        logger.info("BM25索引构建完成")
