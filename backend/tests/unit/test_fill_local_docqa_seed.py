import pytest

from scripts.training.fill_local_docqa_seed import apply_annotation_overrides, validate_completed_annotations


def test_apply_annotation_overrides_updates_question_and_answer_points():
    records = [
        {
            "id": "sample-answerable",
            "question": "",
            "expected_answer_points": [],
            "allow_no_answer": False,
        },
        {
            "id": "sample-rejectable",
            "question": "",
            "expected_answer_points": [],
            "allow_no_answer": True,
        },
    ]
    overrides = {
        "sample-answerable": {
            "question": "什么是智能体？",
            "expected_answer_points": ["感知环境", "采取行动"],
        },
        "sample-rejectable": {
            "question": "文中是否给出了商业报价？",
        },
    }

    updated = apply_annotation_overrides(records, overrides)

    assert updated[0]["question"] == "什么是智能体？"
    assert updated[0]["expected_answer_points"] == ["感知环境", "采取行动"]
    assert updated[1]["question"] == "文中是否给出了商业报价？"


def test_validate_completed_annotations_rejects_empty_answer_points():
    records = [
        {
            "id": "sample-answerable",
            "question": "什么是智能体？",
            "expected_answer_points": [],
            "allow_no_answer": False,
        }
    ]

    with pytest.raises(ValueError):
        validate_completed_annotations(records)
