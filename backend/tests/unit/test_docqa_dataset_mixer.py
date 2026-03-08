import pytest

from scripts.training.mix_docqa_datasets import (
    build_mixed_training_records,
    mix_workspace_datasets,
    repeat_records_to_target,
    split_local_docqa_records,
)


def _make_record(record_id: str, source_dataset: str = "local_docqa", rejectable: bool = False):
    return {
        "id": record_id,
        "source_dataset": source_dataset,
        "rejectable": rejectable,
        "messages": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": f"question-{record_id}"},
            {"role": "assistant", "content": f"answer-{record_id}"},
        ],
    }


def test_split_local_docqa_records_reserves_validation_and_test_sets():
    records = [_make_record(f"local-{index}", rejectable=index % 4 == 0) for index in range(20)]

    train_records, validation_records, test_records = split_local_docqa_records(
        records,
        validation_ratio=0.1,
        test_ratio=0.1,
        seed=7,
    )

    assert len(train_records) == 16
    assert len(validation_records) == 2
    assert len(test_records) == 2
    assert {item["id"] for item in train_records}.isdisjoint({item["id"] for item in validation_records})
    assert {item["id"] for item in train_records}.isdisjoint({item["id"] for item in test_records})


def test_repeat_records_to_target_uses_light_duplication_with_unique_ids():
    records = [_make_record("local-1"), _make_record("local-2")]

    repeated = repeat_records_to_target(records, target_size=5, max_repeat=3)

    assert len(repeated) == 5
    assert len({item["id"] for item in repeated}) == 5
    assert repeated[0]["id"] == "local-1"
    assert any(item["id"].startswith("local-1__dup") for item in repeated)


def test_build_mixed_training_records_matches_requested_source_counts():
    local_records = [_make_record(f"local-{index}") for index in range(3)]
    public_hc3 = [_make_record(f"hc3-{index}", source_dataset="HC3-Chinese") for index in range(4)]
    public_coig = [_make_record(f"coig-{index}", source_dataset="COIG-CQIA") for index in range(3)]

    mixed = build_mixed_training_records(
        local_records=local_records,
        hc3_records=public_hc3,
        coig_records=public_coig,
        local_target=5,
        hc3_target=4,
        coig_target=3,
        seed=11,
    )

    assert len(mixed) == 12
    assert sum(1 for item in mixed if item["source_dataset"] == "local_docqa") == 5
    assert sum(1 for item in mixed if item["source_dataset"] == "HC3-Chinese") == 4
    assert sum(1 for item in mixed if item["source_dataset"] == "COIG-CQIA") == 3


def test_mix_workspace_datasets_reports_local_target_capacity(tmp_path):
    workspace_root = tmp_path / "workspace"
    grounded_path = tmp_path / "local_docqa_grounded.jsonl"
    hc3_path = tmp_path / "hc3.jsonl"
    coig_path = tmp_path / "coig.jsonl"

    grounded_path.write_text(
        "\n".join(
            __import__("json").dumps(_make_record(f"local-{index}"), ensure_ascii=False)
            for index in range(20)
        )
        + "\n",
        encoding="utf-8",
    )
    hc3_path.write_text(
        "\n".join(
            __import__("json").dumps(_make_record(f"hc3-{index}", source_dataset="HC3-Chinese"), ensure_ascii=False)
            for index in range(900)
        )
        + "\n",
        encoding="utf-8",
    )
    coig_path.write_text(
        "\n".join(
            __import__("json").dumps(_make_record(f"coig-{index}", source_dataset="COIG-CQIA"), ensure_ascii=False)
            for index in range(600)
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="max feasible local target is 48"):
        mix_workspace_datasets(
            workspace_root=workspace_root,
            local_grounded_path=grounded_path,
            hc3_path=hc3_path,
            coig_path=coig_path,
            local_target=900,
            hc3_target=900,
            coig_target=600,
            seed=42,
        )
