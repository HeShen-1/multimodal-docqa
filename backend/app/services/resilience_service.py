from __future__ import annotations

import asyncio
import inspect
import random
import threading
import time
from collections import Counter, deque
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Deque, Dict, Optional

import requests
from loguru import logger
from sqlalchemy import text

from app.config import get_settings
from app.services.cache_service import cache_service


class _NoOpMonitor:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


try:
    from app.services.monitoring_service import performance_monitor, task_monitor
except Exception:
    performance_monitor = _NoOpMonitor()
    task_monitor = _NoOpMonitor()

try:
    import psutil
except Exception:
    psutil = None


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class DegradationLevel(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class CircuitBreakerOpenError(RuntimeError):
    pass


class ServiceCircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        error_rate_threshold: float = 0.5,
        open_timeout_seconds: int = 60,
        half_open_success_threshold: int = 3,
        timeout_threshold_seconds: int = 10,
        min_error_rate_samples: int = 6,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.error_rate_threshold = error_rate_threshold
        self.open_timeout_seconds = open_timeout_seconds
        self.half_open_success_threshold = half_open_success_threshold
        self.timeout_threshold_seconds = timeout_threshold_seconds
        self.min_error_rate_samples = min_error_rate_samples

        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.half_open_successes = 0
        self.opened_at: Optional[float] = None
        self.last_failure_at: Optional[float] = None
        self.last_error: Optional[str] = None
        self._half_open_in_flight = False

        self.recent_outcomes: Deque[bool] = deque(maxlen=50)
        self._lock = threading.Lock()

    def _switch_state(self, new_state: CircuitState) -> None:
        if self.state == new_state:
            return
        logger.warning(f"熔断状态变更: service={self.name}, from={self.state.value}, to={new_state.value}")
        self.state = new_state
        if new_state == CircuitState.OPEN:
            self.opened_at = time.time()
            self._half_open_in_flight = False
            self.half_open_successes = 0
        elif new_state == CircuitState.CLOSED:
            self.opened_at = None
            self.consecutive_failures = 0
            self.half_open_successes = 0
            self._half_open_in_flight = False
        elif new_state == CircuitState.HALF_OPEN:
            self.half_open_successes = 0
            self._half_open_in_flight = False

    def allow_request(self) -> bool:
        with self._lock:
            if self.state == CircuitState.OPEN:
                if not self.opened_at:
                    self.opened_at = time.time()
                elapsed = time.time() - self.opened_at
                if elapsed >= self.open_timeout_seconds:
                    self._switch_state(CircuitState.HALF_OPEN)
                else:
                    return False

            if self.state == CircuitState.HALF_OPEN:
                if self._half_open_in_flight:
                    return False
                self._half_open_in_flight = True

            return True

    def record_success(self, duration_seconds: float) -> None:
        with self._lock:
            self.recent_outcomes.append(True)
            self.consecutive_failures = 0

            if self.state == CircuitState.HALF_OPEN:
                self.half_open_successes += 1
                self._half_open_in_flight = False
                if self.half_open_successes >= self.half_open_success_threshold:
                    self._switch_state(CircuitState.CLOSED)

            if duration_seconds > self.timeout_threshold_seconds:
                self.last_error = f"响应超时: {round(duration_seconds, 2)}s"
                self.last_failure_at = time.time()
                self.recent_outcomes.append(False)
                self.consecutive_failures += 1
                self._switch_state(CircuitState.OPEN)

    def record_failure(self, duration_seconds: float, error: Exception) -> None:
        with self._lock:
            self.last_error = str(error)
            self.last_failure_at = time.time()
            self.recent_outcomes.append(False)
            self.consecutive_failures += 1

            if self.state == CircuitState.HALF_OPEN:
                self._half_open_in_flight = False
                self._switch_state(CircuitState.OPEN)
                return

            if duration_seconds > self.timeout_threshold_seconds:
                self._switch_state(CircuitState.OPEN)
                return

            if self.consecutive_failures > self.failure_threshold:
                self._switch_state(CircuitState.OPEN)
                return

            if len(self.recent_outcomes) >= self.min_error_rate_samples:
                failure_count = sum(1 for ok in self.recent_outcomes if not ok)
                error_rate = failure_count / len(self.recent_outcomes)
                if error_rate > self.error_rate_threshold:
                    self._switch_state(CircuitState.OPEN)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            failure_count = sum(1 for ok in self.recent_outcomes if not ok)
            total = len(self.recent_outcomes)
            return {
                "service": self.name,
                "state": self.state.value,
                "consecutiveFailures": self.consecutive_failures,
                "errorRate": round(failure_count / total, 4) if total else 0.0,
                "recentSampleSize": total,
                "openedAt": datetime.utcfromtimestamp(self.opened_at).isoformat() if self.opened_at else None,
                "lastFailureAt": datetime.utcfromtimestamp(self.last_failure_at).isoformat()
                if self.last_failure_at
                else None,
                "lastError": self.last_error,
            }


class RetryMechanism:
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay_seconds: float = 1.0,
        max_delay_seconds: float = 30.0,
        request_timeout_seconds: float = 60.0,
    ):
        self.max_retries = max_retries
        self.initial_delay_seconds = initial_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.request_timeout_seconds = request_timeout_seconds

        self.retry_counter: Counter[str] = Counter()
        self.failure_counter: Counter[str] = Counter()
        self.success_counter: Counter[str] = Counter()
        self._result_cache: Dict[str, tuple[float, Any]] = {}
        self._cache_ttl_seconds = 600
        self._lock = threading.Lock()

    def _should_retry(self, error: Exception) -> bool:
        non_retryable = (CircuitBreakerOpenError, ValueError, TypeError)
        if isinstance(error, non_retryable):
            return False
        if isinstance(error, asyncio.TimeoutError):
            return True
        if isinstance(error, requests.ConnectionError):
            return True
        if isinstance(error, requests.Timeout):
            return True
        if isinstance(error, ConnectionError):
            return True
        return True

    async def _execute_once(
        self,
        operation: Callable[[], Any] | Callable[[], Awaitable[Any]],
        timeout_seconds: float,
    ) -> Any:
        if inspect.iscoroutinefunction(operation):
            return await asyncio.wait_for(operation(), timeout=timeout_seconds)

        return await asyncio.wait_for(asyncio.to_thread(operation), timeout=timeout_seconds)

    def _read_cached_result(self, key: Optional[str]) -> Optional[Any]:
        if not key:
            return None
        with self._lock:
            item = self._result_cache.get(key)
            if not item:
                return None
            cached_at, value = item
            if time.time() - cached_at > self._cache_ttl_seconds:
                self._result_cache.pop(key, None)
                return None
            return value

    def _cache_result(self, key: Optional[str], value: Any) -> None:
        if not key:
            return
        with self._lock:
            self._result_cache[key] = (time.time(), value)

    async def execute(
        self,
        operation_name: str,
        operation: Callable[[], Any] | Callable[[], Awaitable[Any]],
        timeout_seconds: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> Any:
        cached = self._read_cached_result(idempotency_key)
        if cached is not None:
            logger.info(f"幂等去重命中: operation={operation_name}, key={idempotency_key}")
            return cached

        timeout = timeout_seconds or self.request_timeout_seconds
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                result = await self._execute_once(operation=operation, timeout_seconds=timeout)
                self.success_counter[operation_name] += 1
                self._cache_result(idempotency_key, result)
                return result
            except Exception as exc:
                last_error = exc
                self.failure_counter[operation_name] += 1

                if attempt >= self.max_retries or not self._should_retry(exc):
                    raise

                self.retry_counter[operation_name] += 1
                base_delay = min(self.max_delay_seconds, self.initial_delay_seconds * (2 ** (attempt - 1)))
                jitter = random.uniform(0, min(1.0, base_delay * 0.2))
                wait_seconds = round(base_delay + jitter, 3)
                logger.warning(
                    f"请求重试: operation={operation_name}, attempt={attempt}/{self.max_retries}, "
                    f"wait={wait_seconds}s, error={exc}"
                )
                await asyncio.sleep(wait_seconds)

        if last_error:
            raise last_error
        raise RuntimeError(f"操作执行失败: {operation_name}")

    def snapshot(self) -> Dict[str, Any]:
        return {
            "maxRetries": self.max_retries,
            "initialDelaySeconds": self.initial_delay_seconds,
            "maxDelaySeconds": self.max_delay_seconds,
            "requestTimeoutSeconds": self.request_timeout_seconds,
            "retryCounter": dict(self.retry_counter),
            "failureCounter": dict(self.failure_counter),
            "successCounter": dict(self.success_counter),
        }


class GracefulDegradationManager:
    def __init__(self):
        self.current_level = DegradationLevel.L0
        self.manual_level: Optional[DegradationLevel] = None
        self.last_updated = datetime.utcnow()

        self.active_queries = 0
        self._lock = threading.Lock()

    def _determine_level(
        self, cpu_usage: float, memory_usage: float, queue_backlog: int, db_pool_exhausted: bool
    ) -> DegradationLevel:
        if db_pool_exhausted:
            return DegradationLevel.L3
        if cpu_usage > 90 or memory_usage > 90 or queue_backlog > 100:
            return DegradationLevel.L2
        if cpu_usage > 80:
            return DegradationLevel.L1
        return DegradationLevel.L0

    def evaluate(
        self,
        metrics: Dict[str, Any],
        queue_backlog: int = 0,
        db_pool_exhausted: bool = False,
    ) -> DegradationLevel:
        if self.manual_level is not None:
            return self.manual_level

        cpu_usage = metrics.get("cpu", {}).get("usagePercent") or 0.0
        memory_usage = metrics.get("memory", {}).get("usagePercent") or 0.0
        target_level = self._determine_level(
            cpu_usage=float(cpu_usage),
            memory_usage=float(memory_usage),
            queue_backlog=queue_backlog,
            db_pool_exhausted=db_pool_exhausted,
        )

        if target_level != self.current_level:
            logger.warning(f"降级级别变化: from={self.current_level.value}, to={target_level.value}")
            self.current_level = target_level
            self.last_updated = datetime.utcnow()

        return self.current_level

    def set_manual_level(self, level: DegradationLevel) -> None:
        self.manual_level = level
        self.current_level = level
        self.last_updated = datetime.utcnow()
        logger.warning(f"手动设置降级级别: {level.value}")

    def clear_manual_level(self) -> None:
        if self.manual_level is not None:
            logger.info("清除手动降级级别，恢复自动评估")
        self.manual_level = None
        self.last_updated = datetime.utcnow()

    def feature_flags(self) -> Dict[str, Any]:
        level = self.current_level

        if level == DegradationLevel.L0:
            return {
                "level": level.value,
                "recommendationEnabled": True,
                "documentRecommendationEnabled": True,
                "thinkingChainEnabled": True,
                "rerankEnabled": True,
                "simplifiedResponse": False,
                "maxRetrievalTopK": 8,
                "limitConcurrentQueries": False,
                "maxConcurrentQueries": 0,
                "uploadLimited": False,
                "basicQueryOnly": False,
            }
        if level == DegradationLevel.L1:
            return {
                "level": level.value,
                "recommendationEnabled": False,
                "documentRecommendationEnabled": False,
                "thinkingChainEnabled": True,
                "rerankEnabled": True,
                "simplifiedResponse": False,
                "maxRetrievalTopK": 5,
                "limitConcurrentQueries": False,
                "maxConcurrentQueries": 0,
                "uploadLimited": False,
                "basicQueryOnly": False,
            }
        if level == DegradationLevel.L2:
            return {
                "level": level.value,
                "recommendationEnabled": False,
                "documentRecommendationEnabled": False,
                "thinkingChainEnabled": False,
                "rerankEnabled": False,
                "simplifiedResponse": True,
                "maxRetrievalTopK": 3,
                "limitConcurrentQueries": False,
                "maxConcurrentQueries": 0,
                "uploadLimited": False,
                "basicQueryOnly": False,
            }
        return {
            "level": DegradationLevel.L3.value,
            "recommendationEnabled": False,
            "documentRecommendationEnabled": False,
            "thinkingChainEnabled": False,
            "rerankEnabled": False,
            "simplifiedResponse": True,
            "maxRetrievalTopK": 2,
            "limitConcurrentQueries": True,
            "maxConcurrentQueries": 2,
            "uploadLimited": True,
            "basicQueryOnly": True,
        }

    def try_acquire_query_slot(self) -> bool:
        flags = self.feature_flags()
        if not flags.get("limitConcurrentQueries"):
            return True

        with self._lock:
            max_queries = flags.get("maxConcurrentQueries", 1)
            if self.active_queries >= max_queries:
                return False
            self.active_queries += 1
            return True

    def release_query_slot(self) -> None:
        with self._lock:
            if self.active_queries > 0:
                self.active_queries -= 1

    def snapshot(self) -> Dict[str, Any]:
        return {
            "currentLevel": self.current_level.value,
            "manualLevel": self.manual_level.value if self.manual_level else None,
            "lastUpdated": self.last_updated.isoformat(),
            "activeQueries": self.active_queries,
            "flags": self.feature_flags(),
        }


class ResilienceManager:
    def __init__(self):
        self.breakers: Dict[str, ServiceCircuitBreaker] = {}
        self.retry_mechanism = RetryMechanism()
        self.degradation = GracefulDegradationManager()

    def _get_breaker(self, service_name: str) -> ServiceCircuitBreaker:
        if service_name not in self.breakers:
            self.breakers[service_name] = ServiceCircuitBreaker(name=service_name)
        return self.breakers[service_name]

    async def execute(
        self,
        service_name: str,
        operation_name: str,
        operation: Callable[[], Any] | Callable[[], Awaitable[Any]],
        timeout_seconds: float = 60,
        enable_retry: bool = True,
        idempotency_key: Optional[str] = None,
    ) -> Any:
        breaker = self._get_breaker(service_name)
        if not breaker.allow_request():
            raise CircuitBreakerOpenError(f"服务熔断中: {service_name}")

        start = time.perf_counter()
        try:
            if enable_retry:
                result = await self.retry_mechanism.execute(
                    operation_name=operation_name,
                    operation=operation,
                    timeout_seconds=timeout_seconds,
                    idempotency_key=idempotency_key,
                )
            else:
                result = await self.retry_mechanism._execute_once(operation, timeout_seconds=timeout_seconds)

            elapsed = time.perf_counter() - start
            breaker.record_success(elapsed)
            return result
        except Exception as exc:
            elapsed = time.perf_counter() - start
            breaker.record_failure(elapsed, exc)
            raise

    def evaluate_degradation(self) -> Dict[str, Any]:
        metrics = performance_monitor.collect_metrics()
        queue_backlog = metrics.get("queue", {}).get("backlog", task_monitor.batch_backlog())
        database = metrics.get("database", {})
        pool_size = database.get("poolSize")
        checked_out = database.get("checkedOut")
        db_pool_exhausted = (
            isinstance(pool_size, int)
            and isinstance(checked_out, int)
            and pool_size > 0
            and checked_out >= pool_size
        )
        level = self.degradation.evaluate(
            metrics=metrics,
            queue_backlog=int(queue_backlog) if isinstance(queue_backlog, int) else 0,
            db_pool_exhausted=db_pool_exhausted,
        )
        return {
            "level": level.value,
            "metrics": metrics,
            "queueBacklog": queue_backlog,
            "dbPoolExhausted": db_pool_exhausted,
            "flags": self.degradation.feature_flags(),
        }

    async def _check_database(self) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            from app.dependencies import get_session_maker

            session_maker = get_session_maker()
            async with session_maker() as session:
                await session.execute(text("SELECT 1"))
            return {
                "status": "healthy",
                "latencyMs": round((time.perf_counter() - start) * 1000, 3),
            }
        except Exception as exc:
            return {
                "status": "unhealthy",
                "latencyMs": round((time.perf_counter() - start) * 1000, 3),
                "error": str(exc),
            }

    async def _check_redis(self) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            if cache_service.redis_client and cache_service._connected:
                await cache_service.redis_client.ping()
            else:
                import redis.asyncio as redis

                settings = get_settings()
                redis_client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    password=settings.redis_password if settings.redis_password else None,
                    db=settings.redis_db,
                    decode_responses=True,
                )
                await redis_client.ping()
                await redis_client.aclose()
            return {
                "status": "healthy",
                "latencyMs": round((time.perf_counter() - start) * 1000, 3),
            }
        except Exception as exc:
            return {
                "status": "degraded",
                "latencyMs": round((time.perf_counter() - start) * 1000, 3),
                "error": str(exc),
            }

    async def _check_ollama(self) -> Dict[str, Any]:
        start = time.perf_counter()
        settings = get_settings()
        base_url = settings.ollama_base_url.rstrip("/api")
        url = f"{base_url}/api/tags"
        try:
            response = await asyncio.to_thread(lambda: requests.get(url, timeout=5))
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "latencyMs": round((time.perf_counter() - start) * 1000, 3),
                }
            return {
                "status": "unhealthy",
                "latencyMs": round((time.perf_counter() - start) * 1000, 3),
                "error": f"HTTP {response.status_code}",
            }
        except Exception as exc:
            return {
                "status": "unhealthy",
                "latencyMs": round((time.perf_counter() - start) * 1000, 3),
                "error": str(exc),
            }

    async def _check_vector_db(self) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            from app.services.embedding_service import EmbeddingService

            service = EmbeddingService()
            count = service.text_collection.count()
            return {
                "status": "healthy",
                "latencyMs": round((time.perf_counter() - start) * 1000, 3),
                "documents": count,
            }
        except Exception as exc:
            return {
                "status": "degraded",
                "latencyMs": round((time.perf_counter() - start) * 1000, 3),
                "error": str(exc),
            }

    async def _check_resources(self) -> Dict[str, Any]:
        if not psutil:
            return {
                "status": "unknown",
                "error": "psutil not installed",
            }

        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            cpu = psutil.cpu_percent(interval=0.1)

            status = "healthy"
            if cpu > 90 or memory.percent > 90:
                status = "degraded"
            if disk.percent > 95:
                status = "unhealthy"

            return {
                "status": status,
                "cpuPercent": round(cpu, 2),
                "memoryPercent": round(memory.percent, 2),
                "diskPercent": round(disk.percent, 2),
            }
        except Exception as exc:
            return {"status": "degraded", "error": str(exc)}

    async def check_health(self) -> Dict[str, Any]:
        database, redis_data, ollama, vector_db, resources = await asyncio.gather(
            self._check_database(),
            self._check_redis(),
            self._check_ollama(),
            self._check_vector_db(),
            self._check_resources(),
        )

        critical_components = [database, ollama]
        critical_failed = any(component.get("status") == "unhealthy" for component in critical_components)
        any_degraded = any(
            component.get("status") in {"degraded", "unhealthy"}
            for component in [database, redis_data, ollama, vector_db, resources]
        )

        if critical_failed:
            overall = "unhealthy"
        elif any_degraded:
            overall = "degraded"
        else:
            overall = "healthy"

        return {
            "status": overall,
            "checkedAt": datetime.utcnow().isoformat(),
            "components": {
                "database": database,
                "redis": redis_data,
                "ollama": ollama,
                "vectorDB": vector_db,
                "resources": resources,
            },
            "degradation": self.degradation.snapshot(),
        }

    def status_snapshot(self) -> Dict[str, Any]:
        return {
            "degradation": self.degradation.snapshot(),
            "retry": self.retry_mechanism.snapshot(),
            "circuitBreakers": {
                service_name: breaker.snapshot()
                for service_name, breaker in self.breakers.items()
            },
        }


resilience_manager = ResilienceManager()
