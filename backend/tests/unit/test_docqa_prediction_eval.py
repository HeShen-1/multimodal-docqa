from scripts.training.evaluate_docqa_predictions import (
    evaluate_predictions,
    infer_predicted_no_answer,
)


def test_infer_predicted_no_answer_matches_grounded_refusal_phrases():
    assert infer_predicted_no_answer("未找到足够依据，无法回答这个问题。")
    assert infer_predicted_no_answer("根据当前提供的文档，暂无足够证据支持结论。")
    assert not infer_predicted_no_answer("RAG 可以结合检索结果提升回答准确率。")


def test_evaluate_predictions_scores_rejectable_and_answerable_records():
    ground_truth = [
        {
            "id": "q1",
            "rejectable": False,
            "ideal_answer": "RAG 可以结合外部知识提升回答准确性。",
        },
        {
            "id": "q2",
            "rejectable": True,
            "ideal_answer": "未找到足够依据。",
        },
    ]
    predictions = [
        {"id": "q1", "answer": "RAG 可以结合外部知识提升回答准确性。"},
        {"id": "q2", "answer": "未找到足够依据，当前文档没有提供答案。"},
    ]

    metrics = evaluate_predictions(ground_truth, predictions)

    assert metrics["covered_samples"] == 2
    assert metrics["no_answer_precision"] == 1.0
    assert metrics["answer_overlap"] == 1.0
