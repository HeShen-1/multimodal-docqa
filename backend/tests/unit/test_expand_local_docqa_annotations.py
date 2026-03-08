from scripts.training.expand_local_docqa_annotations import expand_annotations


def test_expand_annotations_fills_each_document_to_requested_quota():
    documents = {
        "math.md": """# 数学基础

## 核心概念

数学基础主要介绍极限、导数和积分的核心定义。

## 关键方法

- 建立目标函数
- 计算梯度
- 分析收敛条件

## 应用场景

可用于优化建模与算法分析。
""",
        "optim.md": """# 优化方法

## 梯度下降

梯度下降通过沿负梯度方向更新参数来逐步降低目标函数。

## 学习率

学习率决定每一步更新幅度，过大可能震荡，过小可能收敛缓慢。
""",
    }
    existing = [
        {
            "id": "math-answerable-001",
            "question": "数学基础主要介绍什么？",
            "target_documents": ["math.md"],
            "expected_evidence": ["math.md#数学基础"],
            "expected_answer_points": ["极限", "导数", "积分"],
            "allow_no_answer": False,
        }
    ]

    expanded = expand_annotations(
        existing_records=existing,
        documents=documents,
        answerable_target_per_doc=3,
        rejectable_target_per_doc=1,
    )

    math_records = [item for item in expanded if item["target_documents"] == ["math.md"]]
    optim_records = [item for item in expanded if item["target_documents"] == ["optim.md"]]

    assert len(math_records) == 4
    assert len(optim_records) == 4
    assert sum(1 for item in math_records if not item["allow_no_answer"]) == 3
    assert sum(1 for item in optim_records if not item["allow_no_answer"]) == 3
    assert sum(1 for item in math_records if item["allow_no_answer"]) == 1
    assert sum(1 for item in optim_records if item["allow_no_answer"]) == 1

    generated_answerable = [
        item
        for item in expanded
        if item["id"] != "math-answerable-001" and not item["allow_no_answer"]
    ]
    assert generated_answerable
    assert all(item["expected_evidence"] for item in generated_answerable)
    assert all(item["expected_answer_points"] for item in generated_answerable)
    assert len({item["id"] for item in expanded}) == len(expanded)
