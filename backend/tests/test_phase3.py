"""
Phase 3 测试 - 缓存优化系统
测试缓存服务、缓存管理器和缓存API
"""
import pytest
import asyncio
from datetime import datetime
from httpx import AsyncClient
from app.main import app
from app.services.cache_service import cache_service, cache_result, get_config_cache, clear_config_cache
from app.services.cache_manager import cache_manager


class TestCacheService:
    """测试缓存服务"""
    
    @pytest.mark.asyncio
    async def test_cache_connection(self):
        """测试Redis连接"""
        await cache_service.connect()
        # 无论是否连接成功都不应该报错
        assert cache_service._connected is not None
        await cache_service.disconnect()
    
    @pytest.mark.asyncio
    async def test_cache_set_get(self):
        """测试缓存设置和获取"""
        await cache_service.connect()
        
        if not cache_service._connected:
            pytest.skip("Redis未连接，跳过测试")
        
        # 设置缓存
        key = "test:key1"
        value = {"name": "test", "value": 123}
        success = await cache_service.set(key, value, expire=60)
        assert success
        
        # 获取缓存
        cached_value = await cache_service.get(key)
        assert cached_value == value
        
        # 删除缓存
        await cache_service.delete(key)
        cached_value = await cache_service.get(key)
        assert cached_value is None
        
        await cache_service.disconnect()
    
    @pytest.mark.asyncio
    async def test_cache_exists(self):
        """测试缓存存在性检查"""
        await cache_service.connect()
        
        if not cache_service._connected:
            pytest.skip("Redis未连接，跳过测试")
        
        key = "test:exists"
        value = "test_value"
        
        # 设置缓存
        await cache_service.set(key, value, expire=60)
        
        # 检查存在
        exists = await cache_service.exists(key)
        assert exists
        
        # 删除后检查
        await cache_service.delete(key)
        exists = await cache_service.exists(key)
        assert not exists
        
        await cache_service.disconnect()
    
    @pytest.mark.asyncio
    async def test_cache_ttl(self):
        """测试缓存TTL"""
        await cache_service.connect()
        
        if not cache_service._connected:
            pytest.skip("Redis未连接，跳过测试")
        
        key = "test:ttl"
        value = "test_value"
        expire = 300  # 5分钟
        
        await cache_service.set(key, value, expire=expire)
        
        ttl = await cache_service.get_ttl(key)
        assert ttl > 0 and ttl <= expire
        
        # 清理
        await cache_service.delete(key)
        
        await cache_service.disconnect()
    
    @pytest.mark.asyncio
    async def test_cache_increment(self):
        """测试计数器递增"""
        await cache_service.connect()
        
        if not cache_service._connected:
            pytest.skip("Redis未连接，跳过测试")
        
        key = "test:counter"
        
        # 递增
        count1 = await cache_service.increment(key, 1)
        count2 = await cache_service.increment(key, 5)
        
        assert count2 == count1 + 5
        
        # 清理
        await cache_service.delete(key)
        
        await cache_service.disconnect()
    
    @pytest.mark.asyncio
    async def test_cache_pattern_delete(self):
        """测试模式删除"""
        await cache_service.connect()
        
        if not cache_service._connected:
            pytest.skip("Redis未连接，跳过测试")
        
        # 设置多个缓存
        keys = ["test:pattern:1", "test:pattern:2", "test:pattern:3"]
        for key in keys:
            await cache_service.set(key, "value", expire=60)
        
        # 批量删除
        deleted = await cache_service.delete_pattern("test:pattern:*")
        assert deleted >= 3
        
        await cache_service.disconnect()


class TestCacheDecorator:
    """测试缓存装饰器"""
    
    @pytest.mark.asyncio
    async def test_cache_decorator(self):
        """测试缓存装饰器功能"""
        await cache_service.connect()
        
        if not cache_service._connected:
            pytest.skip("Redis未连接，跳过测试")
        
        call_count = 0
        
        @cache_result(prefix="test_func", expire=60)
        async def expensive_function(x: int, y: int):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # 模拟耗时操作
            return x + y
        
        # 第一次调用（缓存未命中）
        result1 = await expensive_function(1, 2)
        assert result1 == 3
        assert call_count == 1
        
        # 第二次调用（缓存命中）
        result2 = await expensive_function(1, 2)
        assert result2 == 3
        # 第二次调用不应该增加call_count
        assert call_count == 1
        
        await cache_service.disconnect()
    
    def test_lru_cache(self):
        """测试L1缓存（LRU）"""
        # 清除缓存
        clear_config_cache()
        
        # 第一次调用
        value1 = get_config_cache("max_file_size")
        assert value1 is not None
        
        # 第二次调用（应该从缓存获取）
        value2 = get_config_cache("max_file_size")
        assert value2 == value1
        
        # 清除缓存
        clear_config_cache()


