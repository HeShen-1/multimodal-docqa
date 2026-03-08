import json
from pathlib import Path

import pytest

from scripts.training.build_qlora_dataset import (
    build_training_record,
    extract_markdown_sections,
    write_jsonl,
)


def test_extract_markdown_sections_returns_heading_content():
    markdown = """# Product Manual

## Pipeline

系统主链路为：上传文档 → 解析与切块 → 向量化。

## Share Capability

支持设置访问密码与过期时间。
"""

    sections = extract_markdown_sections(markdown)

    assert sections["Pipeline"] == "系统主链路为：上传文档 → 解析与切块 → 向量化。"
    assert sections["Share Capability"] == "支持设置访问密码与过期时间。"


def test_build_training_record_contains_evidence_and_messages():
    sample = {
        "id": "q01",
        "question": "系统的完整主链路是什么？",
        "target_documents": ["product_manual.md"],
        "expected_evidence": ["product_manual.md#Pipeline"],
        "expected_answer_points": ["上传文档", "解析与切块", "向量化", "检索", "流式回答", "分享访问"],
        "allow_no_answer": False,
    }
    documents = {
        "product_manual.md": """# Product Manual

## Pipeline

系统主链路为：上传文档 → 解析与切块 → 向量化 → 检索 → 流式回答 → 分享访问。
"""
    }

    record = build_training_record(sample, documents)

    assert record["id"] == "q01"
    assert record["rejectable"] is False
    assert "product_manual.md#Pipeline" in record["evidence"]
    assert "系统主链路为" in record["evidence"]
    assert "上传文档、解析与切块、向量化、检索、流式回答、分享访问" in record["ideal_answer"]
    assert record["messages"][0]["role"] == "system"
    assert record["messages"][1]["role"] == "user"
    assert record["messages"][2]["role"] == "assistant"
    assert "仅依据提供的证据回答" in record["messages"][0]["content"]
    assert "证据片段" in record["messages"][1]["content"]


def test_build_training_record_for_rejectable_question_returns_grounded_refusal():
    sample = {
        "id": "q18",
        "question": "如果用户询问 GPU 部署参数，文档里是否有明确答案？",
        "target_documents": ["product_manual.md", "operations_policy.md"],
        "expected_evidence": [],
        "expected_answer_points": [],
        "allow_no_answer": True,
    }

    record = build_training_record(sample, {})

    assert record["rejectable"] is True
    assert record["evidence"] == ""
    assert "未找到足够依据" in record["ideal_answer"]
    assert "不要编造" in record["messages"][0]["content"]
    assert "未找到足够依据" in record["messages"][-1]["content"]


def test_write_jsonl_persists_each_record_on_new_line(tmp_path):
    records = [
        {"id": "a", "messages": []},
        {"id": "b", "messages": []},
    ]
    output_path = tmp_path / "train.jsonl"

    write_jsonl(records, output_path)

    content = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(content) == 2
    assert [json.loads(line)["id"] for line in content] == ["a", "b"]
