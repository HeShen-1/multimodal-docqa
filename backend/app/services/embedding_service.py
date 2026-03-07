import httpx
import requests
import os
import asyncio
from typing import List, Dict, Any
from loguru import logger

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import Settings, get_settings
from app.services.resilience_service import CircuitBreakerOpenError, resilience_manager
from app.utils.exceptions import OllamaConnectionError


class EmbeddingService:
    """向量化服务"""
    
    def __init__(self, settings: Settings = None):
        self.settings = settings or get_settings()
        
        # 使用 requests 而不是 httpx.AsyncClient (Windows 兼容性问题)
        self.ollama_base_url = self.settings.ollama_base_url.rstrip('/api')
        self.embedding_model = self.settings.ollama_embedding_model
        
        # 初始化ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=self.settings.chroma_persist_dir,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                chroma_product_telemetry_impl="app.services.chroma_telemetry.NoOpProductTelemetryClient",
                chroma_telemetry_impl="app.services.chroma_telemetry.NoOpProductTelemetryClient",
            ),
        )
        
        # 创建文本collection（明确指定维度为 1024）
        try:
            self.text_collection = self.chroma_client.get_collection(name="text_chunks")
        except:
            # 如果不存在则创建
            self.text_collection = self.chroma_client.create_collection(
                name="text_chunks",
                metadata={
                    "hnsw:space": "cosine",
                    "dimension": 1024  # qwen3-embedding:0.6b-fp16 的向量维度
                }
            )
        
        logger.info("EmbeddingService初始化完成")
    
    async def encode_text(self, texts: List[str]) -> List[List[float]]:
        """
        文本向量化
        
        Args:
            texts: 文本列表
            
        Returns:
            向量列表
        """
        try:
            embeddings = []
            
            # 批量处理（每批8条）
            batch_size = 8
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                for text in batch:
                    try:
                        # 确保文本不为空且长度合理
                        if not text or not text.strip():
                            logger.warning("跳过空文本")
                            continue
                        
                        # 清理文本：移除多余的空白字符
                        text = ' '.join(text.split())
                        
                        # 限制文本长度（避免超长文本导致 502）
                        max_length = 2000
                        if len(text) > max_length:
                            logger.warning(f"文本过长 ({len(text)} 字符)，截断到 {max_length} 字符")
                            text = text[:max_length]
                        
                        # 重试逻辑
                        max_retries = 3
                        retry_count = 0
                        
                        while retry_count < max_retries:
                            try:
                                # 使用 requests 库（在线程中运行以保持异步兼容）
                                def _sync_request():
                                    request_data = {
                                        "model": self.embedding_model,
                                        "input": text
                                    }
                                    url = f"{self.ollama_base_url}/api/embed"
                                    response = requests.post(url, json=request_data, timeout=60)
                                    return response
                                
                                logger.info(f"发送向量化请求 (尝试 {retry_count + 1}/{max_retries})")
                                logger.info(f"Model: {self.embedding_model}, Text Length: {len(text)}")
                                
                                # 在线程池中运行同步请求
                                response = await resilience_manager.execute(
                                    service_name="ollama_embedding",
                                    operation_name="embedding_encode",
                                    operation=_sync_request,
                                    timeout_seconds=60,
                                    enable_retry=False,
                                )
                                
                                logger.info(f"收到响应: status={response.status_code}")
                                
                                if response.status_code == 200:
                                    data = response.json()
                                    # Ollama /api/embed 返回 embeddings 数组
                                    if "embeddings" in data and len(data["embeddings"]) > 0:
                                        embeddings.append(data["embeddings"][0])
                                        break  # 成功，跳出重试循环
                                    elif "embedding" in data:
                                        embeddings.append(data["embedding"])
                                        break
                                    else:
                                        logger.error(f"响应格式错误: {data.keys()}")
                                        raise OllamaConnectionError()
                                else:
                                    error_text = response.text[:500] if response.text else ""
                                    logger.error(f"向量化失败 (状态码: {response.status_code})")
                                    logger.error(f"错误响应: {error_text}")
                                    
                                    # 如果是 502 或 400，可能是临时问题，重试
                                    if response.status_code in [400, 502] and retry_count < max_retries - 1:
                                        retry_count += 1
                                        logger.warning(f"收到 {response.status_code} 错误，等待 2 秒后重试...")
                                        await asyncio.sleep(2)
                                        continue
                                    else:
                                        logger.error(f"请求文本: {text[:100]}...")
                                        raise OllamaConnectionError()
                                        
                            except CircuitBreakerOpenError:
                                logger.error("Embedding 服务熔断开启")
                                raise OllamaConnectionError()
                            except requests.exceptions.ConnectionError as e:
                                logger.error(f"无法连接到Ollama服务: {e}")
                                raise OllamaConnectionError()
                            except OllamaConnectionError:
                                raise
                            except Exception as e:
                                if retry_count < max_retries - 1:
                                    retry_count += 1
                                    logger.warning(f"请求失败: {e}，等待 2 秒后重试...")
                                    await asyncio.sleep(2)
                                    continue
                                else:
                                    logger.error(f"处理向量化响应时出错: {e}")
                                    raise
                                    
                    except requests.exceptions.ConnectionError as e:
                        logger.error(f"无法连接到Ollama服务: {e}")
                        raise OllamaConnectionError()
                    except Exception as e:
                        logger.error(f"处理向量化响应时出错: {e}")
                        raise
            
            logger.info(f"成功向量化 {len(embeddings)} 条文本")
            return embeddings
            
        except OllamaConnectionError:
            raise
        except Exception as e:
            logger.error(f"向量化过程异常: {e}")
            raise OllamaConnectionError()

    async def embed_query(self, query: str) -> List[float]:
        """对单条查询文本做向量化"""
        embeddings = await self.encode_text([query])
        if not embeddings:
            raise OllamaConnectionError()
        return embeddings[0]
    
    async def add_text_chunks(
        self, 
        document_id: str,
        chunks: List[Dict[str, Any]]
    ):
        """
        添加文本块到向量数据库
        
        Args:
            document_id: 文档ID
            chunks: 文本块列表
        """
        if not chunks:
            return
        
        # 过滤掉空文本块
        valid_chunks = [chunk for chunk in chunks if chunk.get('content', '').strip()]
        if not valid_chunks:
            logger.warning("没有有效的文本块需要向量化")
            return
        
        texts = [chunk['content'] for chunk in valid_chunks]
        embeddings = await self.encode_text(texts)
        
        # 准备元数据
        metadatas = []
        ids = []
        
        for idx, chunk in enumerate(valid_chunks):
            chunk_id = f"{document_id}_chunk_{idx}"
            ids.append(chunk_id)
            
            metadatas.append({
                "document_id": document_id,
                "page": chunk.get('page', 1),
                "chunk_index": chunk.get('chunk_index', idx),
                "type": chunk.get('type', 'text')
            })
        
        # 添加到ChromaDB
        self.text_collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        
        logger.info(f"成功添加 {len(valid_chunks)} 个文本块到向量数据库")
    
    async def delete_document_chunks(self, document_id: str):
        """删除文档的所有向量"""
        try:
            # 查询该文档的所有chunk
            results = self.text_collection.get(
                where={"document_id": document_id}
            )
            
            if results and results['ids']:
                self.text_collection.delete(ids=results['ids'])
                logger.info(f"删除文档 {document_id} 的 {len(results['ids'])} 个向量")
        except Exception as e:
            logger.error(f"删除向量失败: {e}")
    
    async def search_similar(
        self,
        query: str,
        top_k: int = 5,
        document_ids: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        向量检索
        
        Args:
            query: 查询文本
            top_k: 返回数量
            document_ids: 指定文档ID列表
            
        Returns:
            检索结果列表
        """
        # 查询向量化
        query_embeddings = await self.encode_text([query])
        
        # 构建过滤条件
        where_filter = None
        if document_ids:
            where_filter = {"document_id": {"$in": document_ids}}
        
        # 检索
        results = self.text_collection.query(
            query_embeddings=query_embeddings,
            n_results=top_k,
            where=where_filter
        )
        
        # 格式化结果
        formatted_results = []
        if results and results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    "id": results['ids'][0][i],
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i] if 'distances' in results else None
                })
        
        return formatted_results
    
    async def close(self):
        """关闭连接"""
        # 使用 requests 库，无需关闭连接
        pass

