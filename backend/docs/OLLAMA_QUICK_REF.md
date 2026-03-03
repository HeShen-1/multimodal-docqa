# Ollama Docker 快速参考

## 快速启动

### Windows
```powershell
cd backend
.\scripts\start-ollama.ps1
```

### Linux/Mac
```bash
cd backend
chmod +x scripts/start-ollama.sh
./scripts/start-ollama.sh
```

## 常用命令

### 启动服务
```bash
docker-compose up -d ollama
```

### 停止服务
```bash
docker-compose stop ollama
```

### 重启服务
```bash
docker-compose restart ollama
```

### 查看日志
```bash
docker-compose logs -f ollama
```

### 查看状态
```bash
docker-compose ps ollama
```

## 模型管理

### 下载模型
```bash
# 嵌入模型（必需）
docker-compose exec ollama ollama pull qwen3-embedding:0.6b-fp16

# 对话模型（可选）
docker-compose exec ollama ollama pull qwen2.5:7b
```

### 列出模型
```bash
docker-compose exec ollama ollama list
```

### 删除模型
```bash
docker-compose exec ollama ollama rm qwen2.5:7b
```

## 测试验证

### Python 测试脚本
```bash
conda activate multimodal-docqa
python scripts/test_ollama.py
```

### API 测试
```bash
# 检查服务
curl http://localhost:11434/api/tags

# 测试嵌入
curl -X POST http://localhost:11434/api/embed \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen3-embedding:0.6b-fp16", "input": "测试"}'
```

## 故障排查

### 服务无法启动
```bash
# 查看详细日志
docker-compose logs ollama

# 检查端口占用
netstat -ano | findstr :11434  # Windows
lsof -i :11434                 # Linux/Mac
```

### GPU 不可用
```bash
# 检查 GPU
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# 如果没有 GPU，修改 docker-compose.yml 移除 GPU 配置
```

### 模型下载失败
```bash
# 使用代理
docker-compose exec ollama bash
export HTTP_PROXY=http://proxy:port
ollama pull qwen3-embedding:0.6b-fp16
```

## 配置文件

### docker-compose.yml
```yaml
ollama:
  image: ollama/ollama:latest
  ports:
    - "11434:11434"
  volumes:
    - ollama_data:/root/.ollama
```

### .env
```env
OLLAMA_BASE_URL=http://ollama:11434/api
OLLAMA_EMBEDDING_MODEL=qwen3-embedding:0.6b-fp16
```

## 性能优化

### 预加载模型
```bash
curl -X POST http://localhost:11434/api/generate \
  -d '{"model": "qwen3-embedding:0.6b-fp16", "keep_alive": -1}'
```

### 调整并发
```yaml
environment:
  - OLLAMA_NUM_PARALLEL=4
  - OLLAMA_MAX_LOADED_MODELS=2
```

## 数据备份

### 备份模型数据
```bash
docker run --rm \
  -v multimodal-docqa_ollama_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/ollama-backup.tar.gz /data
```

### 恢复模型数据
```bash
docker run --rm \
  -v multimodal-docqa_ollama_data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/ollama-backup.tar.gz -C /
```

## 更新

### 更新 Ollama
```bash
docker-compose pull ollama
docker-compose up -d ollama
```

### 更新模型
```bash
docker-compose exec ollama ollama pull qwen3-embedding:0.6b-fp16
```

## 监控

### 资源使用
```bash
docker stats multimodal-docqa-ollama
```

### 模型状态
```bash
curl http://localhost:11434/api/ps
```

## 完全清理

```bash
# 停止并删除容器
docker-compose down ollama

# 删除数据卷（谨慎！）
docker volume rm multimodal-docqa_ollama_data
```

