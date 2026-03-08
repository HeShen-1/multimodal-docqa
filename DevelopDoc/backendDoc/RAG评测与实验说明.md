# RAG 评测与实验说明

## 目录

- 评测集：`backend/scripts/evaluation/rag_eval_dataset.json`
- 示例文档：`backend/scripts/evaluation/sample_docs/`
- 结果模板：`backend/scripts/evaluation/example_results_template.json`
- 统计脚本：`backend/scripts/run_rag_eval_baseline.py`
- 对比矩阵模板：`backend/scripts/evaluation/experiment_matrix_template.json`
- 对比矩阵脚本：`backend/scripts/run_rag_eval_matrix.py`

## 数据集字段

- `question`：问题
- `target_documents`：目标文档
- `expected_evidence`：期望证据
- `expected_answer_points`：期望答案要点
- `allow_no_answer`：是否允许拒答

## 固定实验组

### A. 纯向量检索

- 目的：给出最低成本基线
- 适用：小文档集 / 纯语义匹配场景

### B. 混合检索

- 目的：提升关键词和术语命中率
- 适用：制度文档、技术文档、编号类问题

### C. 混合检索 + reranker

- 目的：提升 topN 候选的排序质量
- 适用：正式投递演示的默认方案

## 建议指标

- `document_hit_rate`
- `citation_precision`
- `no_answer_precision`
- `avg_manual_relevance`
- `avg_latency_ms`

## 推荐展示表

建议固定输出以下 5 组结果，方便简历与面试直接引用：

- `Baseline`
- `Hybrid`
- `Hybrid + Reranker`
- `Hybrid + Reranker + Prompt优化`
- `轻量微调版`

## 结果产出方式

先产出每组实验的结果 JSON，再运行：

```bash
cd backend
python scripts/run_rag_eval_baseline.py --experiment vector --results scripts/evaluation/example_results_template.json
```

如果需要写 Markdown 报告：

```bash
python scripts/run_rag_eval_baseline.py ^
  --experiment hybrid_reranker ^
  --results scripts/evaluation/example_results_template.json ^
  --output logs/eval/hybrid_reranker.md
```

如果需要把多组结果汇总成一页矩阵表：

```bash
python scripts/run_rag_eval_matrix.py ^
  --matrix scripts/evaluation/experiment_matrix_template.json ^
  --output logs/eval/experiment_matrix.md
```

## 当前推荐讲法

- 主链路：`query rewrite -> hybrid recall -> parent context merge -> optional rerank -> grounded answer`
- 拒答策略：当 `top_score` 或 `evidence_coverage` 低于阈值时，返回“未找到足够依据”
- 面试重点展示：
  - 为什么混合检索比纯向量更稳
  - 为什么 `Reranker` 只做加分项而不是所有场景默认强依赖
  - 为什么微调是加分项，不替代 `RAG`

## 面试结论模板

- 默认推荐：`混合检索 + reranker`
- 原因：
  - 术语类问题比纯向量更稳
  - 引用正确率更高，适合面试展示 grounded answer
  - 在可接受延迟下换来更好的 topN 质量

- 资源受限回退：`混合检索`
