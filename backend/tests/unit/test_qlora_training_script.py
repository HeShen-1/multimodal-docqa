import json
from argparse import Namespace

from scripts.training.run_qlora_sft import (
    build_text_dataset,
    prepare_model_for_training,
    build_training_arguments,
    load_jsonl,
    write_run_summary,
)


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


def test_load_jsonl_supports_utf8_bom(tmp_path):
    dataset_path = tmp_path / "train_bom.jsonl"
    dataset_path.write_text(
        '\n'.join(
            [
                json.dumps({"id": "a", "messages": []}, ensure_ascii=False),
                json.dumps({"id": "b", "messages": []}, ensure_ascii=False),
            ]
        ),
        encoding="utf-8-sig",
    )

    records = load_jsonl(dataset_path)

    assert [record["id"] for record in records] == ["a", "b"]


class _FakeCuda:
    @staticmethod
    def is_available():
        return True

    @staticmethod
    def is_bf16_supported():
        return False


class _FakeTorch:
    cuda = _FakeCuda()


class _FakeTrainingArguments:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_build_training_arguments_drops_unused_columns_for_sft_collator():
    args = Namespace(
        output_dir="outputs/test",
        num_train_epochs=1.0,
        learning_rate=2e-4,
        weight_decay=0.0,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=16,
        warmup_ratio=0.03,
        logging_steps=5,
        save_strategy="epoch",
        save_steps=50,
        seed=42,
    )

    training_args = build_training_arguments(args, _FakeTorch(), _FakeTrainingArguments)

    assert training_args.kwargs["remove_unused_columns"] is True
    assert training_args.kwargs["fp16"] is True
    assert training_args.kwargs["bf16"] is False


class _FakeConfig:
    def __init__(self):
        self.use_cache = True


class _FakeModel:
    def __init__(self):
        self.config = _FakeConfig()
        self.gradient_checkpointing_calls = 0

    def gradient_checkpointing_enable(self):
        self.gradient_checkpointing_calls += 1


def test_prepare_model_for_training_uses_kbit_preparation_for_4bit():
    calls = []

    def _fake_prepare(model, use_gradient_checkpointing=True, gradient_checkpointing_kwargs=None):
        calls.append(
            {
                "model": model,
                "use_gradient_checkpointing": use_gradient_checkpointing,
                "gradient_checkpointing_kwargs": gradient_checkpointing_kwargs,
            }
        )
        return model

    model = _FakeModel()
    prepared = prepare_model_for_training(
        model=model,
        use_4bit=True,
        disable_gradient_checkpointing=False,
        prepare_model_for_kbit_training_fn=_fake_prepare,
    )

    assert prepared is model
    assert model.config.use_cache is False
    assert model.gradient_checkpointing_calls == 0
    assert calls == [
        {
            "model": model,
            "use_gradient_checkpointing": True,
            "gradient_checkpointing_kwargs": None,
        }
    ]
