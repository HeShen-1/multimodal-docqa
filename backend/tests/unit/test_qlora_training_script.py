import json
from argparse import Namespace

from scripts.training.run_qlora_sft import build_text_dataset, load_jsonl, write_run_summary


class _FakeTokenizer:
    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
        assert tokenize is False
        assert add_generation_prompt is False
        return " || ".join(f"{item['role']}:{item['content']}" for item in messages)


class _FakeDataset:
    @classmethod
    def from_list(cls, items):
        return items


def test_build_text_dataset_formats_messages_for_chat_training():
    records = [
        {
            "id": "q01",
            "messages": [
                {"role": "system", "content": "s"},
                {"role": "user", "content": "u"},
                {"role": "assistant", "content": "a"},
            ],
            "rejectable": False,
        }
    ]

    dataset = build_text_dataset(records, _FakeTokenizer(), _FakeDataset)

    assert dataset == [
        {
            "id": "q01",
            "text": "system:s || user:u || assistant:a",
            "rejectable": False,
        }
    ]


def test_load_jsonl_and_write_run_summary(tmp_path):
    dataset_path = tmp_path / "train.jsonl"
    dataset_path.write_text(
        '\n'.join(
            [
                json.dumps({"id": "a", "messages": []}, ensure_ascii=False),
                json.dumps({"id": "b", "messages": []}, ensure_ascii=False),
            ]
        ),
        encoding="utf-8",
    )

    records = load_jsonl(dataset_path)
    assert [record["id"] for record in records] == ["a", "b"]

    args = Namespace(
        output_dir=str(tmp_path / "output"),
        model_name="Qwen/Qwen2.5-3B-Instruct",
        dataset_path=str(dataset_path),
        num_train_epochs=2.0,
        learning_rate=2e-4,
        lora_r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        target_modules="q_proj,v_proj",
        no_4bit=False,
    )
    write_run_summary(args, record_count=2)

    summary = json.loads((tmp_path / "output" / "run_config.json").read_text(encoding="utf-8"))
    assert summary["record_count"] == 2
    assert summary["target_modules"] == ["q_proj", "v_proj"]
    assert summary["use_4bit"] is True
