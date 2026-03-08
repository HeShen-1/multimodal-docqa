"""
重排序服务

使用专门的Rerank模型优化检索结果排序
"""
from typing import List, Dict, Any, Optional
import numpy as np
import hashlib
from loguru import logger


class RerankerService:
    """重排序服务"""
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-base",
        cache_service = None,
        device: str = "cpu"
    ):
        """
        初始化重排序服务
        
        Args:
            model_name: Rerank模型名称
            cache_service: 缓存服务实例
            device: 设备（cpu/cuda）
        """
        self.model_name = model_name
        self.cache_service = cache_service
        self.device = device
        self.model = None
    
    def load_model(self):
        """加载Rerank模型"""
        if self.model is None:
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"加载Rerank模型: {self.model_name}")
                self.model = CrossEncoder(
                    self.model_name,
                    max_length=512,
                    device=self.device
                )
                logger.info("Rerank模型加载成功")
            except Exception as e:
                logger.error(f"加载Rerank模型失败: {e}")
                raise
    
    async def rerank(
        self,
        question: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        重排序候选结果
        
        Args:
            question: 用户问题
            candidates: 候选结果列表
            top_k: 返回结果数
            
        Returns:
            重排序后的结果列表
        """
        if not candidates:
            return []
        
        # 1. 检查缓存
        if self.cache_service:
            cache_key = self._generate_cache_key(question, candidates)
            cached_result = await self.cache_service.get(cache_key)
            if cached_result:
                logger.info(f"Rerank缓存命中: {cache_key}")
                return cached_result[:top_k]
        
        # 2. 加载模型
        self.load_model()
        
        # 3. 准备输入对
        pairs = [
            [question, candidate["content"]]
            for candidate in candidates
        ]
        
        # 4. 批量计算分数
        try:
            scores = self.model.predict(pairs, batch_size=32)
        except Exception as e:
            logger.error(f"Rerank预测失败: {e}")
            # 如果重排序失败，返回原始结果
            return candidates[:top_k]
        
        # 5. 排序
        ranked_indices = np.argsort(scores)[::-1]
        
        # 6. 构建结果
        results = []
        for new_rank, idx in enumerate(ranked_indices, start=1):
            result = candidates[idx].copy()
            result["score"] = float(scores[idx])
            result["original_rank"] = int(idx) + 1
            result["new_rank"] = int(new_rank)
            results.append(result)
        
        # 7. 保存到缓存
        if self.cache_service:
            await self.cache_service.set(cache_key, results, ttl=3600)
        
        return results[:top_k]
    
    def _generate_cache_key(
        self,
        question: str,
        candidates: List[Dict[str, Any]]
    ) -> str:
        """生成缓存键"""
        # 使用问题和候选内容的哈希作为键
        content_hash = hashlib.md5(
            (question + "|" + "|".join(c["content"] for c in candidates)).encode()
        ).hexdigest()
        
        return f"rerank:{self.model_name}:{content_hash}"


# 全局实例（延迟初始化）
_reranker_service = None


def get_reranker_service(
    model_name: str = "BAAI/bge-reranker-base",
    cache_service = None,
    device: str = "cpu"
) -> RerankerService:
    """获取重排序服务实例"""
    global _reranker_service
    if _reranker_service is None:
        _reranker_service = RerankerService(
            model_name=model_name,
            cache_service=cache_service,
            device=device
        )
    return _reranker_service


# 便捷访问
reranker_service = get_reranker_service()
