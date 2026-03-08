"""
多文档检索器

支持并行检索多个文档，使用RRF算法融合结果
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import asyncio
import hashlib
from loguru import logger


@dataclass
class SearchResult:
    """检索结果"""
    content: str              # 文本内容
    score: float              # 相关性分数
    document_id: str          # 文档ID
    document_name: str        # 文档名称
    page: Optional[int]       # 页码
    chunk_id: str             # 块ID
    metadata: Dict[str, Any]  # 元数据


class MultiDocRetriever:
    """多文档检索器"""
    
    def __init__(
        self,
        retrieval_service,
        cache_service,
        fusion_method: str = "rrf"
    ):
        """
        初始化多文档检索器
        
        Args:
            retrieval_service: 检索服务实例
            cache_service: 缓存服务实例
            fusion_method: 融合方法（rrf/weighted）
        """
        self.retrieval_service = retrieval_service
        self.cache_service = cache_service
        self.fusion_method = fusion_method
    
    async def retrieve(
        self,
        question: str,
        document_ids: List[str],
        top_k: int = 5,
        enable_rerank: bool = False
    ) -> Dict[str, Any]:
        """
        多文档联合检索
        
        Args:
            question: 用户问题
            document_ids: 文档ID列表
            top_k: 每个文档返回结果数
            enable_rerank: 是否启用重排序
            
        Returns:
            检索结果字典
        """
        # 1. 检查缓存
        cache_key = self._generate_cache_key(
            question, document_ids, top_k, enable_rerank
        )
        cached_result = await self.cache_service.get(cache_key)
        if cached_result:
            logger.info(f"缓存命中: {cache_key}")
            return cached_result
        
        # 2. 并行检索多个文档
        logger.info(f"开始并行检索 {len(document_ids)} 个文档")
        tasks = [
            self._retrieve_single_doc(question, doc_id, top_k)
            for doc_id in document_ids
        ]
        doc_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤异常结果
        valid_results = []
        for i, result in enumerate(doc_results):
            if isinstance(result, Exception):
                logger.error(f"检索文档 {document_ids[i]} 失败: {result}")
                continue
            valid_results.append(result)
        
        if not valid_results:
            raise ValueError("所有文档检索均失败")
        
        # 3. 融合结果
        fused_results = self._fuse_results(valid_results, top_k * len(document_ids))
        
        # 4. 可选：重排序
        if enable_rerank and fused_results:
            try:
                fused_results = await self._rerank_results(question, fused_results)
            except Exception as e:
                logger.warning(f"重排序失败，使用原始结果: {e}")
        
        # 5. 构建响应
        response = self._build_response(fused_results, valid_results)
        
        # 6. 保存到缓存
        await self.cache_service.set(cache_key, response, ttl=3600)
        
        return response
    
    async def _retrieve_single_doc(
        self,
        question: str,
        document_id: str,
        top_k: int
    ) -> List[SearchResult]:
        """检索单个文档"""
        try:
            results = await self.retrieval_service.retrieve(
                question=question,
                document_id=document_id,
                top_k=top_k
            )
            
            return [
                SearchResult(
                    content=r.get("content", ""),
                    score=r.get("score", 0.0),
                    document_id=document_id,
                    document_name=r.get("document_name", ""),
                    page=r.get("page"),
                    chunk_id=r.get("chunk_id", ""),
                    metadata=r.get("metadata", {})
                )
                for r in results
            ]
        except Exception as e:
            logger.error(f"检索文档 {document_id} 失败: {e}")
            raise
    
    def _fuse_results(
        self,
        doc_results: List[List[SearchResult]],
        total_k: int
    ) -> List[SearchResult]:
        """
        融合多个文档的检索结果
        
        使用RRF（Reciprocal Rank Fusion）算法
        """
        if self.fusion_method == "rrf":
            return self._rrf_fusion(doc_results, total_k)
        elif self.fusion_method == "weighted":
            return self._weighted_fusion(doc_results, total_k)
        else:
            raise ValueError(f"Unknown fusion method: {self.fusion_method}")
    
    def _rrf_fusion(
        self,
        doc_results: List[List[SearchResult]],
        k: int,
        rrf_k: int = 60
    ) -> List[SearchResult]:
        """
        RRF融合算法
        
        RRF Score = Σ(1 / (rank + k))
        
        Args:
            doc_results: 各文档的检索结果
            k: 返回结果数
            rrf_k: RRF参数，默认60
        """
        # 收集所有结果
        all_results = {}
        
        for results in doc_results:
            for rank, result in enumerate(results, start=1):
                key = f"{result.document_id}_{result.chunk_id}"
                
                if key not in all_results:
                    all_results[key] = {
                        "result": result,
                        "rrf_score": 0.0
                    }
                
                # 累加RRF分数
                all_results[key]["rrf_score"] += 1.0 / (rank + rrf_k)
        
        # 按RRF分数排序
        sorted_results = sorted(
            all_results.values(),
            key=lambda x: x["rrf_score"],
            reverse=True
        )
        
        # 更新分数并返回Top K
        final_results = []
        for item in sorted_results[:k]:
            result = item["result"]
            result.score = item["rrf_score"]
            final_results.append(result)
        
        return final_results
    
    def _weighted_fusion(
        self,
        doc_results: List[List[SearchResult]],
        k: int,
        weights: Optional[List[float]] = None
    ) -> List[SearchResult]:
        """
        加权融合算法
        
        Weighted Score = Σ(weight_i * score_i)
        """
        if weights is None:
            # 默认均等权重
            weights = [1.0 / len(doc_results)] * len(doc_results)
        
        # 收集所有结果
        all_results = {}
        
        for weight, results in zip(weights, doc_results):
            for result in results:
                key = f"{result.document_id}_{result.chunk_id}"
                
                if key not in all_results:
                    all_results[key] = {
                        "result": result,
                        "weighted_score": 0.0
                    }
                
                # 累加加权分数
                all_results[key]["weighted_score"] += weight * result.score
        
        # 按加权分数排序
        sorted_results = sorted(
            all_results.values(),
            key=lambda x: x["weighted_score"],
            reverse=True
        )
        
        # 更新分数并返回Top K
        final_results = []
        for item in sorted_results[:k]:
            result = item["result"]
            result.score = item["weighted_score"]
            final_results.append(result)
        
        return final_results
    
    async def _rerank_results(
        self,
        question: str,
        results: List[SearchResult]
    ) -> List[SearchResult]:
        """使用Rerank模型重排序"""
        from app.services.reranker_service import reranker_service
        
        candidates = [
            {
                "content": r.content,
                "metadata": {
                    "document_id": r.document_id,
                    "chunk_id": r.chunk_id
                }
            }
            for r in results
        ]
        
        reranked = await reranker_service.rerank(
            question=question,
            candidates=candidates,
            top_k=len(results)
        )
        
        # 创建新的结果列表，按重排序后的顺序
        reranked_results = []
        for reranked_item in reranked:
            # 找到对应的原始结果
            for result in results:
                if (result.document_id == reranked_item["metadata"]["document_id"] and
                    result.chunk_id == reranked_item["metadata"]["chunk_id"]):
                    result.score = reranked_item["score"]
                    reranked_results.append(result)
                    break
        
        return reranked_results
    
    def _build_response(
        self,
        results: List[SearchResult],
        doc_results: List[List[SearchResult]]
    ) -> Dict[str, Any]:
        """构建响应"""
        # 统计各文档信息
        document_stats = {}
        for doc_res in doc_results:
            if not doc_res:
                continue
            
            doc_id = doc_res[0].document_id
            doc_name = doc_res[0].document_name
            
            document_stats[doc_id] = {
                "name": doc_name,
                "matched_chunks": len(doc_res),
                "avg_score": sum(r.score for r in doc_res) / len(doc_res) if doc_res else 0
            }
        
        return {
            "results": [
                {
                    "content": r.content,
                    "score": r.score,
                    "document_id": r.document_id,
                    "document_name": r.document_name,
                    "page": r.page,
                    "chunk_id": r.chunk_id,
                    "metadata": r.metadata
                }
                for r in results
            ],
            "total": len(results),
            "fusion_method": self.fusion_method,
            "document_stats": document_stats
        }
    
    def _generate_cache_key(
        self,
        question: str,
        document_ids: List[str],
        top_k: int,
        enable_rerank: bool
    ) -> str:
        """生成缓存键"""
        key_parts = [
            question,
            ",".join(sorted(document_ids)),
            str(top_k),
            str(enable_rerank),
            self.fusion_method
        ]
        key_str = "|".join(key_parts)
        
        return f"multi_doc:{hashlib.md5(key_str.encode()).hexdigest()}"
