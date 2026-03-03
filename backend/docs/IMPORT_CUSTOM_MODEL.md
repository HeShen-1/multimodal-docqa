# 导入本地微调模型到 Ollama Docker

## 概述

本指南介绍如何将本地微调的 `qwen3-vl:2b-thinking-q4_K_M` 模型导入到 Ollama Docker 容器中。

## 前提条件

1. Ollama Docker 容器已启动
2. 本地有微调后的模型文件（GGUF 格式）
3. 足够的磁盘空间（模型大小 + 额外空间）

## 方法 1: 使用 Modelfile 创建（推荐）

这是最标准和推荐的方法。

### 步骤 1: 准备模型文件

确保你的模型文件是 GGUF 格式。如果是其他格式，需要先转换：

```bash
# 如果是 PyTorch 格式，使用 llama.cpp 转换
python convert.py your_model_dir --outtype q4_K_M --outfile qwen3-vl-2b-thinking-q4_K_M.gguf
```

### 步骤 2: 创建 Modelfile

创建 `Modelfile.qwen3-vl-custom` 文件：

```dockerfile
# 从本地 GGUF 文件加载
FROM /tmp/model.gguf

# 设置参数
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER repeat_penalty 1.1

# 系统提示词（可选）
SYSTEM """
你是一个经过微调的 Qwen3-VL 模型，专门用于多模态文档问答。
你可以理解图像和文本，并提供准确的答案。
"""

# 模板（根据你的微调配置调整）
TEMPLATE """{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ if .Prompt }}<|im_start|>user
{{ .Prompt }}<|im_end|>
{{ end }}<|im_start|>assistant
{{ .Response }}<|im_end|>
"""
```

### 步骤 3: 使用脚本导入

#### Windows PowerShell

```powershell
# 修改脚本中的路径
$LOCAL_MODEL_PATH = "D:\path\to\your\qwen3-vl-2b-thinking-q4_K_M.gguf"

# 运行导入脚本
.\scripts\import-custom-model.ps1
```

#### 手动导入

```powershell
# 1. 复制模型文件到容器
docker cp D:\path\to\your\qwen3-vl-2b-thinking-q4_K_M.gguf multimodal-docqa-ollama:/tmp/model.gguf

# 2. 创建 Modelfile
$modelfile = @"
FROM /tmp/model.gguf
PARAMETER temperature 0.7
PARAMETER top_p 0.9
"@
$modelfile | docker exec -i multimodal-docqa-ollama sh -c "cat > /tmp/Modelfile"

# 3. 创建模型
docker exec multimodal-docqa-ollama ollama create qwen3-vl:2b-thinking-q4_K_M -f /tmp/Modelfile

# 4. 清理临时文件
docker exec multimodal-docqa-ollama rm /tmp/model.gguf /tmp/Modelfile

# 5. 验证
docker exec multimodal-docqa-ollama ollama list
```

## 方法 2: 使用 Docker Volume 挂载

这种方法适合频繁更新模型的场景。

### 步骤 1: 修改 docker-compose.yml

```yaml
  ollama:
    image: ollama/ollama:latest
    container_name: multimodal-docqa-ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
      - ./models:/models  # 添加这行，挂载本地模型目录
    environment:
      - OLLAMA_HOST=0.0.0.0
    networks:
      - app-network
```

### 步骤 2: 放置模型文件

```bash
# 创建模型目录
mkdir -p backend/models

# 复制模型文件
cp /path/to/qwen3-vl-2b-thinking-q4_K_M.gguf backend/models/
```

### 步骤 3: 创建模型

```bash
# 重启容器以应用挂载
docker-compose restart ollama

# 创建 Modelfile
cat > backend/models/Modelfile << EOF
FROM /models/qwen3-vl-2b-thinking-q4_K_M.gguf
PARAMETER temperature 0.7
EOF

# 创建模型
docker exec multimodal-docqa-ollama ollama create qwen3-vl:2b-thinking-q4_K_M -f /models/Modelfile
```

## 方法 3: 使用 Ollama API 导入

适合自动化场景。

```python
import requests
import base64

# 读取模型文件
with open("qwen3-vl-2b-thinking-q4_K_M.gguf", "rb") as f:
    model_data = f.read()

# 创建 Modelfile
modelfile = """
FROM /tmp/model.gguf
PARAMETER temperature 0.7
"""

# 上传并创建模型
# 注意：这需要先将文件复制到容器中
```

## 验证和测试

### 1. 列出模型

```bash
docker exec multimodal-docqa-ollama ollama list
```

应该看到：
```
NAME                              ID              SIZE      MODIFIED
qwen3-vl:2b-thinking-q4_K_M      abc123def456    1.2 GB    2 minutes ago
```

