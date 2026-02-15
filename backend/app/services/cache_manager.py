"""
缓存管理器 - Phase 3
提供缓存监控、管理和统计功能
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from loguru import logger
import redis.asyncio as redis

from app.services.cache_service import cache_service
from app.config import settings


class CacheManager:
    """缓存管理器"""
    
    def __init__(self):
        self.cache_service = cache_service
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            缓存统计数据
        """
        try:
            redis_info = await self.cache_service.get_info()
            
            if not redis_info.get("connected"):
                return {
                    "status": "disconnected",
                    "message": "Redis未连接",
                    "timestamp": datetime.now().isoformat()
                }
            
            # 计算命中率
            hits = redis_info.get("keyspace_hits", 0)
            misses = redis_info.get("keyspace_misses", 0)
            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0
            
            return {
                "status": "connected",
                "memory": {
                    "used": redis_info.get("used_memory", "N/A"),
                    "peak": redis_info.get("used_memory_peak", "N/A")
                },
                "performance": {
                    "hit_rate": round(hit_rate, 2),
                    "hits": hits,
                    "misses": misses,
                    "total_requests": total
                },
                "connections": {
                    "clients": redis_info.get("connected_clients", 0)
                },
                "uptime": {
                    "seconds": redis_info.get("uptime_in_seconds", 0),
                    "human": self._format_uptime(redis_info.get("uptime_in_seconds", 0))
                },
                "commands": {
                    "total_processed": redis_info.get("total_commands_processed", 0)
                },
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def get_hot_keys(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取热点键统计
        
        Args:
            limit: 返回数量
            
        Returns:
            热点键列表
        """
        try:
            # 获取所有键的模式
            patterns = [
                "query:*",
                "document:*",
                "conversation:*",
                "user:*"
            ]
            
            hot_keys = []
            for pattern in patterns:
                keys = await self.cache_service.get_keys_by_pattern(pattern, limit=50)
                for key in keys:
                    ttl = await self.cache_service.get_ttl(key)
                    hot_keys.append({
                        "key": key,
                        "ttl": ttl,
                        "pattern": pattern.replace("*", "")
                    })
            
            # 按TTL排序（TTL越小说明越快过期，可能是热点数据）
            hot_keys.sort(key=lambda x: x["ttl"] if x["ttl"] > 0 else float('inf'))
            
            return hot_keys[:limit]
        except Exception as e:
            logger.error(f"获取热点键失败: {e}")
            return []
    
    async def clear_cache_by_type(self, cache_type: str) -> Dict[str, Any]:
        """
        按类型清除缓存
        
        Args:
            cache_type: 缓存类型 (query/document/conversation/user/all)
            
        Returns:
            清除结果
        """
        try:
            if cache_type == "all":
                # 清除所有缓存
                patterns = ["query:*", "document:*", "conversation:*", "user:*"]
                total_deleted = 0
                for pattern in patterns:
                    deleted = await self.cache_service.delete_pattern(pattern)
                    total_deleted += deleted
                
                logger.info(f"清除所有缓存，共删除 {total_deleted} 个键")
                return {
                    "success": True,
                    "type": "all",
                    "deleted_count": total_deleted,
                    "message": f"成功清除所有缓存，共 {total_deleted} 个键",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                # 清除指定类型缓存
                pattern = f"{cache_type}:*"
                deleted = await self.cache_service.delete_pattern(pattern)
                
                logger.info(f"清除 {cache_type} 缓存，共删除 {deleted} 个键")
                return {
                    "success": True,
                    "type": cache_type,
                    "deleted_count": deleted,
                    "message": f"成功清除 {cache_type} 缓存，共 {deleted} 个键",
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")
            return {
                "success": False,
                "type": cache_type,
                "deleted_count": 0,
                "message": f"清除缓存失败: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    async def clear_expired_cache(self) -> Dict[str, Any]:
        """
        清除过期缓存（Redis会自动清除，这里主要用于统计）
        
        Returns:
            清除结果
        """
        try:
            # Redis会自动清除过期键，这里只是获取统计信息
            info = await self.cache_service.get_info()
            
            return {
                "success": True,
                "message": "Redis自动管理过期键",
                "info": {
                    "expired_keys": info.get("expired_keys", 0),
                    "evicted_keys": info.get("evicted_keys", 0)
                },
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"清除过期缓存失败: {e}")
            return {
                "success": False,
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def warmup_cache(self, cache_types: List[str] = None) -> Dict[str, Any]:
        """
        缓存预热（加载热点数据）
        
        Args:
            cache_types: 要预热的缓存类型列表
            
        Returns:
            预热结果
        """
        try:
            if cache_types is None:
                cache_types = ["config"]
            
            warmed_count = 0
            results = []
            
            for cache_type in cache_types:
                if cache_type == "config":
                    # 预热配置缓存
                    from app.services.cache_service import get_config_cache
                    config_keys = ["max_file_size", "chunk_size", "chunk_overlap"]
                    for key in config_keys:
                        get_config_cache(key)
                        warmed_count += 1
                    results.append(f"配置缓存: {len(config_keys)} 项")
                
                # 可以添加更多预热逻辑
                # 例如：预热常用文档、热门查询等
            
            logger.info(f"缓存预热完成，共预热 {warmed_count} 项")
            return {
                "success": True,
                "warmed_count": warmed_count,
                "details": results,
                "message": f"缓存预热完成，共 {warmed_count} 项",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"缓存预热失败: {e}")
            return {
                "success": False,
                "warmed_count": 0,
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def get_cache_keys_count(self) -> Dict[str, int]:
        """
        获取各类型缓存键数量
        
        Returns:
            各类型键数量统计
        """
        try:
            patterns = {
                "query": "query:*",
                "document": "document:*",
                "conversation": "conversation:*",
                "user": "user:*"
            }
            
            counts = {}
            for name, pattern in patterns.items():
                keys = await self.cache_service.get_keys_by_pattern(pattern, limit=10000)
                counts[name] = len(keys)
            
            counts["total"] = sum(counts.values())
            return counts
        except Exception as e:
            logger.error(f"获取缓存键数量失败: {e}")
            return {"total": 0}
    
    async def get_cache_detail(self, key: str) -> Optional[Dict[str, Any]]:
        """
        获取指定缓存的详细信息
        
        Args:
            key: 缓存键
            
        Returns:
            缓存详细信息
        """
        try:
            exists = await self.cache_service.exists(key)
            if not exists:
                return None
            
            value = await self.cache_service.get(key)
            ttl = await self.cache_service.get_ttl(key)
            
            return {
                "key": key,
                "value": value,
                "ttl": ttl,
                "expires_at": (
                    datetime.now() + timedelta(seconds=ttl)
                ).isoformat() if ttl > 0 else "never",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"获取缓存详情失败 {key}: {e}")
            return None
    
    def _format_uptime(self, seconds: int) -> str:
        """
        格式化运行时间
        
        Args:
            seconds: 秒数
            
        Returns:
            格式化的时间字符串
        """
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}天")
        if hours > 0:
            parts.append(f"{hours}小时")
        if minutes > 0:
            parts.append(f"{minutes}分钟")
        if secs > 0 or not parts:
            parts.append(f"{secs}秒")
        
        return "".join(parts)


# 全局缓存管理器实例
cache_manager = CacheManager()

