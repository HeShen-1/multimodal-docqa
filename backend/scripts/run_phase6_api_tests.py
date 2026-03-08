"""
Phase 6 API 集成测试脚本（登录态）

说明：
- 登录凭证来自 TEST_CREDENTIALS.txt
- 登录接口固定调用 /api/v1/auth/login 获取新 token
- 覆盖成功路径与常见失败路径
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import List

from fastapi.testclient import TestClient
import psycopg2
from psycopg2.extras import Json

from app.config import get_settings
from app.main import app
from app.services.embedding_service import EmbeddingService


CREDENTIALS_FILE = Path("TEST_CREDENTIALS.txt")


@dataclass
class TestResult:
    name: str
    passed: bool
    detail: str


def parse_credentials(path: Path) -> tuple[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"凭证文件不存在: {path}")

    content = path.read_text(encoding="utf-8")
    username_match = re.search(r"用户名[:：]\s*(.+)", content)
    password_match = re.search(r"密码[:：]\s*(.+)", content)
    if not username_match or not password_match:
        raise ValueError("未能从 TEST_CREDENTIALS.txt 解析用户名或密码")

    return username_match.group(1).strip(), password_match.group(1).strip()


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    if response.status_code != 200:
        raise RuntimeError(f"登录失败: {response.status_code} {response.text}")

    payload = response.json()
    token = (
        payload.get("access_token")
        or payload.get("data", {}).get("access_token")
        or payload.get("data", {}).get("accessToken")
    )
    if not token:
        raise RuntimeError(f"登录响应缺少 access_token: {response.text}")
    return token


def seed_test_documents(user_id: str) -> tuple[str, str]:
    doc_a_id = str(uuid.uuid4())
    doc_b_id = str(uuid.uuid4())
    settings = get_settings()

    with psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_db,
    ) as connection:
        with connection.cursor() as cursor:
            now = datetime.utcnow()
            cursor.execute(
                """
                INSERT INTO documents (
                    id, user_id, file_name, file_type, file_size, file_path, status,
                    description, page_count, chunk_count, image_count, doc_metadata,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    doc_a_id,
                    user_id,
                    "phase6_seed_doc_a.pdf",
                    ".pdf",
                    2048,
                    f"./data/documents/{doc_a_id}.pdf",
                    "COMPLETED",
                    None,
                    1,
                    1,
                    0,
                    Json({}),
                    now,
                    now,
                ),
            )
            cursor.execute(
                """
                INSERT INTO documents (
                    id, user_id, file_name, file_type, file_size, file_path, status,
                    description, page_count, chunk_count, image_count, doc_metadata,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    doc_b_id,
                    user_id,
                    "phase6_seed_doc_b.pdf",
                    ".pdf",
                    2048,
                    f"./data/documents/{doc_b_id}.pdf",
                    "COMPLETED",
                    None,
                    1,
                    1,
                    0,
                    Json({}),
                    now,
                    now,
                ),
            )
        connection.commit()

    embedding_service = EmbeddingService()
    collection = embedding_service.text_collection

    text_a = "Phase 6 智能分析测试文档A，主题包括 AI、RAG、向量检索、摘要生成。"
    text_b = "Phase 6 智能分析测试文档B，主题包括 检索增强、Embedding、关键词提取、文档对比。"

    vector_a = [0.1] * 1024
    vector_b = [0.1] * 900 + [0.2] * 124

    for document_id in (doc_a_id, doc_b_id):
        try:
            collection.delete(where={"document_id": document_id})
        except Exception:
            pass

    collection.add(
        ids=[f"{doc_a_id}_chunk_0"],
        documents=[text_a],
        metadatas=[{"document_id": doc_a_id, "page": 1, "chunk_index": 0, "type": "text"}],
        embeddings=[vector_a],
    )
    collection.add(
        ids=[f"{doc_b_id}_chunk_0"],
        documents=[text_b],
        metadatas=[{"document_id": doc_b_id, "page": 1, "chunk_index": 0, "type": "text"}],
        embeddings=[vector_b],
    )

    return doc_a_id, doc_b_id


def cleanup_test_documents(doc_ids: tuple[str, str]) -> None:
    settings = get_settings()

    with psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_db,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM documents WHERE id = ANY(%s)",
                (list(doc_ids),),
            )
        connection.commit()

    embedding_service = EmbeddingService()
    for document_id in doc_ids:
        try:
            embedding_service.text_collection.delete(where={"document_id": document_id})
        except Exception:
            pass


def record(results: List[TestResult], name: str, condition: bool, response_text: str) -> None:
    results.append(TestResult(name=name, passed=condition, detail=response_text[:400]))


def run() -> int:
    username, password = parse_credentials(CREDENTIALS_FILE)

    with TestClient(app) as client:
        token = login(client, username, password)
        headers = {"Authorization": f"Bearer {token}"}

        me_response = client.get("/api/v1/auth/me", headers=headers)
        if me_response.status_code != 200:
            raise RuntimeError(f"获取当前用户失败: {me_response.status_code} {me_response.text}")

        user_id = me_response.json().get("id")
        if not user_id:
            raise RuntimeError(f"当前用户响应缺少 id: {me_response.text}")

        doc_ids = seed_test_documents(user_id)
        doc_a, doc_b = doc_ids

        results: List[TestResult] = []

        try:
            response = client.post(
                "/api/v1/analysis/summary",
                headers=headers,
                json={
                    "documentId": doc_a,
                    "method": "hybrid",
                    "maxLength": 180,
                    "style": "简洁",
                },
            )
            record(
                results,
                "summary_success",
                response.status_code == 200 and "summary" in response.json().get("data", {}),
                response.text,
            )

            response = client.post(
                "/api/v1/analysis/keywords",
                headers=headers,
                json={
                    "documentId": doc_a,
                    "method": "hybrid",
                    "topK": 8,
                },
            )
            record(
                results,
                "keywords_success",
                response.status_code == 200
                and len(response.json().get("data", {}).get("keywords", [])) > 0,
                response.text,
            )

            response = client.post(
                "/api/v1/analysis/compare",
                headers=headers,
                json={
                    "documentIdA": doc_a,
                    "documentIdB": doc_b,
                    "topK": 8,
                },
            )
            record(
                results,
                "compare_success",
                response.status_code == 200
                and "similarity" in response.json().get("data", {}).get("result", {}),
                response.text,
            )

            response = client.get(
                f"/api/v1/analysis/similar/{doc_a}",
                headers=headers,
                params={"limit": 5, "minSimilarity": 0.0},
            )
            record(
                results,
                "similar_success",
                response.status_code == 200
                and "similarDocuments" in response.json().get("data", {}),
                response.text,
            )

            response = client.post(
                "/api/v1/analysis/summary",
                headers=headers,
                json={
                    "documentId": "not_exists_doc",
                    "method": "extractive",
                    "maxLength": 120,
                    "style": "简洁",
                },
            )
            record(results, "summary_not_found", response.status_code == 404, response.text)

            response = client.post(
                "/api/v1/analysis/compare",
                headers=headers,
                json={
                    "documentIdA": doc_a,
                    "documentIdB": doc_a,
                    "topK": 8,
                },
            )
            record(results, "compare_invalid_param", response.status_code == 400, response.text)

            response = client.post(
                "/api/v1/analysis/keywords",
                json={
                    "documentId": doc_a,
                    "method": "hybrid",
                    "topK": 8,
                },
            )
            record(results, "keywords_unauthorized", response.status_code in (401, 403), response.text)
        finally:
            cleanup_test_documents(doc_ids)

    print(json.dumps([item.__dict__ for item in results], ensure_ascii=False, indent=2))
    return 0 if all(item.passed for item in results) else 1


if __name__ == "__main__":
    sys.exit(run())
