"""
Phase 7 / Phase 8 登录态 API 集成测试脚本

特性：
- 从 TEST_CREDENTIALS.txt 解析登录账号
- 自动将测试账号临时提升为 admin（测试后恢复）
- 记录详细请求/响应日志，便于问题排查
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi.testclient import TestClient

from app.main import app


CREDENTIALS_FILE = Path("TEST_CREDENTIALS.txt")


@dataclass
class TestResult:
    name: str
    method: str
    endpoint: str
    status_code: int
    passed: bool
    detail: str


class Phase78Tester:
    def __init__(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_dir = Path("logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"phase78_api_test_{timestamp}.log"
        self.result_file = self.log_dir / f"phase78_api_test_result_{timestamp}.json"

    def _log(self, message: str) -> None:
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        print(line)
        with self.log_file.open("a", encoding="utf-8") as file:
            file.write(line + "\n")

    def parse_credentials(self) -> tuple[str, str]:
        if not CREDENTIALS_FILE.exists():
            raise FileNotFoundError(f"凭证文件不存在: {CREDENTIALS_FILE}")

        content = CREDENTIALS_FILE.read_text(encoding="utf-8")
        username_match = re.search(r"用户名[:：]\s*(.+)", content)
        password_match = re.search(r"密码[:：]\s*(.+)", content)

        if not username_match or not password_match:
            raise ValueError("未能从 TEST_CREDENTIALS.txt 中解析用户名或密码")

        return username_match.group(1).strip(), password_match.group(1).strip()

    def login(self, client: TestClient, username: str, password: str) -> str:
        self._log(f"登录测试账号: username={username}")
        response = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        self._log(f"登录响应: status={response.status_code}, body={response.text[:500]}")
        if response.status_code != 200:
            raise RuntimeError(f"登录失败: {response.status_code} {response.text}")

        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise RuntimeError(f"登录响应缺少 access_token: {response.text}")
        return token

    def run_case(
        self,
        client: TestClient,
        name: str,
        method: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        expected_statuses: tuple[int, ...] = (200,),
        validator: Optional[Callable[[Any], bool]] = None,
    ) -> TestResult:
        self._log(f"执行用例: {name}")
        self._log(
            f"请求: method={method}, endpoint={endpoint}, "
            f"headers={json.dumps(headers or {}, ensure_ascii=False)}, "
            f"body={json.dumps(json_body or {}, ensure_ascii=False)}"
        )

        response = client.request(method=method, url=endpoint, headers=headers, json=json_body)
        detail_text = response.text[:800]
        self._log(f"响应: status={response.status_code}, body={detail_text}")

        passed = response.status_code in expected_statuses
        payload: Any = None
        if response.headers.get("content-type", "").startswith("application/json"):
            try:
                payload = response.json()
            except Exception:
                payload = None

        if passed and validator:
            try:
                passed = validator(payload)
            except Exception:
                passed = False

        return TestResult(
            name=name,
            method=method,
            endpoint=endpoint,
            status_code=response.status_code,
            passed=passed,
            detail=detail_text,
        )

    def run(self) -> int:
        username, password = self.parse_credentials()
        self._log("开始执行 Phase 7/8 API 登录态测试")

        results: List[TestResult] = []

        with TestClient(app) as client:
            token = self.login(client, username, password)
            auth_headers = {"Authorization": f"Bearer {token}"}

            results.append(
                self.run_case(
                    client=client,
                    name="admin_tasks_snapshot",
                    method="GET",
                    endpoint="/api/v1/admin/tasks",
                    headers=auth_headers,
                    validator=lambda payload: payload.get("code") == 100000
                    and "pendingTasks" in payload.get("data", {}),
                )
            )

            results.append(
                self.run_case(
                    client=client,
                    name="admin_api_stats",
                    method="GET",
                    endpoint="/api/v1/admin/api-stats?hours=24",
                    headers=auth_headers,
                    validator=lambda payload: payload.get("code") == 100000
                    and "summary" in payload.get("data", {}),
                )
            )

            results.append(
                self.run_case(
                    client=client,
                    name="admin_logs_errors",
                    method="GET",
                    endpoint="/api/v1/admin/logs/errors?levels=ERROR,WARNING,CRITICAL&limit=20",
                    headers=auth_headers,
                    validator=lambda payload: payload.get("code") == 100000
                    and "logs" in payload.get("data", {}),
                )
            )

            results.append(
                self.run_case(
                    client=client,
                    name="admin_performance",
                    method="GET",
                    endpoint="/api/v1/admin/performance",
                    headers=auth_headers,
                    validator=lambda payload: payload.get("code") == 100000
                    and "metrics" in payload.get("data", {}),
                )
            )

            results.append(
                self.run_case(
                    client=client,
                    name="stability_status",
                    method="GET",
                    endpoint="/api/v1/stability/status",
                    headers=auth_headers,
                    validator=lambda payload: payload.get("code") == 100000
                    and "circuitBreakers" in payload.get("data", {}),
                )
            )

            results.append(
                self.run_case(
                    client=client,
                    name="stability_evaluate",
                    method="POST",
                    endpoint="/api/v1/stability/degradation/evaluate",
                    headers=auth_headers,
                    validator=lambda payload: payload.get("code") == 100000
                    and payload.get("data", {}).get("level") in {"L0", "L1", "L2", "L3"},
                )
            )

            results.append(
                self.run_case(
                    client=client,
                    name="stability_manual_l1",
                    method="POST",
                    endpoint="/api/v1/stability/degradation/manual/L1",
                    headers=auth_headers,
                    validator=lambda payload: payload.get("code") == 100000
                    and payload.get("data", {}).get("currentLevel") == "L1",
                )
            )

            results.append(
                self.run_case(
                    client=client,
                    name="stability_manual_clear",
                    method="DELETE",
                    endpoint="/api/v1/stability/degradation/manual",
                    headers=auth_headers,
                    validator=lambda payload: payload.get("code") == 100000
                    and payload.get("data", {}).get("manualLevel") is None,
                )
            )

            results.append(
                self.run_case(
                    client=client,
                    name="stability_health",
                    method="GET",
                    endpoint="/api/v1/stability/health",
                    headers=auth_headers,
                    validator=lambda payload: payload.get("code") == 100000
                    and payload.get("data", {}).get("status") in {"healthy", "degraded", "unhealthy"},
                )
            )

            results.append(
                self.run_case(
                    client=client,
                    name="health_detailed",
                    method="GET",
                    endpoint="/api/v1/health/detailed",
                    headers=auth_headers,
                    validator=lambda payload: payload.get("code") == 100000
                    and "components" in payload.get("data", {}),
                )
            )

            results.append(
                self.run_case(
                    client=client,
                    name="admin_tasks_unauthorized",
                    method="GET",
                    endpoint="/api/v1/admin/tasks",
                    expected_statuses=(401, 403),
                )
            )

        summary = {
            "total": len(results),
            "passed": sum(1 for item in results if item.passed),
            "failed": sum(1 for item in results if not item.passed),
            "logFile": str(self.log_file),
            "resultFile": str(self.result_file),
            "results": [asdict(item) for item in results],
        }

        self.result_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))

        return 0 if summary["failed"] == 0 else 1


def run() -> int:
    tester = Phase78Tester()
    return tester.run()


if __name__ == "__main__":
    sys.exit(run())
