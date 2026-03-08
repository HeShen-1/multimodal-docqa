from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run lightweight QLoRA SFT for the DocQA project.")
    parser.add_argument("--model-name", default="Qwen/Qwen2.5-3B-Instruct")
    parser.add_argument("--dataset-path", default="scripts/training/data/qlora_train_template.jsonl")
    parser.add_argument("--output-dir", default="outputs/qwen2_5_3b_docqa_lora")
    parser.add_argument("--num-train-epochs", type=float, default=2.0)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--per-device-train-batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--warmup-ratio", type=float, default=0.03)
    parser.add_argument("--logging-steps", type=int, default=5)
    parser.add_argument("--save-strategy", default="epoch", choices=["no", "steps", "epoch"])
    parser.add_argument("--save-steps", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument(
        "--target-modules",
        default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj",
        help="Comma separated LoRA target modules.",
    )
    parser.add_argument("--disable-gradient-checkpointing", action="store_true")
    parser.add_argument("--no-4bit", action="store_true", help="Disable 4-bit QLoRA and fall back to LoRA.")
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as file:
        return [json.loads(line) for line in file if line.strip()]


def ensure_training_dependencies() -> dict[str, Any]:
    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, prepare_model_for_kbit_training
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            TrainingArguments,
        )
        from trl import SFTTrainer
    except ImportError as exc:
        raise RuntimeError(
            "缺少训练依赖。请先安装 backend/requirements-train.txt，建议在 Linux/WSL + CUDA 环境运行。"
        ) from exc

    return {
        "torch": torch,
        "Dataset": Dataset,
        "LoraConfig": LoraConfig,
        "prepare_model_for_kbit_training": prepare_model_for_kbit_training,
        "AutoModelForCausalLM": AutoModelForCausalLM,
        "AutoTokenizer": AutoTokenizer,
        "BitsAndBytesConfig": BitsAndBytesConfig,
        "TrainingArguments": TrainingArguments,
        "SFTTrainer": SFTTrainer,
    }


def resolve_torch_dtype(torch_module: Any) -> Any:
    if torch_module.cuda.is_available():
        if torch_module.cuda.is_bf16_supported():
            return torch_module.bfloat16
        return torch_module.float16
    return torch_module.float32


def build_quantization_config(torch_module: Any, bitsandbytes_config_cls: Any, use_4bit: bool) -> Any | None:
    if not use_4bit:
        return None

    compute_dtype = resolve_torch_dtype(torch_module)
    return bitsandbytes_config_cls(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=compute_dtype,
    )


def build_text_dataset(records: list[dict[str, Any]], tokenizer: Any, dataset_cls: Any) -> Any:
    formatted = []
    for record in records:
        text = tokenizer.apply_chat_template(
            record["messages"],
            tokenize=False,
            add_generation_prompt=False,
        )
        formatted.append(
            {
                "id": record["id"],
                "text": text,
                "rejectable": record.get("rejectable", False),
            }
        )
    return dataset_cls.from_list(formatted)


def build_training_arguments(args: argparse.Namespace, torch: Any, training_arguments_cls: Any) -> Any:
    return training_arguments_cls(
        output_dir=args.output_dir,
        num_train_epochs=args.num_train_epochs,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        per_device_train_batch_size=args.per_device_train_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        warmup_ratio=args.warmup_ratio,
        logging_steps=args.logging_steps,
        save_strategy=args.save_strategy,
        save_steps=args.save_steps,
        bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
        fp16=torch.cuda.is_available() and not torch.cuda.is_bf16_supported(),
        report_to="none",
        remove_unused_columns=True,
        seed=args.seed,
    )


def prepare_model_for_training(
    model: Any,
    *,
    use_4bit: bool,
    disable_gradient_checkpointing: bool,
    prepare_model_for_kbit_training_fn: Any,
) -> Any:
    if use_4bit:
        model = prepare_model_for_kbit_training_fn(
            model,
            use_gradient_checkpointing=not disable_gradient_checkpointing,
        )
    elif not disable_gradient_checkpointing:
        model.gradient_checkpointing_enable()

    model.config.use_cache = False
    return model


def write_run_summary(args: argparse.Namespace, record_count: int) -> None:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "run_config.json"
    summary_path.write_text(
        json.dumps(
            {
                "model_name": args.model_name,
                "dataset_path": args.dataset_path,
                "record_count": record_count,
                "num_train_epochs": args.num_train_epochs,
                "learning_rate": args.learning_rate,
                "lora_r": args.lora_r,
                "lora_alpha": args.lora_alpha,
                "lora_dropout": args.lora_dropout,
                "target_modules": [item.strip() for item in args.target_modules.split(",") if item.strip()],
                "use_4bit": not args.no_4bit,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    deps = ensure_training_dependencies()
    torch = deps["torch"]
    Dataset = deps["Dataset"]
    LoraConfig = deps["LoraConfig"]
    AutoModelForCausalLM = deps["AutoModelForCausalLM"]
    AutoTokenizer = deps["AutoTokenizer"]
    BitsAndBytesConfig = deps["BitsAndBytesConfig"]
    TrainingArguments = deps["TrainingArguments"]
    SFTTrainer = deps["SFTTrainer"]
    prepare_model_for_kbit_training = deps["prepare_model_for_kbit_training"]

    if not args.no_4bit and not torch.cuda.is_available():
        raise RuntimeError("当前未检测到 CUDA GPU，无法执行 4-bit QLoRA。请改用 `--no-4bit` 或在 CUDA 环境运行。")

    records = load_jsonl(Path(args.dataset_path))
    write_run_summary(args, len(records))

    tokenizer = AutoTokenizer.from_pretrained(args.model_name, use_fast=False, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quantization_config = build_quantization_config(torch, BitsAndBytesConfig, use_4bit=not args.no_4bit)
    torch_dtype = resolve_torch_dtype(torch)
    model_kwargs: dict[str, Any] = {
        "trust_remote_code": True,
        "torch_dtype": torch_dtype,
    }
    if quantization_config is not None:
        model_kwargs["quantization_config"] = quantization_config
        model_kwargs["device_map"] = "auto"

    model = AutoModelForCausalLM.from_pretrained(args.model_name, **model_kwargs)
    model = prepare_model_for_training(
        model,
        use_4bit=not args.no_4bit,
        disable_gradient_checkpointing=args.disable_gradient_checkpointing,
        prepare_model_for_kbit_training_fn=prepare_model_for_kbit_training,
    )

    peft_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[item.strip() for item in args.target_modules.split(",") if item.strip()],
    )

    train_dataset = build_text_dataset(records, tokenizer, Dataset)

    training_args = build_training_arguments(args, torch, TrainingArguments)

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        tokenizer=tokenizer,
        peft_config=peft_config,
        dataset_text_field="text",
        max_seq_length=args.max_seq_length,
        packing=False,
    )

    trainer.train()
    trainer.model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(json.dumps({"status": "ok", "output_dir": args.output_dir}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
