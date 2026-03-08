from __future__ import annotations

import base64
import json
import re
import threading
import time
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from loguru import logger

from app.celery_app import celery_app
from app.config import get_settings

try:
    import psutil
except Exception:
    psutil = None


def _safe_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).replace(tzinfo=None)
    except Exception:
        return None


def _percentile(values: List[float], percent: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = int((len(sorted_values) - 1) * percent)
    return round(sorted_values[index], 3)


def _get_batch_status_store() -> Dict[str, Any]:
    try:
        from app.services.batch_upload_service import batch_status_store

        return batch_status_store
    except Exception:
        return {}


class APIStatsCollector:
    def __init__(self, max_entries: int = 50000):
        self._entries: Deque[Dict[str, Any]] = deque(maxlen=max_entries)
        self._lock = threading.Lock()

    def extract_user_id(self, authorization: Optional[str]) -> Optional[str]:
        if not authorization or " " not in authorization:
            return None

        token = authorization.split(" ", 1)[1].strip()
        parts = token.split(".")
        if len(parts) != 3:
            return None

        payload = parts[1]
        payload += "=" * ((4 - len(payload) % 4) % 4)

        try:
            decoded = base64.urlsafe_b64decode(payload.encode("utf-8"))
            data = json.loads(decoded.decode("utf-8"))
            return data.get("sub") or data.get("username")
        except Exception:
            return None

    def record_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        user_id: Optional[str],
        request_id: str,
        client_ip: Optional[str],
    ) -> None:
        entry = {
            "timestamp": datetime.utcnow(),
            "method": method.upper(),
            "path": path,
            "endpoint": f"{method.upper()} {path}",
            "status_code": status_code,
            "duration_ms": round(duration_ms, 3),
            "user_id": user_id or "anonymous",
            "request_id": request_id,
            "client_ip": client_ip or "unknown",
            "is_error": status_code >= 400,
        }
        with self._lock:
            self._entries.append(entry)

    def get_report(self, hours: int = 24) -> Dict[str, Any]:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        with self._lock:
            entries = [entry.copy() for entry in self._entries if entry["timestamp"] >= cutoff]

        if not entries:
            return {
                "summary": {
                    "timeWindowHours": hours,
                    "totalRequests": 0,
                    "errorRequests": 0,
                    "errorRate": 0.0,
                    "avgResponseMs": 0.0,
                    "p95ResponseMs": 0.0,
                    "uniqueUsers": 0,
                },
                "endpointStats": [],
                "userStats": [],
                "trend": [],
            }

        durations = [entry["duration_ms"] for entry in entries]
        errors = sum(1 for entry in entries if entry["is_error"])
        unique_users = len({entry["user_id"] for entry in entries if entry["user_id"] != "anonymous"})

        endpoint_bucket: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "errors": 0, "durations": [], "statusCodes": Counter()}
        )
        user_bucket: Counter[str] = Counter()
        trend_bucket: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"requests": 0, "errors": 0, "durations": []}
        )

        for entry in entries:
            endpoint_data = endpoint_bucket[entry["endpoint"]]
            endpoint_data["count"] += 1
            endpoint_data["errors"] += 1 if entry["is_error"] else 0
            endpoint_data["durations"].append(entry["duration_ms"])
            endpoint_data["statusCodes"][entry["status_code"]] += 1

            user_bucket[entry["user_id"]] += 1

            minute_key = entry["timestamp"].strftime("%Y-%m-%d %H:%M")
            trend_data = trend_bucket[minute_key]
            trend_data["requests"] += 1
            trend_data["errors"] += 1 if entry["is_error"] else 0
            trend_data["durations"].append(entry["duration_ms"])

        endpoint_stats = []
        for endpoint, data in endpoint_bucket.items():
            count = data["count"]
            errors_count = data["errors"]
            endpoint_stats.append(
                {
                    "endpoint": endpoint,
                    "count": count,
                    "errorCount": errors_count,
                    "errorRate": round(errors_count / count, 4) if count else 0.0,
                    "avgResponseMs": round(sum(data["durations"]) / count, 3) if count else 0.0,
                    "p95ResponseMs": _percentile(data["durations"], 0.95),
                    "statusCodes": dict(data["statusCodes"]),
                }
            )
        endpoint_stats.sort(key=lambda item: item["count"], reverse=True)

        user_stats = [
            {"userId": user_id, "count": count}
            for user_id, count in user_bucket.most_common(20)
        ]

        trend = []
        for minute, data in sorted(trend_bucket.items()):
            trend.append(
                {
                    "time": minute,
                    "requests": data["requests"],
                    "errors": data["errors"],
                    "avgResponseMs": round(
                        sum(data["durations"]) / len(data["durations"]), 3
                    )
                    if data["durations"]
                    else 0.0,
                }
            )

        return {
            "summary": {
                "timeWindowHours": hours,
                "totalRequests": len(entries),
                "errorRequests": errors,
                "errorRate": round(errors / len(entries), 4),
                "avgResponseMs": round(sum(durations) / len(durations), 3),
                "p95ResponseMs": _percentile(durations, 0.95),
                "uniqueUsers": unique_users,
            },
            "endpointStats": endpoint_stats,
            "userStats": user_stats,
            "trend": trend,
        }


