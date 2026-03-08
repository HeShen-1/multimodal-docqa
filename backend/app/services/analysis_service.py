"""
Phase 6 智能分析服务
"""
from __future__ import annotations

import difflib
import math
import re
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Sequence

import jieba
import numpy as np
from loguru import logger

from app.models.document_db import Document
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService


class AnalysisService:
    """智能分析服务"""

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        llm_service: Optional[LLMService] = None,
    ):
        self.embedding_service = embedding_service or EmbeddingService()
        self.llm_service = llm_service or LLMService()
        self.stopwords = {
            "的",
            "了",
            "和",
            "是",
            "在",
            "与",
            "及",
            "或",
            "对",
            "中",
            "为",
            "将",
            "并",
            "通过",
            "以及",
            "this",
            "that",
            "with",
            "from",
            "have",
            "has",
            "are",
            "was",
            "were",
            "for",
            "and",
            "the",
            "to",
            "of",
            "in",
            "on",
            "at",
            "by",
            "an",
            "a",
        }

    async def get_document_text(self, document_id: str) -> str:
        """读取文档已向量化的文本内容"""
        results = self._collection_get(
            where={"document_id": document_id},
            include=["documents", "metadatas"],
        )
        documents = results.get("documents")
        metadatas = results.get("metadatas")
        if documents is None:
            documents = []
        if metadatas is None:
            metadatas = []

        if len(documents) == 0:
            return ""

        indexed_chunks = []
        for index, content in enumerate(documents):
            if not isinstance(content, str):
                continue
            text = content.strip()
            if not text:
                continue

            metadata = metadatas[index] if index < len(metadatas) else {}
            page = self._safe_int((metadata or {}).get("page"), 1)
            chunk_index = self._safe_int((metadata or {}).get("chunk_index"), index)
            indexed_chunks.append((page, chunk_index, text))

        indexed_chunks.sort(key=lambda item: (item[0], item[1]))
        return "\n".join(chunk for _, _, chunk in indexed_chunks).strip()

    async def get_document_embedding(self, document_id: str) -> Optional[np.ndarray]:
        """获取文档平均向量"""
        results = self._collection_get(
            where={"document_id": document_id},
            include=["embeddings"],
        )
        embeddings = results.get("embeddings")
        if embeddings is None:
            embeddings = []
        if len(embeddings) == 0:
            return None

        embedding_array = np.array(embeddings, dtype=float)
        if embedding_array.ndim != 2 or embedding_array.size == 0:
            return None
        return np.mean(embedding_array, axis=0)

    async def generate_summary(
        self,
        text: str,
        method: str = "hybrid",
        max_length: int = 300,
        style: str = "简洁",
    ) -> Dict:
        """生成文档摘要"""
        normalized_method = method.lower()
        normalized_style = self._normalize_style(style)
        fallback_used = False

        extractive_summary = self._extractive_summary(text, max_length=max_length)

        if normalized_method == "extractive":
            summary = extractive_summary
        elif normalized_method == "generative":
            summary = await self._llm_summary(text, max_length=max_length, style=normalized_style)
            if not summary:
                fallback_used = True
                summary = extractive_summary
        else:
            seed_text = self._extractive_summary(text, max_length=min(max_length * 2, 1200))
            summary = await self._llm_summary(seed_text, max_length=max_length, style=normalized_style)
            if not summary:
                fallback_used = True
                summary = extractive_summary
            normalized_method = "hybrid"

        if not summary:
            summary = extractive_summary
            fallback_used = True

        source_length = len(text)
        compression_ratio = round(len(summary) / source_length, 4) if source_length else 0.0

        return {
            "summary": summary,
            "method": normalized_method,
            "style": normalized_style,
            "source_length": source_length,
            "compression_ratio": compression_ratio,
            "fallback_used": fallback_used,
        }

    async def extract_keywords(
        self,
        text: str,
        method: str = "hybrid",
        top_k: int = 10,
    ) -> List[Dict]:
        """提取关键词"""
        normalized_method = method.lower()
        if normalized_method == "tfidf":
            return self._tfidf_keywords(text, top_k=top_k)
        if normalized_method == "textrank":
            return self._textrank_keywords(text, top_k=top_k)
        if normalized_method == "llm":
            llm_keywords = await self._llm_keywords(text, top_k=top_k)
            if llm_keywords:
                return llm_keywords
            return self._tfidf_keywords(text, top_k=top_k)

        tfidf_keywords = self._tfidf_keywords(text, top_k=top_k * 2)
        textrank_keywords = self._textrank_keywords(text, top_k=top_k * 2)

        tfidf_map = {item["keyword"]: item["score"] for item in tfidf_keywords}
        textrank_map = {item["keyword"]: item["score"] for item in textrank_keywords}
        frequency_map = {item["keyword"]: item["frequency"] for item in tfidf_keywords}
        tokens = self._tokenize(text)
        token_counter = Counter(tokens)

        merged_scores = {}
        for word in set(tfidf_map) | set(textrank_map):
            merged_scores[word] = 0.6 * tfidf_map.get(word, 0.0) + 0.4 * textrank_map.get(word, 0.0)

        sorted_words = sorted(merged_scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
        return [
            {
                "keyword": word,
                "score": round(score, 4),
                "frequency": frequency_map.get(word, token_counter.get(word, 0)),
            }
            for word, score in sorted_words
        ]

    async def compare_documents(
        self,
        doc_a: Document,
        doc_b: Document,
        top_k: int = 10,
    ) -> Dict:
        """对比两个文档"""
        text_a = await self.get_document_text(doc_a.id)
        text_b = await self.get_document_text(doc_b.id)
        if not text_a or not text_b:
            raise ValueError("文档内容为空，无法完成对比")

        lexical_similarity = round(
            difflib.SequenceMatcher(None, text_a[:8000], text_b[:8000]).ratio(),
            4,
        )

        embedding_a, embedding_b = await self._load_embeddings(doc_a.id, doc_b.id)
        if embedding_a is not None and embedding_b is not None:
            semantic_similarity = round(self._cosine_similarity(embedding_a, embedding_b), 4)
        else:
            semantic_similarity = round(self._token_jaccard_similarity(text_a, text_b), 4)

        overall_similarity = round(0.65 * semantic_similarity + 0.35 * lexical_similarity, 4)

        keywords_a = await self.extract_keywords(text_a, method="hybrid", top_k=top_k)
        keywords_b = await self.extract_keywords(text_b, method="hybrid", top_k=top_k)

        keyword_map_a = {item["keyword"]: item["score"] for item in keywords_a}
        keyword_map_b = {item["keyword"]: item["score"] for item in keywords_b}
        set_a = set(keyword_map_a)
        set_b = set(keyword_map_b)

        common_topics = sorted(
            list(set_a & set_b),
            key=lambda item: keyword_map_a.get(item, 0.0) + keyword_map_b.get(item, 0.0),
            reverse=True,
        )[:top_k]
        unique_a = sorted(list(set_a - set_b), key=lambda item: keyword_map_a.get(item, 0.0), reverse=True)[:top_k]
        unique_b = sorted(list(set_b - set_a), key=lambda item: keyword_map_b.get(item, 0.0), reverse=True)[:top_k]

        return {
            "similarity": {
                "overall": overall_similarity,
                "semantic": semantic_similarity,
                "lexical": lexical_similarity,
            },
            "topics": {
                "commonTopics": common_topics,
                "uniqueTopicsA": unique_a,
                "uniqueTopicsB": unique_b,
            },
            "structure": {
                "documentA": {
                    "id": doc_a.id,
                    "name": doc_a.file_name,
                    "pageCount": doc_a.page_count or 0,
                    "chunkCount": doc_a.chunk_count or 0,
                    "fileSize": doc_a.file_size or 0,
                },
                "documentB": {
                    "id": doc_b.id,
                    "name": doc_b.file_name,
                    "pageCount": doc_b.page_count or 0,
                    "chunkCount": doc_b.chunk_count or 0,
                    "fileSize": doc_b.file_size or 0,
                },
                "differences": {
                    "pageCountDelta": abs((doc_a.page_count or 0) - (doc_b.page_count or 0)),
                    "chunkCountDelta": abs((doc_a.chunk_count or 0) - (doc_b.chunk_count or 0)),
                    "fileSizeDelta": abs((doc_a.file_size or 0) - (doc_b.file_size or 0)),
                },
            },
            "summary": self._build_compare_summary(
                overall_similarity=overall_similarity,
                common_topics=common_topics,
                unique_a=unique_a,
                unique_b=unique_b,
            ),
        }

    async def recommend_similar_documents(
        self,
        source_doc: Document,
        target_docs: Sequence[Document],
        limit: int = 5,
        min_similarity: float = 0.4,
    ) -> List[Dict]:
        """推荐相似文档"""
        source_text = await self.get_document_text(source_doc.id)
        if not source_text:
            return []

        source_embedding = await self.get_document_embedding(source_doc.id)
        source_keywords = await self.extract_keywords(source_text, method="hybrid", top_k=15)
        source_keyword_set = {item["keyword"] for item in source_keywords}

        results: List[Dict] = []
        for candidate in target_docs:
            target_text = await self.get_document_text(candidate.id)
            if not target_text:
                continue

            target_embedding = await self.get_document_embedding(candidate.id)
            if source_embedding is not None and target_embedding is not None:
                semantic_similarity = self._cosine_similarity(source_embedding, target_embedding)
            else:
                semantic_similarity = self._token_jaccard_similarity(source_text, target_text)

            target_keywords = await self.extract_keywords(target_text, method="hybrid", top_k=15)
            target_keyword_set = {item["keyword"] for item in target_keywords}

            common_topics = sorted(list(source_keyword_set & target_keyword_set))[:6]
            union_size = len(source_keyword_set | target_keyword_set)
            keyword_overlap = len(common_topics) / union_size if union_size else 0.0

            final_similarity = 0.75 * semantic_similarity + 0.25 * keyword_overlap
            if final_similarity < min_similarity:
                continue

            results.append(
                {
                    "id": candidate.id,
                    "name": candidate.file_name,
                    "similarity": round(final_similarity, 4),
                    "semanticSimilarity": round(semantic_similarity, 4),
                    "keywordOverlap": round(keyword_overlap, 4),
                    "commonTopics": common_topics,
                    "uploadTime": candidate.created_at.isoformat() if candidate.created_at else "",
                    "pageCount": candidate.page_count or 0,
                    "fileSize": candidate.file_size or 0,
                }
            )

        results.sort(key=lambda item: item["similarity"], reverse=True)
        return results[:limit]

    async def _load_embeddings(
        self,
        document_id_a: str,
        document_id_b: str,
    ) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        embedding_a, embedding_b = await self.get_document_embedding(document_id_a), await self.get_document_embedding(
            document_id_b
        )
        return embedding_a, embedding_b

    async def _llm_summary(self, text: str, max_length: int, style: str) -> str:
        prompt = (
            "你是一名文档分析助手。"
            f"请输出一段{style}风格摘要，不超过{max_length}字，覆盖核心事实与结论。"
            "禁止编造信息，只能基于给定内容。"
            "\n\n文档内容：\n"
            f"{text[:5000]}"
        )
        try:
            result = await self.llm_service.generate_general_answer(
                query=prompt,
                stream=False,
                temperature=0.2,
            )
            candidate = (result.get("answer") or "").strip()
            if not candidate or candidate.startswith("抱歉"):
                return ""
            if len(candidate) > max_length:
                candidate = candidate[:max_length].rstrip("，,；;。.!? ") + "..."
            return candidate
        except Exception as exc:
            logger.warning(f"LLM 摘要生成失败，回退抽取式摘要: {exc}")
            return ""

    async def _llm_keywords(self, text: str, top_k: int) -> List[Dict]:
        prompt = (
            "请从以下文档中提取关键词。"
            f"返回 {top_k} 个关键词，仅输出关键词列表，使用中文逗号分隔。"
            "\n\n文档内容：\n"
            f"{text[:4000]}"
        )
        try:
            result = await self.llm_service.generate_general_answer(
                query=prompt,
                stream=False,
                temperature=0.2,
            )
            answer = (result.get("answer") or "").strip()
            if not answer or answer.startswith("抱歉"):
                return []

            tokens = self._tokenize(text)
            token_counter = Counter(tokens)
            candidates = re.split(r"[，,、;；\n]+", answer)
            normalized = []
            for candidate in candidates:
                word = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]", "", candidate.strip().lower())
                if len(word) <= 1 or word in self.stopwords:
                    continue
                if word in normalized:
                    continue
                normalized.append(word)
                if len(normalized) >= top_k:
                    break

            score_base = float(len(normalized)) if normalized else 1.0
            return [
                {
                    "keyword": word,
                    "score": round((score_base - index) / score_base, 4),
                    "frequency": token_counter.get(word, 0),
                }
                for index, word in enumerate(normalized)
            ]
        except Exception as exc:
            logger.warning(f"LLM 关键词提取失败，回退统计方法: {exc}")
            return []

    def _extractive_summary(self, text: str, max_length: int) -> str:
        clean_text = text.strip()
        if len(clean_text) <= max_length:
            return clean_text

        sentences = self._split_sentences(clean_text)
        if len(sentences) <= 1:
            return clean_text[:max_length].rstrip("，,；;。.!? ") + "..."

        token_counter = Counter(self._tokenize(clean_text))
        if not token_counter:
            return clean_text[:max_length].rstrip("，,；;。.!? ") + "..."

        max_frequency = max(token_counter.values()) or 1
        frequency_map = {word: value / max_frequency for word, value in token_counter.items()}

        scored_sentences = []
        total_sentences = len(sentences)
        for index, sentence in enumerate(sentences):
            tokens = self._tokenize(sentence)
            if not tokens:
                continue
            word_score = sum(frequency_map.get(token, 0.0) for token in tokens) / len(tokens)
            position_boost = 0.15 * (1.0 - (index / max(total_sentences, 1)))
            length_penalty = -0.05 if len(sentence) > 320 else 0.0
            score = word_score + position_boost + length_penalty
            scored_sentences.append((index, sentence, score))

        if not scored_sentences:
            return clean_text[:max_length].rstrip("，,；;。.!? ") + "..."

        target_sentences = max(2, min(total_sentences, max_length // 90 + 1))
        best = sorted(scored_sentences, key=lambda item: item[2], reverse=True)[:target_sentences]
        best.sort(key=lambda item: item[0])

        summary = "".join(
            sentence if sentence.endswith(("。", "！", "？", ".", "!", "?")) else f"{sentence}。"
            for _, sentence, _ in best
        ).strip()
        if len(summary) > max_length:
            summary = summary[:max_length].rstrip("，,；;。.!? ") + "..."
        return summary

    def _tfidf_keywords(self, text: str, top_k: int) -> List[Dict]:
        sentences = self._split_sentences(text)
        tokenized_docs = [self._tokenize(sentence) for sentence in sentences]
        tokenized_docs = [tokens for tokens in tokenized_docs if tokens]
        if not tokenized_docs:
            return []

        document_count = len(tokenized_docs)
        token_counter = Counter(token for doc in tokenized_docs for token in doc)
        total_tokens = sum(token_counter.values()) or 1

        doc_frequency = Counter()
        for tokens in tokenized_docs:
            for token in set(tokens):
                doc_frequency[token] += 1

        score_map = {}
        for token, count in token_counter.items():
            tf = count / total_tokens
            idf = math.log((document_count + 1) / (doc_frequency[token] + 1)) + 1
            score_map[token] = tf * idf

        sorted_items = sorted(score_map.items(), key=lambda item: item[1], reverse=True)[:top_k]
        return [
            {"keyword": word, "score": round(score, 4), "frequency": token_counter[word]}
            for word, score in sorted_items
        ]

    def _textrank_keywords(self, text: str, top_k: int) -> List[Dict]:
        tokens = self._tokenize(text)
        if len(tokens) < 2:
            return []

        window_size = 4
        graph = defaultdict(Counter)
        for index, token in enumerate(tokens):
            right_bound = min(index + window_size, len(tokens))
            for second_index in range(index + 1, right_bound):
                other = tokens[second_index]
                if token == other:
                    continue
                graph[token][other] += 1
                graph[other][token] += 1

        if not graph:
            return self._tfidf_keywords(text, top_k=top_k)

        damping = 0.85
        scores = {word: 1.0 for word in graph}
        for _ in range(20):
            new_scores = {}
            for word, neighbors in graph.items():
                rank_sum = 0.0
                for neighbor, weight in neighbors.items():
                    total_weight = sum(graph[neighbor].values()) or 1.0
                    rank_sum += (weight / total_weight) * scores.get(neighbor, 1.0)
                new_scores[word] = (1 - damping) + damping * rank_sum
            scores = new_scores

        token_counter = Counter(tokens)
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
        return [
            {"keyword": word, "score": round(score, 4), "frequency": token_counter[word]}
            for word, score in ranked
        ]

    def _split_sentences(self, text: str) -> List[str]:
        chunks = re.split(r"(?<=[。！？!?；;\n])", text.replace("\r", "\n"))
        sentences = [chunk.strip() for chunk in chunks if chunk.strip()]
        if not sentences and text.strip():
            return [text.strip()]
        return sentences

    def _tokenize(self, text: str) -> List[str]:
        lowered = text.lower()
        raw_tokens = jieba.lcut(lowered)
        tokens = []
        for raw_token in raw_tokens:
            token = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]", "", raw_token)
            if not token:
                continue
            if token in self.stopwords:
                continue
            if len(token) == 1 and re.match(r"[\u4e00-\u9fff]", token):
                continue
            tokens.append(token)
        return tokens

    def _token_jaccard_similarity(self, text_a: str, text_b: str) -> float:
        set_a = set(self._tokenize(text_a))
        set_b = set(self._tokenize(text_b))
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

    def _collection_get(self, where: Dict, include: Optional[List[str]] = None) -> Dict:
        try:
            kwargs = {"where": where}
            if include:
                kwargs["include"] = include
            return self.embedding_service.text_collection.get(**kwargs)
        except Exception as exc:
            logger.warning(f"Chroma 查询失败，尝试默认查询: {exc}")
            try:
                return self.embedding_service.text_collection.get(where=where)
            except Exception as fallback_exc:
                logger.error(f"Chroma 查询最终失败: {fallback_exc}")
                return {}

    def _build_compare_summary(
        self,
        overall_similarity: float,
        common_topics: List[str],
        unique_a: List[str],
        unique_b: List[str],
    ) -> str:
        if overall_similarity >= 0.8:
            level = "两份文档高度相似"
        elif overall_similarity >= 0.6:
            level = "两份文档中等相似"
        elif overall_similarity >= 0.4:
            level = "两份文档存在部分相似"
        else:
            level = "两份文档差异较大"

        common_text = "、".join(common_topics[:5]) if common_topics else "暂无明显共同主题"
        unique_a_text = "、".join(unique_a[:3]) if unique_a else "暂无明显独有主题"
        unique_b_text = "、".join(unique_b[:3]) if unique_b else "暂无明显独有主题"
        return f"{level}。共同主题：{common_text}。文档A偏向：{unique_a_text}。文档B偏向：{unique_b_text}。"

    def _normalize_style(self, style: str) -> str:
        lowered = style.lower()
        if lowered in {"detailed", "详细"}:
            return "详细"
        return "简洁"

    def _safe_int(self, value, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _cosine_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        if vec_a.shape != vec_b.shape:
            min_len = min(vec_a.shape[0], vec_b.shape[0])
            if min_len == 0:
                return 0.0
            vec_a = vec_a[:min_len]
            vec_b = vec_b[:min_len]

        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


analysis_service = AnalysisService()
