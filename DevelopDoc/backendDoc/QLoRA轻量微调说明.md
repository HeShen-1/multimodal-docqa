# QLoRA 轻量微调说明

## 1. 目标定位

本项目中的微调不是主链路，而是求职展示中的**加分项**：

- 主链路仍然是 `RAG + 可解释引用 + 可量化评测`
- 微调只用于增强两类能力：
  - 更稳定地引用证据
  - 更稳地拒答无依据问题

因此，本轮推荐使用**高质量小数据集 + 轻量 QLoRA**，而不是大规模知识注入训练。

## 2. 数据集来源

当前仓库已提供一套适合作为轻量 SFT 种子集的数据：

- 评测集：`backend/scripts/evaluation/rag_eval_dataset.json`
- 样例文档：`backend/scripts/evaluation/sample_docs/`

数据集构建脚本：

- `backend/scripts/training/build_qlora_dataset.py`

默认会将评测样本转换为适合监督微调的 `JSONL` 格式，输出到：

- `backend/scripts/training/data/qlora_train_template.jsonl`

每条样本包含：

- `question`
- `evidence`
- `ideal_answer`
- `rejectable`
- `messages`

其中 `messages` 直接可用于聊天模板训练。

## 3. 生成训练集

在 `backend/` 目录运行：

```bash
python -m scripts.training.build_qlora_dataset
```

可选参数：

```bash
python -m scripts.training.build_qlora_dataset \
  --dataset scripts/evaluation/rag_eval_dataset.json \
  --docs-dir scripts/evaluation/sample_docs \
  --output scripts/training/data/qlora_train_template.jsonl
```

## 4. 训练脚本

训练入口：

- `backend/scripts/training/run_qlora_sft.py`

推荐先安装独立训练依赖：

```bash
pip install -r backend/requirements-train.txt
```

基础训练命令：

```bash
python -m scripts.training.run_qlora_sft \
  --model-name Qwen/Qwen2.5-3B-Instruct \
  --dataset-path scripts/training/data/qlora_train_template.jsonl \
  --output-dir outputs/qwen2_5_3b_docqa_lora
```

常用可调参数：

- `--num-train-epochs`
- `--learning-rate`
- `--max-seq-length`
- `--lora-r`
- `--lora-alpha`
- `--lora-dropout`
- `--target-modules`
- `--no-4bit`

说明：

- 默认走 `4-bit NF4` QLoRA
- 若当前环境无法稳定支持 `bitsandbytes`，可用 `--no-4bit` 先回退到普通 LoRA 验证流程
- 训练完成后会在输出目录生成 `run_config.json`、LoRA adapter 和 tokenizer

## 5. 模型选择建议

### 本地可执行优先

推荐首选：

- `Qwen/Qwen2.5-3B-Instruct`

原因：

- 对中文和指令跟随已经足够强，适合文档问答领域适配
- 对单卡 `RTX 3060 Laptop` 更现实，容易在两周内跑出稳定结果
- 更适合做“轻量 QLoRA + 定量对比 + 本地 Demo”的求职故事

### 2026 年如果你想跟最新 Qwen 家族保持一致

可以把次优先推荐设为：

- `Qwen/Qwen3.5-4B`

适用前提：

- 你愿意单独准备训练环境
- 你接受训练脚本依赖更高版本 `transformers`
- 你希望简历里强调“更贴近最新 Qwen 体系”

但对于当前仓库与两周求职排期，我仍然建议把 `Qwen/Qwen2.5-3B-Instruct` 作为默认微调基座，因为它更稳、更容易复现实验。

### 如果你更强调简历里的“多模态”表达

更贴合项目主题但不建议本地重训的方向：

- `Qwen/Qwen2.5-VL-7B-Instruct`
- `Qwen/Qwen3.5-9B`

建议用法：

- 作为多模态推理/演示模型
- 不作为本地 3060 上的主微调对象

### 如果后续有更强算力

可升级到：

- `Qwen/Qwen2.5-7B-Instruct`

适用场景：

- 想要更强的生成质量与更稳的复杂回答
- 具备云端或更高显存环境

## 6. 面试表达建议

推荐说法：

> 我把 Qwen 系列作为基础模型做轻量 QLoRA 领域适配，训练目标不是知识灌输，而是提升基于证据的回答稳定性和无依据拒答能力；线上/本地 Demo 则部署量化推理版本，确保可演示、低成本和可复现实验。

避免说法：

- “我对 Q4_K_M 模型做了微调”

更准确的表达应该是：

- `Q4_K_M` 是部署/推理量化格式
- 真正的训练方法是 `QLoRA`

## 7. 推荐实验对比

最少保留 3 组：

1. `RAG baseline + 未微调模型`
2. `RAG + Prompt 优化 + 未微调模型`
3. `RAG + Prompt 优化 + QLoRA adapter`

重点比较：

- `citation_precision`
- `no_answer_precision`
- `avg_manual_relevance`
- `avg_latency_ms`

这样更容易向面试官讲清：

- 为什么需要微调
- 微调到底改善了什么
- 微调是否值得它带来的训练成本
