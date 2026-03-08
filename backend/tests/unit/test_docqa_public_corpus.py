import pytest

from scripts.training.prepare_public_corpus import (
    PublicCorpusDependencyError,
    dedupe_records,
    is_mostly_chinese,
    load_coig_dataset_from_huggingface_json,
    load_hc3_dataset_from_huggingface_json,
    load_dataset_with_fallback,
    normalize_coig_record,
    normalize_hc3_record,
)


def test_is_mostly_chinese_requires_high_ratio():
    assert is_mostly_chinese("这是一个中文问题，用于测试比例判断。")
    assert not is_mostly_chinese("Explain retrieval augmented generation in English.")


def test_normalize_hc3_record_uses_first_human_answer():
    sample = {
        "question": "什么是向量数据库？",
        "human_answers": ["向量数据库用于存储和检索向量表示。", "另一种答案"],
        "chatgpt_answers": ["这是一种数据库。"],
        "source": "wiki",
    }

    record = normalize_hc3_record(sample, "hc3-0001")

    assert record is not None
    assert record["id"] == "hc3-0001"
    assert record["source_dataset"] == "HC3-Chinese"
    assert record["messages"][1]["content"] == "什么是向量数据库？"
    assert record["messages"][2]["content"] == "向量数据库用于存储和检索向量表示。"


def test_normalize_hc3_record_rejects_non_chinese_or_creative_prompt():
    sample = {
        "question": "Write a poem about spring",
        "human_answers": ["Here is a poem about spring."],
        "chatgpt_answers": [],
        "source": "open_qa",
    }

    assert normalize_hc3_record(sample, "hc3-0002") is None


def test_normalize_coig_record_merges_input_and_keeps_fact_qa():
    sample = {
        "instruction": "概括 RAG 系统的核心价值。",
        "input": "请控制在两句话内。",
        "output": "RAG 可以结合外部知识提升回答准确性，并降低幻觉风险。",
        "task_type": {"major": "问答", "minor": "知识问答"},
        "domain": "technology",
    }

    record = normalize_coig_record(sample, "coig-0001")

    assert record is not None
    assert record["id"] == "coig-0001"
    assert record["source_dataset"] == "COIG-CQIA"
    assert "请控制在两句话内。" in record["messages"][1]["content"]
    assert record["messages"][2]["content"].startswith("RAG 可以结合外部知识")


def test_normalize_coig_record_rejects_roleplay_like_sample():
    sample = {
        "instruction": "请扮演一个古风诗人写一首诗。",
        "input": "",
        "output": "好的，我来写诗。",
        "task_type": {"major": "创作", "minor": "角色扮演"},
        "domain": "creative",
    }

    assert normalize_coig_record(sample, "coig-0002") is None


def test_dedupe_records_removes_duplicate_message_pairs():
    records = [
        {
            "id": "a",
            "messages": [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "什么是 RAG？"},
                {"role": "assistant", "content": "RAG 是检索增强生成。"},
            ],
        },
        {
            "id": "b",
            "messages": [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "什么是 RAG？"},
                {"role": "assistant", "content": "RAG 是检索增强生成。"},
            ],
        },
    ]

    deduped = dedupe_records(records)

    assert [item["id"] for item in deduped] == ["a"]


def test_load_dataset_with_fallback_raises_clear_error_when_datasets_missing(monkeypatch):
    def raise_dependency_error(*args, **kwargs):
        raise PublicCorpusDependencyError("Missing optional dependency 'datasets'. Run `pip install -r requirements-train.txt`.")

    monkeypatch.setattr(
        "scripts.training.prepare_public_corpus._load_dataset_from_huggingface",
        raise_dependency_error,
    )

    with pytest.raises(PublicCorpusDependencyError) as exc_info:
        load_dataset_with_fallback("Hello-SimpleAI/HC3-Chinese", split="train")

    assert "requirements-train.txt" in str(exc_info.value)


def test_load_hc3_dataset_from_huggingface_json_downloads_jsonl(monkeypatch):
    captured = {}

    def fake_download(**kwargs):
        captured["download"] = kwargs
        return "C:/cache/all.jsonl"

    def fake_load_dataset(path, data_files=None, split=None, cache_dir=None):
        captured["load_dataset"] = {
            "path": path,
            "data_files": data_files,
            "split": split,
            "cache_dir": cache_dir,
        }
        return [{"question": "什么是智能体？"}]

    monkeypatch.setattr("scripts.training.prepare_public_corpus._download_hf_dataset_file", fake_download)
    monkeypatch.setattr("scripts.training.prepare_public_corpus._load_json_dataset", fake_load_dataset)

    dataset = load_hc3_dataset_from_huggingface_json(cache_dir="D:/hf-cache")

    assert dataset == [{"question": "什么是智能体？"}]
    assert captured["download"]["repo_id"] == "Hello-SimpleAI/HC3-Chinese"
    assert captured["download"]["filename"] == "all.jsonl"
    assert captured["download"]["cache_dir"] == "D:/hf-cache"
    assert captured["load_dataset"]["path"] == "json"
    assert captured["load_dataset"]["data_files"] == "C:/cache/all.jsonl"
    assert captured["load_dataset"]["split"] == "train"


def test_load_coig_dataset_from_huggingface_json_downloads_folder_jsonl(monkeypatch):
    captured = {}

    def fake_list(repo_id):
        captured["repo_id"] = repo_id
        return [
            "wiki/10why_final.jsonl",
            "wiki/zgbk.jsonl",
            "zhihu/zhihu_expansion.jsonl",
            "README.md",
        ]

    def fake_download(**kwargs):
        captured.setdefault("downloads", []).append(kwargs)
        return f"C:/cache/{kwargs['filename'].replace('/', '__')}"

    def fake_load_dataset(path, data_files=None, split=None, cache_dir=None):
        captured["load_dataset"] = {
            "path": path,
            "data_files": data_files,
            "split": split,
            "cache_dir": cache_dir,
        }
        return [{"instruction": "问题", "output": "答案"}]

    monkeypatch.setattr("scripts.training.prepare_public_corpus._list_hf_dataset_files", fake_list)
    monkeypatch.setattr("scripts.training.prepare_public_corpus._download_hf_dataset_file", fake_download)
    monkeypatch.setattr("scripts.training.prepare_public_corpus._load_json_dataset", fake_load_dataset)

    dataset = load_coig_dataset_from_huggingface_json("wiki", cache_dir="D:/hf-cache")

    assert dataset == [{"instruction": "问题", "output": "答案"}]
    assert captured["repo_id"] == "m-a-p/COIG-CQIA"
    assert [item["filename"] for item in captured["downloads"]] == ["wiki/10why_final.jsonl", "wiki/zgbk.jsonl"]
    assert captured["load_dataset"]["path"] == "json"
    assert captured["load_dataset"]["split"] == "train"
    assert len(captured["load_dataset"]["data_files"]) == 2
