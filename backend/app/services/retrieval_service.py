import asyncio
from typing import List, Dict, Any
from loguru import logger
import jieba
from rank_bm25 import BM25Okapi

from app.services.embedding_service import EmbeddingService
from app.services.cache_service import cache_result
from app.utils.exceptions import RetrievalError
from app.config import settings


class RetrievalService:
    """混合检索服务"""
    
    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service
        self.bm25_index = None
        self.bm25_documents = []
    
    @cache_result(prefix="query", expire=settings.cache_query_expire)
    async def hybrid_search(
        self, 
        query: str, 
        top_k: int = 5,
        document_ids: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        混合检索（向量 + BM25）
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            document_ids: 指定文档ID列表
            
        Returns:
            融合后的检索结果
        """
        try:
            # 并行执行向量检索和BM25检索
            vector_results, bm25_results = await asyncio.gather(
                self._vector_search(query, top_k * 2, document_ids),
                self._bm25_search(query, top_k * 2, document_ids)
            )
            
            logger.info(f"向量检索: {len(vector_results)} 条, BM25检索: {len(bm25_results)} 条")
            
            # RRF融合
            fused_results = self._rrf_fusion(
                [vector_results, bm25_results],
                top_k
            )
            
            return fused_results
            
        except Exception as e:
            logger.error(f"混合检索失败: {e}")
            raise RetrievalError(str(e))
    
    async def _vector_search(
        self, 
        query: str, 
        top_k: int,
        document_ids: List[str] = None
    ) -> List[Dict]:
        """向量检索"""
        results = await self.embedding_service.search_similar(
            query=query,
            top_k=top_k,
            document_ids=document_ids
        )
        return results
    
    async def _bm25_search(
        self,
        query: str,
        top_k: int,
        document_ids: List[str] = None
    ) -> List[Dict]:
        """BM25检索"""
        if not self.bm25_index or not self.bm25_documents:
            # 如果BM25索引未构建，返回空结果
            logger.warning("BM25索引未构建")
            return []
        
        # 分词
        query_tokens = list(jieba.cut(query))
        
        # BM25检索
        scores = self.bm25_index.get_scores(query_tokens)
        
        # 获取top_k结果
        top_indices = sorted(
            range(len(scores)), 
            key=lambda i: scores[i], 
            reverse=True
        )[:top_k]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                doc = self.bm25_documents[idx]
                
                # 如果指定了文档ID，进行过滤
                if document_ids and doc['metadata'].get('document_id') not in document_ids:
                    continue
                
                results.append({
                    "id": doc['id'],
                    "content": doc['content'],
                    "metadata": doc['metadata'],
                    "score": float(scores[idx])
                })
        
        return results
    
    def _rrf_fusion(
        self, 
        results_list: List[List[Dict]], 
        top_k: int,
        k: int = 60
    ) -> List[Dict]:
        """
        RRF融合算法
        
        Args:
            results_list: 多路检索结果列表
            top_k: 返回数量
            k: RRF常数（默认60）
            
        Returns:
            融合后的结果
        """
        doc_scores = {}
        
        for results in results_list:
            for rank, doc in enumerate(results, start=1):
                doc_id = doc['id']
                score = 1.0 / (k + rank)
                
                if doc_id in doc_scores:
                    doc_scores[doc_id]['score'] += score
                else:
                    doc_scores[doc_id] = {
                        'doc': doc,
                        'score': score
                    }
        
        # 按分数排序
        sorted_docs = sorted(
            doc_scores.values(),
            key=lambda x: x['score'],
            reverse=True
        )
        
        return [item['doc'] for item in sorted_docs[:top_k]]
    
    async def build_bm25_index(self, documents: List[Dict]):
        """
        构建BM25索引
        
        Args:
            documents: 文档列表，每个包含id, content, metadata
        """
        if not documents:
            return
        
        logger.info(f"开始构建BM25索引，文档数: {len(documents)}")
        
        # 分词
        tokenized_docs = []
        for doc in documents:
            tokens = list(jieba.cut(doc['content']))
            tokenized_docs.append(tokens)
        
        # 创建BM25索引
        self.bm25_index = BM25Okapi(tokenized_docs)
        self.bm25_documents = documents
        
        logger.info("BM25索引构建完成")

