"""
缓存服务 - Phase 3
实现多级缓存架构（L1本地缓存 + L2 Redis缓存）
"""
import json
import hashlib
from typing import Any, Optional, Callable, List
from functools import wraps, lru_cache
from datetime import timedelta
import redis.asyncio as redis
from loguru import logger

from app.config import settings


class CacheService:
    """多级缓存服务"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self._connected = False
    
    async def connect(self):
        """连接Redis"""
        try:
            self.redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password if settings.redis_password else None,
                db=settings.redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True
            )
            # 测试连接
            await self.redis_client.ping()
            self._connected = True
            logger.info("Redis缓存连接成功")
        except Exception as e:
            logger.warning(f"Redis连接失败，将使用本地缓存: {e}")
            self._connected = False
    
    async def disconnect(self):
        """断开Redis连接"""
        if self.redis_client:
            await self.redis_client.aclose()
            self._connected = False
            logger.info("Redis缓存已断开")
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """
        生成缓存键
        
        Args:
            prefix: 键前缀
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            缓存键
        """
        # 将参数序列化为字符串
        key_parts = [str(arg) for arg in args]
        key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
        key_str = ":".join(key_parts)
        
        # 生成哈希值（避免键过长）
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        
        return f"{prefix}:{key_hash}"
    
    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，不存在返回None
        """
        if not self._connected or not self.redis_client:
            return None
        
        try:
            value = await self.redis_client.get(key)
            if value:
                logger.debug(f"缓存命中: {key}")
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"获取缓存失败 {key}: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        expire: Optional[int] = None
    ) -> bool:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            expire: 过期时间（秒）
            
        Returns:
            是否成功
        """
        if not self._connected or not self.redis_client:
            return False
        
        try:
            value_str = json.dumps(value, ensure_ascii=False)
            if expire:
                await self.redis_client.setex(key, expire, value_str)
            else:
                await self.redis_client.set(key, value_str)
            logger.debug(f"缓存设置成功: {key}")
            return True
        except Exception as e:
            logger.error(f"设置缓存失败 {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        删除缓存
        
        Args:
            key: 缓存键
            
        Returns:
            是否成功
        """
        if not self._connected or not self.redis_client:
            return False
        
        try:
            await self.redis_client.delete(key)
            logger.debug(f"缓存删除成功: {key}")
            return True
        except Exception as e:
            logger.error(f"删除缓存失败 {key}: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """
        删除匹配模式的所有缓存
        
        Args:
            pattern: 键模式（支持通配符*）
            
        Returns:
            删除的键数量
        """
        if not self._connected or not self.redis_client:
            return 0
        
        try:
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                deleted = await self.redis_client.delete(*keys)
                logger.info(f"批量删除缓存: {pattern}, 数量: {deleted}")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"批量删除缓存失败 {pattern}: {e}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """
        检查缓存是否存在
        
        Args:
            key: 缓存键
            
        Returns:
            是否存在
        """
        if not self._connected or not self.redis_client:
            return False
        
        try:
            return await self.redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"检查缓存失败 {key}: {e}")
            return False
    
    async def get_ttl(self, key: str) -> int:
        """
        获取缓存剩余过期时间
        
        Args:
            key: 缓存键
            
        Returns:
            剩余秒数，-1表示永不过期，-2表示不存在
        """
        if not self._connected or not self.redis_client:
            return -2
        
        try:
            return await self.redis_client.ttl(key)
        except Exception as e:
            logger.error(f"获取TTL失败 {key}: {e}")
            return -2
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """
        递增计数器
        
        Args:
            key: 缓存键
            amount: 递增量
            
        Returns:
            递增后的值
        """
        if not self._connected or not self.redis_client:
            return 0
        
        try:
            return await self.redis_client.incrby(key, amount)
        except Exception as e:
            logger.error(f"递增计数器失败 {key}: {e}")
            return 0
    
    async def get_info(self) -> dict:
        """
        获取Redis信息
        
        Returns:
            Redis统计信息
        """
        if not self._connected or not self.redis_client:
            return {"connected": False}
        
        try:
            info = await self.redis_client.info()
            return {
                "connected": True,
                "used_memory": info.get("used_memory_human", "N/A"),
                "used_memory_peak": info.get("used_memory_peak_human", "N/A"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0),
            }
        except Exception as e:
            logger.error(f"获取Redis信息失败: {e}")
            return {"connected": False, "error": str(e)}
    
    async def get_keys_by_pattern(self, pattern: str, limit: int = 100) -> List[str]:
        """
        获取匹配模式的键列表
        
        Args:
            pattern: 键模式
            limit: 最大返回数量
            
        Returns:
            键列表
        """
        if not self._connected or not self.redis_client:
            return []
        
        try:
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern, count=limit):
                keys.append(key)
                if len(keys) >= limit:
                    break
            return keys
        except Exception as e:
            logger.error(f"获取键列表失败 {pattern}: {e}")
            return []


# 全局缓存服务实例
cache_service = CacheService()


def cache_result(
    prefix: str,
    expire: int = 1800,
    key_builder: Optional[Callable] = None
):
    """
    缓存装饰器 - 用于缓存函数结果
    
    Args:
        prefix: 缓存键前缀
        expire: 过期时间（秒），默认30分钟
        key_builder: 自定义键生成函数
        
    Usage:
        @cache_result(prefix="query", expire=1800)
        async def query_documents(question: str, doc_ids: List[str]):
            # 查询逻辑
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = cache_service._generate_key(prefix, *args, **kwargs)
            
            # 尝试从缓存获取
            cached_value = await cache_service.get(cache_key)
            if cached_value is not None:
                logger.info(f"缓存命中: {prefix}")
                return cached_value
            
            # 缓存未命中，执行函数
            logger.info(f"缓存未命中: {prefix}，执行函数")
            result = await func(*args, **kwargs)
            
            # 存入缓存
            await cache_service.set(cache_key, result, expire)
            
            return result
        
        return wrapper
    return decorator


@lru_cache(maxsize=1000)
def get_config_cache(key: str) -> Any:
    """
    L1缓存 - 用于配置信息等不常变化的数据
    使用Python内置的LRU缓存
    
    Args:
        key: 配置键
        
    Returns:
        配置值
    """
    # 这里可以从配置文件或数据库加载
    # 示例实现
    config_map = {
        "max_file_size": settings.max_file_size,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
    }
    return config_map.get(key)


def clear_config_cache():
    """清除配置缓存"""
    get_config_cache.cache_clear()
    logger.info("配置缓存已清除")

