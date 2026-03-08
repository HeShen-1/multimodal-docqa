# Windows 公开数据 QLoRA 微调工作流

## 1. 目标

本工作流面向当前仓库的 DocQA 场景，使用 `Qwen/Qwen2.5-3B-Instruct` 做轻量 `QLoRA` 微调：

- 公开中文数据负责补足中文问答与指令表达
- 本地业务文档负责对齐“基于证据回答 / 证据不足拒答”
- 训练环境保持为原生 Windows

## 2. 数据工作区

固定目录：`backend/scripts/training/data/docqa_workspace/`

- `public_raw/`：公开数据原始导出
- `public_norm/`：公开数据清洗结果
- `local_raw_docs/`：手动放入的原始 `pdf/md/docx/txt`
- `local_norm_docs/`：归一化后的 Markdown 文档
- `annotations/`：本地标注与清单
- `prepared/`：训练、验证、测试 JSONL 与训练输出
- `eval/`：保留评测集与离线评测结果

## 3. 依赖安装

在 `backend/` 目录执行：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-train.txt
```

如果要启用魔搭回退，`requirements-train.txt` 已包含 `modelscope`。

## 4. 本地文档准备

把你的 `pdf/md` 文档放到：

`backend/scripts/training/data/docqa_workspace/local_raw_docs/`

运行归一化与标注模板生成：

```bash
python -m scripts.training.prepare_local_corpus --seed-output
```

输出：

- 归一化 Markdown：`backend/scripts/training/data/docqa_workspace/local_norm_docs/`
- 文档清单：`backend/scripts/training/data/docqa_workspace/annotations/local_corpus_manifest.jsonl`
- 标注模板：`backend/scripts/training/data/docqa_workspace/annotations/local_docqa_seed_v1.json`

然后手工补全 `local_docqa_seed_v1.json` 中的：

- `question`
- `expected_evidence`
- `expected_answer_points`
- `allow_no_answer`

构建 grounded 本地训练集：

```bash
python -m scripts.training.build_qlora_dataset ^
  --dataset scripts/training/data/docqa_workspace/annotations/local_docqa_seed_v1.json ^
  --docs-dir scripts/training/data/docqa_workspace/local_norm_docs ^
  --output scripts/training/data/docqa_workspace/prepared/local_docqa_grounded.jsonl
```

## 5. 公开数据准备

当前固定候选源：

- `Hello-SimpleAI/HC3-Chinese`
- `BAAI/COIG-CQIA`

运行：

```bash
python -m scripts.training.prepare_public_corpus
```

输出：

- `backend/scripts/training/data/docqa_workspace/public_norm/hc3_chinese.jsonl`
- `backend/scripts/training/data/docqa_workspace/public_norm/coig_cqia.jsonl`

说明：

- 优先从 Hugging Face 拉取
- Hugging Face 失败时，`COIG-CQIA` 会尝试走魔搭镜像
- 清洗时会排除低中文占比、创作类、角色扮演、明显主观化样本

## 6. 混合训练集

将本地 grounded 样本与公开数据合成为最终训练集：

```bash
python -m scripts.training.mix_docqa_datasets
```

默认输出：

- 训练集：`backend/scripts/training/data/docqa_workspace/prepared/train_mixed.jsonl`
- 验证集：`backend/scripts/training/data/docqa_workspace/prepared/validation_local_docqa.jsonl`
- 测试集：`backend/scripts/training/data/docqa_workspace/prepared/test_local_docqa.jsonl`

默认目标配比：

- 本地 DocQA：`900`
- `HC3-Chinese`：`900`
- `COIG-CQIA`：`600`

## 7. 训练命令

首轮冒烟：

```bash
python -m scripts.training.run_qlora_sft ^
  --model-name Qwen/Qwen2.5-3B-Instruct ^
  --dataset-path scripts/training/data/docqa_workspace/prepared/train_mixed.jsonl ^
  --output-dir scripts/training/data/docqa_workspace/prepared/outputs/qwen2_5_3b_docqa_lora_v1 ^
  --num-train-epochs 1 ^
  --max-seq-length 512 ^
  --per-device-train-batch-size 1 ^
  --gradient-accumulation-steps 16 ^
  --learning-rate 2e-4 ^
  --lora-r 8 ^
  --lora-alpha 16 ^
  --lora-dropout 0.05
```

正式训练：

```bash
python -m scripts.training.run_qlora_sft ^
  --model-name Qwen/Qwen2.5-3B-Instruct ^
  --dataset-path scripts/training/data/docqa_workspace/prepared/train_mixed.jsonl ^
  --output-dir scripts/training/data/docqa_workspace/prepared/outputs/qwen2_5_3b_docqa_lora_v1 ^
  --num-train-epochs 2 ^
  --max-seq-length 768 ^
  --per-device-train-batch-size 1 ^
  --gradient-accumulation-steps 16 ^
  --learning-rate 2e-4 ^
  --lora-r 8 ^
  --lora-alpha 16 ^
  --lora-dropout 0.05
```

OOM 回退顺序：

1. `768 -> 512`
2. 缩小 `target_modules` 到 `q_proj,k_proj,v_proj,o_proj`

## 8. 离线评测

如果你已经导出模型预测结果 JSONL，可用下面脚本做快速离线打分：

```bash
python -m scripts.training.evaluate_docqa_predictions ^
  --ground-truth scripts/training/data/docqa_workspace/prepared/test_local_docqa.jsonl ^
  --predictions scripts/training/data/docqa_workspace/eval/lora_predictions.jsonl ^
  --output scripts/training/data/docqa_workspace/eval/lora_eval_summary.json
```

当前指标：

- `covered_samples`
- `no_answer_precision`
- `answer_overlap`

## 9. 常见问题

### `bitsandbytes` 无法正常加载

- 先确认 PyTorch CUDA 轮子正确安装
- 再确认 `bitsandbytes` 版本与当前 CUDA / Windows 组合兼容
- 如果量化初始化仍失败，先停在环境排查，不自动切换成全量微调

### 本地 PDF 抽取效果一般

- 优先使用文本型 PDF
- 对扫描件可先在外部做 OCR，再放入 `md/txt`
- 当前脚本只在页面文本不足时才启用 OCR 补充

### 标注数据不够

- 先补本地 grounded 样本，再考虑调大公开数据比例
- 本地样本不足时，混合脚本只允许轻度重复采样，不会自动伪造问答