class TaskMonitor:
    def __init__(self):
        self._runtime_samples: Deque[float] = deque(maxlen=5000)
        self._failed_tasks: Deque[Dict[str, Any]] = deque(maxlen=500)

    def record_failed_task(self, task_id: str, task_name: str, reason: str) -> None:
        self._failed_tasks.appendleft(
            {
                "taskId": task_id,
                "taskName": task_name,
                "reason": reason,
                "source": "runtime",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def _inspect(self) -> Dict[str, Dict[str, Any]]:
        try:
            inspector = celery_app.control.inspect(timeout=1.5)
            return {
                "active": inspector.active() or {},
                "reserved": inspector.reserved() or {},
                "scheduled": inspector.scheduled() or {},
                "ping": inspector.ping() or {},
                "stats": inspector.stats() or {},
            }
        except Exception as exc:
            logger.warning(f"Celery inspect 失败，降级返回空监控数据: {exc}")
            return {
                "active": {},
                "reserved": {},
                "scheduled": {},
                "ping": {},
                "stats": {},
            }

    def _runtime_distribution(self) -> Dict[str, int]:
        distribution = {"lt1s": 0, "s1to3": 0, "s3to10": 0, "gte10s": 0}
        for runtime in self._runtime_samples:
            if runtime < 1:
                distribution["lt1s"] += 1
            elif runtime < 3:
                distribution["s1to3"] += 1
            elif runtime < 10:
                distribution["s3to10"] += 1
            else:
                distribution["gte10s"] += 1
        return distribution

    def _batch_failed_tasks(self) -> List[Dict[str, Any]]:
        failed_tasks: List[Dict[str, Any]] = []
        batch_status_store = _get_batch_status_store()
        for batch in batch_status_store.values():
            for task in batch.get("documents", []):
                if task.get("status") == "failed":
                    failed_tasks.append(
                        {
                            "taskId": task.get("document_id"),
                            "taskName": "tasks.process_single_document",
                            "reason": task.get("message", "unknown"),
                            "batchId": batch.get("batch_id"),
                            "source": "batch_upload",
                            "timestamp": batch.get("created_at"),
                        }
                    )
        return failed_tasks

    def batch_backlog(self) -> int:
        backlog = 0
        batch_status_store = _get_batch_status_store()
        for batch in batch_status_store.values():
            backlog += int(batch.get("processing", 0))
        return backlog

    def get_snapshot(self) -> Dict[str, Any]:
        inspect_data = self._inspect()
        active = inspect_data["active"]
        reserved = inspect_data["reserved"]
        scheduled = inspect_data["scheduled"]
        ping = inspect_data["ping"]
        stats = inspect_data["stats"]

        active_tasks: List[Dict[str, Any]] = []
        for worker, tasks in active.items():
            for task in tasks:
                runtime_seconds = None
                time_start = task.get("time_start")
                if isinstance(time_start, (int, float)):
                    runtime_seconds = max(0.0, time.time() - float(time_start))
                    self._runtime_samples.append(runtime_seconds)

                active_tasks.append(
                    {
                        "taskId": task.get("id"),
                        "taskName": task.get("name"),
                        "worker": worker,
                        "args": task.get("args"),
                        "kwargs": task.get("kwargs"),
                        "runtimeSeconds": round(runtime_seconds, 3) if runtime_seconds else None,
                    }
                )

        pending_tasks = sum(len(items) for items in reserved.values()) + sum(
            len(items) for items in scheduled.values()
        )
        running_tasks = sum(len(items) for items in active.values())

        workers = []
        for worker_name in sorted(set(active.keys()) | set(reserved.keys()) | set(ping.keys()) | set(stats.keys())):
            worker_stats = stats.get(worker_name, {})
            total_tasks = 0
            total_dict = worker_stats.get("total")
            if isinstance(total_dict, dict):
                total_tasks = sum(total_dict.values())

            workers.append(
                {
                    "name": worker_name,
                    "healthy": worker_name in ping,
                    "activeTasks": len(active.get(worker_name, [])),
                    "reservedTasks": len(reserved.get(worker_name, [])),
                    "processedTasks": total_tasks,
                }
            )

        failed_tasks = list(self._failed_tasks) + self._batch_failed_tasks()
        failed_tasks = failed_tasks[:100]

        return {
            "pendingTasks": pending_tasks,
            "runningTasks": running_tasks,
            "failedTaskCount": len(failed_tasks),
            "failedTasks": failed_tasks,
            "activeTasks": active_tasks[:100],
            "workers": workers,
            "taskExecutionTimeDistribution": self._runtime_distribution(),
            "batchBacklog": self.batch_backlog(),
            "updatedAt": datetime.utcnow().isoformat(),
        }

    def retry_task(
        self,
        task_name: str,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        result = celery_app.send_task(task_name, args=args or [], kwargs=kwargs or {})
        logger.info(f"手动重试任务: task_name={task_name}, new_task_id={result.id}")
        return {"taskId": result.id, "taskName": task_name}

    def cancel_task(self, task_id: str, terminate: bool = True, signal: str = "SIGTERM") -> None:
        celery_app.control.revoke(task_id, terminate=terminate, signal=signal)
        logger.warning(f"任务已撤销: task_id={task_id}, terminate={terminate}, signal={signal}")

    def cleanup_zombie_tasks(self, max_runtime_seconds: int = 3600) -> Dict[str, Any]:
        inspect_data = self._inspect()
        active = inspect_data["active"]

        revoked_ids: List[str] = []
        now = time.time()
        for worker, tasks in active.items():
            for task in tasks:
                time_start = task.get("time_start")
                task_id = task.get("id")
                if not isinstance(time_start, (int, float)) or not task_id:
                    continue
                runtime = max(0.0, now - float(time_start))
                if runtime >= max_runtime_seconds:
                    celery_app.control.revoke(task_id, terminate=True, signal="SIGKILL")
                    revoked_ids.append(task_id)
                    logger.warning(
                        f"清理僵尸任务: worker={worker}, task_id={task_id}, runtime={round(runtime, 2)}s"
                    )

        return {"revokedTaskIds": revoked_ids, "count": len(revoked_ids)}


class LogManager:
    LOG_PATTERN = re.compile(
        r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| "
        r"(?P<level>[A-Z]+)\s*\| (?P<source>.*?) - (?P<message>.*)$"
    )

    def __init__(self):
        self.settings = get_settings()

    def _error_type(self, message: str) -> str:
        if not message:
            return "unknown"
        head = message.split(":", 1)[0].strip()
        return head[:120] if head else "unknown"

    def query_errors(
        self,
        levels: Optional[List[str]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        keyword: Optional[str] = None,
        regex_pattern: Optional[str] = None,
        limit: int = 200,
    ) -> Dict[str, Any]:
        level_set = {level.strip().upper() for level in (levels or ["ERROR", "WARNING", "CRITICAL"]) if level}
        start_dt = _safe_datetime(start_time)
        end_dt = _safe_datetime(end_time)
        matcher = re.compile(regex_pattern) if regex_pattern else None

        log_path = Path(self.settings.log_file)
        if not log_path.exists():
            return {
                "totalMatched": 0,
                "logs": [],
                "summary": {
                    "levels": {},
                    "errorTypes": [],
                    "trend": [],
                },
            }

        matched_logs: List[Dict[str, Any]] = []
        with log_path.open("r", encoding="utf-8", errors="ignore") as file:
            for raw_line in file:
                line = raw_line.strip()
                if not line:
                    continue

                parsed = self.LOG_PATTERN.match(line)
                if not parsed:
                    continue

                timestamp_text = parsed.group("timestamp")
                level = parsed.group("level").upper()
                source = parsed.group("source").strip()
                message = parsed.group("message").strip()

                if level not in level_set:
                    continue

                timestamp = datetime.strptime(timestamp_text, "%Y-%m-%d %H:%M:%S")
                if start_dt and timestamp < start_dt:
                    continue
                if end_dt and timestamp > end_dt:
                    continue

                if keyword and keyword.lower() not in message.lower():
                    continue
                if matcher and not matcher.search(message):
                    continue

                matched_logs.append(
                    {
                        "timestamp": timestamp.isoformat(),
                        "level": level,
                        "source": source,
                        "message": message,
                    }
                )

        matched_logs.sort(key=lambda item: item["timestamp"], reverse=True)
        trimmed = matched_logs[:limit]

        level_counter = Counter(item["level"] for item in matched_logs)
        error_counter = Counter(self._error_type(item["message"]) for item in matched_logs)
        trend_counter = Counter(item["timestamp"][:13] for item in matched_logs)

        return {
            "totalMatched": len(matched_logs),
            "logs": trimmed,
            "summary": {
                "levels": dict(level_counter),
                "errorTypes": [
                    {"type": error_type, "count": count}
                    for error_type, count in error_counter.most_common(10)
                ],
                "trend": [
                    {"time": bucket + ":00:00", "count": count}
                    for bucket, count in sorted(trend_counter.items())
                ],
            },
        }


class PerformanceMonitor:
    def __init__(self, stats_collector: APIStatsCollector, task_monitor: TaskMonitor):
        self.stats_collector = stats_collector
        self.task_monitor = task_monitor

    def collect_metrics(self) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {"timestamp": datetime.utcnow().isoformat()}

        if psutil:
            cpu_usage = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_io_counters()
            network = psutil.net_io_counters()

            metrics["cpu"] = {"usagePercent": round(cpu_usage, 2)}
            metrics["memory"] = {
                "usagePercent": round(memory.percent, 2),
                "usedBytes": int(memory.used),
                "totalBytes": int(memory.total),
            }
            metrics["diskIO"] = {
                "readBytes": int(disk.read_bytes) if disk else 0,
                "writeBytes": int(disk.write_bytes) if disk else 0,
            }
            metrics["network"] = {
                "bytesSent": int(network.bytes_sent) if network else 0,
                "bytesReceived": int(network.bytes_recv) if network else 0,
            }
        else:
            metrics["cpu"] = {"usagePercent": None}
            metrics["memory"] = {"usagePercent": None, "usedBytes": None, "totalBytes": None}
            metrics["diskIO"] = {"readBytes": None, "writeBytes": None}
            metrics["network"] = {"bytesSent": None, "bytesReceived": None}

        try:
            from app.dependencies import get_engine

            engine = get_engine()
            pool = engine.pool
            metrics["database"] = {
                "poolSize": pool.size(),
                "checkedIn": pool.checkedin(),
                "checkedOut": pool.checkedout(),
                "overflow": pool.overflow(),
            }
        except Exception as exc:
            metrics["database"] = {"error": str(exc)}

        api_summary = self.stats_collector.get_report(hours=1).get("summary", {})
        metrics["api"] = {
            "avgResponseMs": api_summary.get("avgResponseMs", 0.0),
            "p95ResponseMs": api_summary.get("p95ResponseMs", 0.0),
            "errorRate": api_summary.get("errorRate", 0.0),
            "requestsLastHour": api_summary.get("totalRequests", 0),
        }
        metrics["queue"] = {"backlog": self.task_monitor.batch_backlog()}

        return metrics

    def evaluate_alerts(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        alerts: List[Dict[str, Any]] = []

        cpu_usage = metrics.get("cpu", {}).get("usagePercent")
        if isinstance(cpu_usage, (int, float)) and cpu_usage > 80:
            alerts.append({"type": "cpu", "level": "warning", "message": f"CPU 使用率过高: {cpu_usage}%"})

        memory_usage = metrics.get("memory", {}).get("usagePercent")
        if isinstance(memory_usage, (int, float)) and memory_usage > 90:
            alerts.append({"type": "memory", "level": "critical", "message": f"内存使用率过高: {memory_usage}%"})

        queue_backlog = metrics.get("queue", {}).get("backlog", 0)
        if isinstance(queue_backlog, int) and queue_backlog > 100:
            alerts.append({"type": "queue", "level": "critical", "message": f"任务队列积压: {queue_backlog}"})

        db = metrics.get("database", {})
        pool_size = db.get("poolSize")
        checked_out = db.get("checkedOut")
        if isinstance(pool_size, int) and isinstance(checked_out, int) and pool_size > 0 and checked_out >= pool_size:
            alerts.append({"type": "database", "level": "critical", "message": "数据库连接池接近耗尽"})

        return alerts


api_stats_collector = APIStatsCollector()
task_monitor = TaskMonitor()
log_manager = LogManager()
performance_monitor = PerformanceMonitor(api_stats_collector, task_monitor)
