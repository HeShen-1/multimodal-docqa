import asyncio
import os
from typing import Any, Dict, List

import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger

from app.config import Settings, get_settings
from app.services.clients import OllamaClient
from app.services.resilience_service import CircuitBreakerOpenError, resilience_manager
from app.utils.exceptions import LLMProviderError, OllamaConnectionError

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")


class EmbeddingService:
    """向量化服务。"""

    def __init__(self, settings: Settings = None):
        self.settings = settings or get_settings()
        self.embedding_model = self.settings.ollama_embedding_model
        self.ollama_client = OllamaClient(self.settings.ollama_base_url)

        self.chroma_client = chromadb.PersistentClient(
            path=self.settings.chroma_persist_dir,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                chroma_product_telemetry_impl="app.services.chroma_telemetry.NoOpProductTelemetryClient",
                chroma_telemetry_impl="app.services.chroma_telemetry.NoOpProductTelemetryClient",
            ),
        )

        try:
            self.text_collection = self.chroma_client.get_collection(name="text_chunks")
        except Exception:
            self.text_collection = self.chroma_client.create_collection(
                name="text_chunks",
                metadata={
                    "hnsw:space": "cosine",
                    "dimension": 1024,
                },
            )

        logger.info("EmbeddingService 初始化完成")

    async def encode_text(self, texts: List[str]) -> List[List[float]]:
        """文本向量化。"""
        try:
            embeddings: List[List[float]] = []

            batch_size = 8
            for index in range(0, len(texts), batch_size):
                batch = texts[index:index + batch_size]
                for text in batch:
                    normalized_text = self._normalize_text(text)
                    if not normalized_text:
                        logger.warning("跳过空文本")
                        continue
                    embeddings.extend(await self._encode_single_text(normalized_text))

            logger.info(f"成功向量化 {len(embeddings)} 条文本")
            return embeddings
        except OllamaConnectionError:
            raise
        except Exception as exc:
            logger.error(f"向量化过程异常: {exc}")
            raise OllamaConnectionError() from exc

    async def embed_query(self, query: str) -> List[float]:
        """对单条查询文本做向量化。"""
        embeddings = await self.encode_text([query])
        if not embeddings:
            raise OllamaConnectionError()
        return embeddings[0]

    def _normalize_text(self, text: str) -> str:
        if not text or not text.strip():
            return ""

        normalized = " ".join(text.split())
        max_length = 2000
        if len(normalized) > max_length:
            logger.warning(f"文本过长 ({len(normalized)} 字符)，截断到 {max_length} 字符")
            normalized = normalized[:max_length]
        return normalized

    async def _encode_single_text(self, text: str) -> List[List[float]]:
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                logger.info(f"发送向量化请求 (尝试 {retry_count + 1}/{max_retries})")
                logger.info(f"Model: {self.embedding_model}, Text Length: {len(text)}")

                async def _embed_once():
                    return await self.ollama_client.embed(
                        model=self.embedding_model,
                        text=text,
                        timeout=60,
                    )

                response_embeddings = await resilience_manager.execute(
                    service_name="ollama_embedding",
                    operation_name="embedding_encode",
                    operation=_embed_once,
                    timeout_seconds=60,
                    enable_retry=False,
                )

                if not response_embeddings:
                    raise OllamaConnectionError()

                embedding = response_embeddings[0]
                if len(embedding) != 1024:
                    logger.warning(f"向量维度异常: expected 1024, got {len(embedding)}")
                logger.info(f"成功获取向量，维度: {len(embedding)}")
                return [embedding]
            except CircuitBreakerOpenError:
                logger.error("Embedding 服务熔断开启")
                raise OllamaConnectionError()
            except (OllamaConnectionError, LLMProviderError):
                raise
            except Exception as exc:
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error(f"处理向量化响应时出错: {exc}")
                    raise
                logger.warning(f"请求失败: {exc}，等待 2 秒后重试...")
                await asyncio.sleep(2)

        raise OllamaConnectionError()

    async def add_text_chunks(self, document_id: str, chunks: List[Dict[str, Any]]):
        """添加文本块到向量数据库。"""
        if not chunks:
            return

        valid_chunks = [chunk for chunk in chunks if chunk.get("content", "").strip()]
        if not valid_chunks:
            logger.warning("没有有效的文本块需要向量化")
            return

        texts = [chunk["content"] for chunk in valid_chunks]
        embeddings = await self.encode_text(texts)

        metadatas = []
        ids = []

        for idx, chunk in enumerate(valid_chunks):
            chunk_id = f"{document_id}_chunk_{idx}"
            ids.append(chunk_id)
            metadatas.append(
                {
                    "document_id": document_id,
                    "page": chunk.get("page", 1),
                    "chunk_index": chunk.get("chunk_index", idx),
                    "type": chunk.get("type", "text"),
                    "parent_chunk_index": chunk.get("parent_chunk_index", -1),
                }
            )

        self.text_collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

        logger.info(f"成功添加 {len(valid_chunks)} 个文本块到向量数据库")

    async def get_document_chunks(self, document_id: str) -> List[Dict[str, Any]]:
        """获取文档的全部文本块。"""
        try:
            results = self.text_collection.get(
                where={"document_id": document_id},
                include=["documents", "metadatas"],
            )
        except Exception as exc:
            logger.error(f"读取文档 {document_id} 的切块失败: {exc}")
            return []

        documents = results.get("documents") or []
        metadatas = results.get("metadatas") or []
        ids = results.get("ids") or []
        chunks: List[Dict[str, Any]] = []

        for index, content in enumerate(documents):
            text = str(content or "").strip()
            if not text:
                continue

            metadata = metadatas[index] if index < len(metadatas) else {}
            chunk_id = ids[index] if index < len(ids) else f"{document_id}_chunk_{index}"
            try:
                page = int((metadata or {}).get("page", 1))
            except (TypeError, ValueError):
                page = 1
            try:
                chunk_index = int((metadata or {}).get("chunk_index", index))
            except (TypeError, ValueError):
                chunk_index = index
            try:
                parent_chunk_index = int((metadata or {}).get("parent_chunk_index", -1))
            except (TypeError, ValueError):
                parent_chunk_index = -1

            chunks.append(
                {
                    "id": chunk_id,
                    "content": text,
                    "page": page,
                    "chunkIndex": chunk_index,
                    "parentChunkIndex": parent_chunk_index,
                    "type": (metadata or {}).get("type", "text"),
                    "length": len(text),
                }
            )

        chunks.sort(key=lambda item: (item["page"], item["chunkIndex"]))
        return chunks

    async def list_text_chunks(self, document_ids: List[str] | None = None) -> List[Dict[str, Any]]:
        """列出指定文档的全部文本块，用于 BM25 或父子块回溯。"""
        where_filter = None
        if document_ids:
            where_filter = {"document_id": {"$in": document_ids}}

        try:
            results = self.text_collection.get(
                where=where_filter,
                include=["documents", "metadatas"],
            )
        except Exception as exc:
            logger.error(f"读取文本块列表失败: {exc}")
            return []

        documents = results.get("documents") or []
        metadatas = results.get("metadatas") or []
        ids = results.get("ids") or []
        items: List[Dict[str, Any]] = []

        for index, content in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            chunk_id = ids[index] if index < len(ids) else f"chunk_{index}"
            items.append(
                {
                    "id": chunk_id,
                    "content": str(content or ""),
                    "metadata": metadata or {},
                }
            )

        return items

    async def delete_document_chunks(self, document_id: str):
        """删除文档的所有向量。"""
        try:
            results = self.text_collection.get(where={"document_id": document_id})
            if results and results["ids"]:
                self.text_collection.delete(ids=results["ids"])
                logger.info(f"删除文档 {document_id} 的 {len(results['ids'])} 个向量")
        except Exception as exc:
            logger.error(f"删除向量失败: {exc}")

    async def search_similar(
        self,
        query: str,
        top_k: int = 5,
        document_ids: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """向量检索。"""
        query_embeddings = await self.encode_text([query])

        where_filter = None
        if document_ids:
            where_filter = {"document_id": {"$in": document_ids}}

        results = self.text_collection.query(
            query_embeddings=query_embeddings,
            n_results=top_k,
            where=where_filter,
        )

        formatted_results = []
        if results and results["ids"] and results["ids"][0]:
            for index in range(len(results["ids"][0])):
                formatted_results.append(
                    {
                        "id": results["ids"][0][index],
                        "content": results["documents"][0][index],
                        "metadata": results["metadatas"][0][index],
                        "distance": results["distances"][0][index] if "distances" in results else None,
                    }
                )

        return formatted_results

    async def close(self):
        """关闭连接。"""
        pass
