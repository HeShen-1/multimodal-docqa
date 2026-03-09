from scripts.training.build_qlora_dataset import SYSTEM_PROMPT, build_user_message
from scripts.training.run_lora_inference import build_arg_parser


def test_system_prompt_emphasizes_brief_verifiable_answers():
    assert "简洁" in SYSTEM_PROMPT
    assert "可核验" in SYSTEM_PROMPT
    assert "不要编造" in SYSTEM_PROMPT


def test_build_user_message_requires_short_grounded_answer():
    message = build_user_message("智能客服通常处理哪些问题？", "订单查询、退货流程。")

    assert "先用 1 句话" in message
    assert "2-4 个要点" in message
    assert "未找到足够依据" in message


def test_inference_parser_uses_shorter_generation_defaults():
    args = build_arg_parser().parse_args([])

    assert args.max_new_tokens == 160
    assert args.max_input_length == 1536
