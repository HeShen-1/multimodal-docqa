# Release Notes

## 2026.03

- Prompt 版本升级为 `2026.03.v1`。
- 文档约束问答增加“未找到依据”受限回答策略。
- 前端补充登录 → 上传 → 问答 → 分享访问的 E2E 主流程。

## Retrieval Experiments

推荐固定三组实验：

1. 纯向量检索
2. 混合检索（向量 + 关键词/BM25）
3. 混合检索 + reranker

## Default Recommendation

若面向真实业务文档，优先选择“混合检索 + reranker”；若资源受限，可退化到“混合检索”。
