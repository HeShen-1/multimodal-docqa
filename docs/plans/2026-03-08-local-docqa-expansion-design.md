# Local DocQA Expansion Design

**Context**

当前仓库已经具备三段式本地数据流程：把 `backend/scripts/training/data/docqa_workspace/local_raw_docs/` 中的文档归一化到 `local_norm_docs/`，在 `annotations/local_docqa_seed_v1.json` 中维护问答标注，再由 grounded 数据构建脚本生成本地训练样本。用户新增了一批本地 Markdown 文档，并希望把本地 DocQA 样本扩充到足以支撑默认混合训练配置。

**Goal**

在不改动业务接口和训练主流程的前提下，把新增本地文档纳入数据工作区，扩充 `local_docqa_seed_v1.json` 中的高质量 grounded 问答标注，并将 grounded 本地样本提升到能支撑默认 `python -m scripts.training.mix_docqa_datasets` 的规模。

**Approach**

采用混合方案：先重新执行本地文档归一化，确保新增 `md/pdf` 文档全部进入 `local_norm_docs/`；再基于每篇文档的标题和结构，优先扩充“定义、列表、流程、对比、条件、拒答”六类问题，保证每篇文档既有可回答样本，也有明确无依据的拒答样本；最后重建 grounded 数据并验证默认混合命令可以直接运行。

**Data Strategy**

- 继续沿用单文档 grounded SFT 样本格式，不改变现有训练脚本的数据接口。
- 对现有 18 篇已归一化文档保留原始标注，并为新增文档补充新的标注组。
- 扩样优先覆盖新增文档，再对已有文档补足问题密度，目标是本地 grounded 样本总量达到至少 `374` 条。
- 每篇文档的拒答比例保持在约 `20%~30%`，避免模型只学会“有答案时回答”。

**Validation**

- `local_norm_docs/` 中出现新增文档对应的 Markdown 文件。
- `annotations/local_docqa_seed_v1.json` 记录数显著增加，且字段完整。
- `prepared/local_docqa_grounded.jsonl` 的记录数达到默认混合所需阈值。
- `python -m scripts.training.mix_docqa_datasets` 默认参数能直接运行成功。