### 2. 测试模型

```bash
# 简单测试
docker exec -it multimodal-docqa-ollama ollama run qwen3-vl:2b-thinking-q4_K_M "你好"

# API 测试
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-vl:2b-thinking-q4_K_M",
    "prompt": "介绍一下你自己",
    "stream": false
  }'
```

### 3. Python 测试

```python
import requests

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen3-vl:2b-thinking-q4_K_M",
        "prompt": "你好，请介绍一下你自己",
        "stream": False
    }
)

print(response.json()["response"])
```

## 在应用中使用

### 更新 .env 配置

```env
# 使用自定义模型
OLLAMA_EMBEDDING_MODEL=qwen3-vl:2b-thinking-q4_K_M
OLLAMA_CHAT_MODEL=qwen3-vl:2b-thinking-q4_K_M
```

### 在代码中使用

```python
from app.services.embedding_service import EmbeddingService

# 初始化服务
embedding_service = EmbeddingService(
    model_name="qwen3-vl:2b-thinking-q4_K_M"
)

# 使用模型
embeddings = await embedding_service.encode_text("测试文本")
```

## 模型管理

### 查看模型信息

```bash
docker exec multimodal-docqa-ollama ollama show qwen3-vl:2b-thinking-q4_K_M
```

### 删除模型

```bash
docker exec multimodal-docqa-ollama ollama rm qwen3-vl:2b-thinking-q4_K_M
```

### 更新模型

```bash
# 删除旧模型
docker exec multimodal-docqa-ollama ollama rm qwen3-vl:2b-thinking-q4_K_M

# 重新导入新版本
# 重复上述导入步骤
```

## 性能优化

### 1. 预加载模型

```bash
# 保持模型在内存中
curl -X POST http://localhost:11434/api/generate \
  -d '{
    "model": "qwen3-vl:2b-thinking-q4_K_M",
    "keep_alive": -1
  }'
```

### 2. 调整参数

在 Modelfile 中调整：

```dockerfile
# 更快的推理速度
PARAMETER num_ctx 2048        # 上下文长度
PARAMETER num_batch 512       # 批处理大小
PARAMETER num_gpu 1           # GPU 层数
PARAMETER num_thread 8        # CPU 线程数
```

### 3. 使用 GPU

确保 docker-compose.yml 中配置了 GPU：

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

## 故障排查

### 问题 1: 模型创建失败

```bash
# 检查日志
docker logs multimodal-docqa-ollama

# 常见原因：
# - 模型文件格式不正确
# - 磁盘空间不足
# - 内存不足
```

### 问题 2: 模型加载慢

```bash
# 检查模型大小
docker exec multimodal-docqa-ollama ollama list

# 优化：
# - 使用更小的量化版本（q4_K_M -> q4_0）
# - 增加内存限制
# - 使用 GPU
```

### 问题 3: 推理速度慢

```bash
# 检查 GPU 使用
docker exec multimodal-docqa-ollama nvidia-smi

# 优化：
# - 确保 GPU 可用
# - 调整 num_gpu 参数
# - 减少 num_ctx
```

## 备份和迁移

### 备份模型

```bash
# 导出模型
docker exec multimodal-docqa-ollama ollama show qwen3-vl:2b-thinking-q4_K_M --modelfile > Modelfile.backup

# 备份数据卷
docker run --rm \
  -v multimodal-docqa_ollama_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/ollama-custom-model.tar.gz /data
```

### 迁移到其他环境

```bash
# 1. 导出 Modelfile
docker exec multimodal-docqa-ollama ollama show qwen3-vl:2b-thinking-q4_K_M --modelfile > Modelfile

# 2. 复制原始 GGUF 文件
docker cp multimodal-docqa-ollama:/root/.ollama/models/blobs/sha256-xxx ./model.gguf

# 3. 在新环境中导入
# 使用上述方法 1 重新创建
```

## 最佳实践

1. **版本管理**: 在模型名称中包含版本号，如 `qwen3-vl:2b-thinking-q4_K_M-v1.0`
2. **文档记录**: 记录模型的训练参数、数据集和性能指标
3. **定期备份**: 定期备份模型文件和 Modelfile
4. **性能测试**: 导入后进行完整的性能测试
5. **监控资源**: 监控内存和 GPU 使用情况

## 参考资源

- [Ollama 官方文档](https://github.com/ollama/ollama)
- [Ollama Modelfile 语法](https://github.com/ollama/ollama/blob/main/docs/modelfile.md)
- [导入模型指南](https://github.com/ollama/ollama/blob/main/docs/import.md)
- [GGUF 格式说明](https://github.com/ggerganov/llama.cpp)

