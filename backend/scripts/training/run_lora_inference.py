from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.training.build_qlora_dataset import SYSTEM_PROMPT, build_user_message
from scripts.training.run_qlora_sft import build_quantization_config, resolve_torch_dtype


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run base-model or LoRA inference for local DocQA evaluation.")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-3B-Instruct")
    parser.add_argument(
        "--adapter-path",
        default="scripts/training/data/docqa_workspace/prepared/outputs/qwen2_5_3b_docqa_lora_v1",
        help="Optional PEFT adapter path. Ignored when --base-only is set.",
    )
    parser.add_argument(
        "--input",
        default="scripts/training/data/docqa_workspace/prepared/test_local_docqa.jsonl",
        help="Grounded test/eval JSONL path.",
    )
    parser.add_argument(
        "--output",
        default="scripts/training/data/docqa_workspace/eval/lora_predictions.jsonl",
        help="Prediction JSONL output path.",
    )
    parser.add_argument("--max-input-length", type=int, default=1536)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--base-only", action="store_true", help="Ignore adapter_path and run base-model inference only.")
    parser.add_argument("--no-4bit", action="store_true", help="Disable 4-bit loading and run full precision inference.")
    parser.add_argument("--sample-limit", type=int, help="Optional limit for smoke inference.")
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as file:
        return [json.loads(line) for line in file if line.strip()]


def write_predictions(output_path: Path, predictions: list[dict[str, Any]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for record in predictions:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_inference_messages(record: dict[str, Any]) -> list[dict[str, str]]:
    raw_messages = [
        {"role": str(item.get("role", "")).strip(), "content": str(item.get("content", ""))}
        for item in record.get("messages", [])
        if str(item.get("role", "")).strip() and str(item.get("content", "")).strip()
    ]
    while raw_messages and raw_messages[-1]["role"] == "assistant":
        raw_messages.pop()
    if raw_messages:
        return raw_messages

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_user_message(
                str(record.get("question", "")),
                str(record.get("evidence", "")),
            ),
        },
    ]


def render_prompt(record: dict[str, Any], tokenizer: Any) -> str:
    messages = build_inference_messages(record)
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )


def decode_generated_answer(decoded_text: str, prompt_text: str) -> str:
    text = str(decoded_text or "")
    if text.startswith(prompt_text):
        text = text[len(prompt_text) :]
    return text.strip()


def ensure_inference_dependencies() -> dict[str, Any]:
    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    except ImportError as exc:
        raise RuntimeError(
            "缺少推理依赖。请先安装 backend/requirements-train.txt，并确认 Transformers / PEFT / bitsandbytes 可用。"
        ) from exc

    return {
        "torch": torch,
        "PeftModel": PeftModel,
        "AutoModelForCausalLM": AutoModelForCausalLM,
        "AutoTokenizer": AutoTokenizer,
        "BitsAndBytesConfig": BitsAndBytesConfig,
    }


def resolve_tokenizer_source(base_model: str, adapter_path: str | None, *, base_only: bool) -> str:
    if base_only or not adapter_path:
        return base_model
    adapter_dir = Path(adapter_path)
    if adapter_dir.exists() and (adapter_dir / "tokenizer_config.json").exists():
        return str(adapter_dir)
    return base_model


def load_generation_model(args: argparse.Namespace, deps: dict[str, Any]) -> tuple[Any, Any]:
    torch = deps["torch"]
    AutoModelForCausalLM = deps["AutoModelForCausalLM"]
    AutoTokenizer = deps["AutoTokenizer"]
    BitsAndBytesConfig = deps["BitsAndBytesConfig"]
    PeftModel = deps["PeftModel"]

    if not args.no_4bit and not torch.cuda.is_available():
        raise RuntimeError("当前未检测到 CUDA GPU，无法执行 4-bit 推理。请改用 --no-4bit 或在 CUDA 环境运行。")

    tokenizer_source = resolve_tokenizer_source(args.base_model, args.adapter_path, base_only=args.base_only)
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_source, use_fast=False, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quantization_config = build_quantization_config(torch, BitsAndBytesConfig, use_4bit=not args.no_4bit)
    model_kwargs: dict[str, Any] = {
        "trust_remote_code": True,
        "torch_dtype": resolve_torch_dtype(torch),
    }
    if quantization_config is not None:
        model_kwargs["quantization_config"] = quantization_config
        model_kwargs["device_map"] = "auto"

    model = AutoModelForCausalLM.from_pretrained(args.base_model, **model_kwargs)
    if not args.base_only and args.adapter_path:
        model = PeftModel.from_pretrained(model, args.adapter_path)
    model.eval()
    return model, tokenizer


def _move_inputs_to_device(inputs: dict[str, Any], model: Any) -> dict[str, Any]:
    try:
        device = model.device
    except AttributeError:
        return inputs
    return {key: value.to(device) for key, value in inputs.items()}


def generate_answer(record: dict[str, Any], model: Any, tokenizer: Any, args: argparse.Namespace) -> str:
    prompt_text = render_prompt(record, tokenizer)
    inputs = tokenizer(
        prompt_text,
        return_tensors="pt",
        truncation=True,
        max_length=args.max_input_length,
    )
    inputs = _move_inputs_to_device(inputs, model)

    generation_kwargs: dict[str, Any] = {
        "max_new_tokens": args.max_new_tokens,
        "pad_token_id": tokenizer.pad_token_id,
        "eos_token_id": tokenizer.eos_token_id,
        "do_sample": args.temperature > 0,
    }
    if args.temperature > 0:
        generation_kwargs["temperature"] = args.temperature
        generation_kwargs["top_p"] = args.top_p

    with deps_no_grad(model):
        output_ids = model.generate(**inputs, **generation_kwargs)

    input_length = inputs["input_ids"].shape[-1]
    generated_ids = output_ids[0][input_length:]
    answer = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
    if answer:
        return answer

    decoded_full_text = tokenizer.decode(output_ids[0], skip_special_tokens=True)
    return decode_generated_answer(decoded_full_text, prompt_text)


class deps_no_grad:
    def __init__(self, model: Any):
        self.model = model
        self.torch = __import__("torch")
        self._context = None

    def __enter__(self):
        self._context = self.torch.no_grad()
        return self._context.__enter__()

    def __exit__(self, exc_type, exc, tb):
        return self._context.__exit__(exc_type, exc, tb)


def run_inference(
    records: list[dict[str, Any]],
    model: Any,
    tokenizer: Any,
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    predictions: list[dict[str, Any]] = []
    selected_records = records[: args.sample_limit] if args.sample_limit else records

    for record in selected_records:
        answer = generate_answer(record, model, tokenizer, args)
        predictions.append(
            {
                "id": record["id"],
                "answer": answer,
            }
        )
    return predictions


def main() -> None:
    args = parse_args()
    deps = ensure_inference_dependencies()
    records = load_jsonl(Path(args.input))
    model, tokenizer = load_generation_model(args, deps)
    predictions = run_inference(records, model, tokenizer, args)
    write_predictions(Path(args.output), predictions)
    print(
        json.dumps(
            {
                "status": "ok",
                "mode": "base" if args.base_only else "lora",
                "input_records": len(records),
                "predictions_written": len(predictions),
                "output": args.output,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
