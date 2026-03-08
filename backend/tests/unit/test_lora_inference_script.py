import json

from scripts.training.run_lora_inference import (
    build_inference_messages,
    decode_generated_answer,
    render_prompt,
    write_predictions,
)


class _FakeTokenizer:
    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
        assert tokenize is False
        assert add_generation_prompt is True
        return " || ".join(f"{item['role']}:{item['content']}" for item in messages)


def test_build_inference_messages_drops_assistant_answer():
    record = {
        "id": "sample-1",
        "messages": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": "gold-answer"},
        ],
    }

    messages = build_inference_messages(record)

    assert messages == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "question"},
    ]


def test_render_prompt_uses_chat_template_with_generation_prompt():
    record = {
        "id": "sample-1",
        "messages": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": "gold-answer"},
        ],
    }

    prompt = render_prompt(record, _FakeTokenizer())

    assert prompt == "system:sys || user:question"


def test_decode_generated_answer_strips_prompt_prefix():
    prompt = "system:sys || user:question"
    decoded = "system:sys || user:question模型回答"

    answer = decode_generated_answer(decoded, prompt)

    assert answer == "模型回答"


def test_write_predictions_outputs_jsonl(tmp_path):
    output_path = tmp_path / "predictions.jsonl"
    predictions = [
        {"id": "a", "answer": "答案A"},
        {"id": "b", "answer": "答案B"},
    ]

    write_predictions(output_path, predictions)

    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert [json.loads(line)["id"] for line in lines] == ["a", "b"]
    assert [json.loads(line)["answer"] for line in lines] == ["答案A", "答案B"]