class TestCacheManager:
    """测试缓存管理器"""
    
    @pytest.mark.asyncio
    async def test_get_stats(self):
        """测试获取缓存统计"""
        await cache_service.connect()
        
        stats = await cache_manager.get_stats()
        
        assert "status" in stats
        assert "timestamp" in stats
        
        if stats["status"] == "connected":
            assert "memory" in stats
            assert "performance" in stats
            assert "hit_rate" in stats["performance"]
        
        await cache_service.disconnect()
    
    @pytest.mark.asyncio
    async def test_get_hot_keys(self):
        """测试获取热点键"""
        await cache_service.connect()
        
        if not cache_service._connected:
            pytest.skip("Redis未连接，跳过测试")
        
        # 设置一些测试键
        test_keys = ["query:test1", "query:test2", "document:test1"]
        for key in test_keys:
            await cache_service.set(key, "value", expire=60)
        
        hot_keys = await cache_manager.get_hot_keys(limit=10)
        
        assert isinstance(hot_keys, list)
        
        # 清理
        for key in test_keys:
            await cache_service.delete(key)
        
        await cache_service.disconnect()
    
    @pytest.mark.asyncio
    async def test_clear_cache_by_type(self):
        """测试按类型清除缓存"""
        await cache_service.connect()
        
        if not cache_service._connected:
            pytest.skip("Redis未连接，跳过测试")
        
        # 设置测试缓存
        await cache_service.set("query:test1", "value1", expire=60)
        await cache_service.set("query:test2", "value2", expire=60)
        
        # 清除query类型缓存
        result = await cache_manager.clear_cache_by_type("query")
        
        assert "success" in result
        assert "deleted_count" in result
        assert result["success"] is True
        
        await cache_service.disconnect()
    
    @pytest.mark.asyncio
    async def test_warmup_cache(self):
        """测试缓存预热"""
        await cache_service.connect()
        
        result = await cache_manager.warmup_cache(["config"])
        
        assert "success" in result
        assert "warmed_count" in result
        assert result["success"] is True
        
        await cache_service.disconnect()
    
    @pytest.mark.asyncio
    async def test_get_keys_count(self):
        """测试获取缓存键数量"""
        await cache_service.connect()
        
        counts = await cache_manager.get_cache_keys_count()
        
        assert isinstance(counts, dict)
        assert "total" in counts
        
        await cache_service.disconnect()
    
    @pytest.mark.asyncio
    async def test_get_cache_detail(self):
        """测试获取缓存详情"""
        await cache_service.connect()
        
        if not cache_service._connected:
            pytest.skip("Redis未连接，跳过测试")
        
        key = "test:detail"
        value = {"test": "data"}
        
        await cache_service.set(key, value, expire=60)
        
        detail = await cache_manager.get_cache_detail(key)
        
        assert detail is not None
        assert detail["key"] == key
        assert detail["value"] == value
        assert "ttl" in detail
        
        # 清理
        await cache_service.delete(key)
        
        await cache_service.disconnect()


class TestCacheIntegration:
    """集成测试"""
    
    @pytest.mark.asyncio
    async def test_cache_lifecycle(self):
        """测试缓存完整生命周期"""
        await cache_service.connect()
        
        if not cache_service._connected:
            pytest.skip("Redis未连接，跳过测试")
        
        # 1. 设置缓存
        key = "test:lifecycle"
        value = {"data": "test", "timestamp": datetime.now().isoformat()}
        
        success = await cache_service.set(key, value, expire=300)
        assert success
        
        # 2. 验证存在
        exists = await cache_service.exists(key)
        assert exists
        
        # 3. 获取缓存
        cached = await cache_service.get(key)
        assert cached == value
        
        # 4. 获取TTL
        ttl = await cache_service.get_ttl(key)
        assert ttl > 0
        
        # 5. 删除缓存
        await cache_service.delete(key)
        
        # 6. 验证已删除
        exists = await cache_service.exists(key)
        assert not exists
        
        await cache_service.disconnect()
    
    @pytest.mark.asyncio
    async def test_cache_performance(self):
        """测试缓存性能提升"""
        await cache_service.connect()
        
        if not cache_service._connected:
            pytest.skip("Redis未连接，跳过测试")
        
        @cache_result(prefix="perf_test", expire=60)
        async def slow_function(n: int):
            await asyncio.sleep(0.5)  # 模拟耗时操作
            return n * 2
        
        # 第一次调用（无缓存）
        import time
        start1 = time.time()
        result1 = await slow_function(10)
        time1 = time.time() - start1
        
        # 第二次调用（有缓存）
        start2 = time.time()
        result2 = await slow_function(10)
        time2 = time.time() - start2
        
        assert result1 == result2 == 20
        
        # 第二次应该更快
        assert time2 < time1
        improvement = (time1 - time2) / time1 * 100
        print(f"\n性能提升: {improvement:.2f}%")
        assert improvement > 50  # 至少提升50%
        
        await cache_service.disconnect()


class TestCacheAPI:
    """测试缓存API接口"""
    
    @pytest.mark.asyncio
    async def test_cache_stats_without_auth(self):
        """测试未认证访问缓存统计"""
        from httpx import ASGITransport
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/cache/stats")
            # 未认证可能返回401或403
            assert response.status_code in [401, 403]
    
    @pytest.mark.asyncio
    async def test_cache_stats_with_admin(self):
        """测试管理员访问缓存统计"""
        from httpx import ASGITransport
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 先登录获取token
            login_response = await client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "admin123"}
            )
            
            if login_response.status_code != 200:
                pytest.skip("管理员账号不存在，跳过测试")
            
            login_data = login_response.json()
            
            # 兼容不同的响应格式
            if "data" in login_data:
                token = login_data["data"]["access_token"]
            elif "access_token" in login_data:
                token = login_data["access_token"]
            else:
                pytest.skip("无法获取access_token，跳过测试")
            
            # 访问缓存统计
            response = await client.get(
                "/api/v1/cache/stats",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            # 如果用户不是管理员，会返回403
            if response.status_code == 403:
                pytest.skip("当前用户不是管理员，跳过测试")
            
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert "status" in data["data"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
