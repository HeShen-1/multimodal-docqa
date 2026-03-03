# Docker Compose 配置 - 使用本地目录存储模型

## 当前配置（Docker Volume）

```yaml
ollama:
  volumes:
    - ollama_data:/root/.ollama  # Docker 管理的 volume
```

**优点**：
- Docker 自动管理
- 性能较好
- 跨平台兼容

**缺点**：
- 不在本地可见目录
- 需要 docker cp 访问文件

---

## 修改为本地目录存储

### 方法 1: 完全本地化（推荐用于开发）

```yaml
ollama:
  image: ollama/ollama:latest
  container_name: multimodal-docqa-ollama
  restart: unless-stopped
  ports:
    - "11434:11434"
  volumes:
    # 使用本地目录替代 Docker volume
    - ./data/ollama:/root/.ollama
    # 可选：单独挂载模型目录
    - ./models:/models
  environment:
    - OLLAMA_HOST=0.0.0.0
  networks:
    - app-network
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
```

**存储位置**：
- 模型数据：`backend/data/ollama/`
- 自定义模型：`backend/models/`

### 方法 2: 混合模式（推荐用于生产）

```yaml
ollama:
  image: ollama/ollama:latest
  container_name: multimodal-docqa-ollama
  restart: unless-stopped
  ports:
    - "11434:11434"
  volumes:
    # 核心数据使用 Docker volume（性能好）
    - ollama_data:/root/.ollama
    # 自定义模型使用本地目录（方便管理）
    - ./models:/models:ro  # 只读挂载
  environment:
    - OLLAMA_HOST=0.0.0.0
  networks:
    - app-network
```

**存储位置**：
- 下载的模型：Docker volume（不可见）
- 自定义模型：`backend/models/`（可见）

---

## 迁移步骤

### 从 Docker Volume 迁移到本地目录

```powershell
# 1. 停止容器
docker-compose stop ollama

# 2. 创建本地目录
New-Item -ItemType Directory -Force -Path ".\data\ollama"

# 3. 复制数据
docker run --rm `
  -v multimodal-docqa_ollama_data:/source `
  -v ${PWD}\data\ollama:/target `
  alpine sh -c "cp -r /source/* /target/"

# 4. 修改 docker-compose.yml（使用上面的配置）

# 5. 重启容器
docker-compose up -d ollama

# 6. 验证
docker exec multimodal-docqa-ollama ollama list
```

### 从本地目录迁移到 Docker Volume

```powershell
# 1. 停止容器
docker-compose stop ollama

# 2. 复制数据到 volume
docker run --rm `
  -v ${PWD}\data\ollama:/source `
  -v multimodal-docqa_ollama_data:/target `
  alpine sh -c "cp -r /source/* /target/"

# 3. 修改 docker-compose.yml（恢复原配置）

# 4. 重启容器
docker-compose up -d ollama
```

---

## 目录结构说明

### Docker Volume 内部结构

```
/root/.ollama/
├── models/
│   ├── manifests/          # 模型清单
│   │   └── registry.ollama.ai/
│   │       └── library/
│   │           ├── qwen3-embedding/
│   │           └── qwen2.5/
│   └── blobs/              # 实际模型文件（GGUF）
│       ├── sha256-xxx...   # 模型权重
│       ├── sha256-yyy...   # 模型配置
│       └── ...
└── history/                # 对话历史
```

### 本地目录结构（如果使用本地挂载）

```
backend/
├── data/
│   └── ollama/             # Ollama 数据目录
│       ├── models/
│       │   ├── manifests/
│       │   └── blobs/
│       └── history/
└── models/                 # 自定义模型目录
    ├── qwen3-vl-2b-thinking-q4_K_M.gguf
    └── Modelfile.qwen3-vl-custom
```

---

## 访问模型文件

### 从 Docker Volume 复制模型

```powershell
# 复制单个模型文件
docker cp multimodal-docqa-ollama:/root/.ollama/models/blobs/sha256-xxx ./backup/

# 复制整个模型目录
docker cp multimodal-docqa-ollama:/root/.ollama/models ./backup/ollama-models/

# 查找特定模型的文件
docker exec multimodal-docqa-ollama find /root/.ollama/models -name "*qwen*"
```

### 直接访问 Docker Volume

```powershell
# Windows
cd C:\ProgramData\Docker\volumes\multimodal-docqa_ollama_data\_data

# Linux
cd /var/lib/docker/volumes/multimodal-docqa_ollama_data/_data
```

---

## 推荐配置

### 开发环境（方便调试）

```yaml
volumes:
  - ./data/ollama:/root/.ollama  # 本地目录，方便查看
  - ./models:/models              # 自定义模型
```

### 生产环境（性能优先）

```yaml
volumes:
  - ollama_data:/root/.ollama     # Docker volume，性能好
  - ./models:/models:ro           # 自定义模型只读
```

---

## 磁盘空间管理

### 查看占用空间

```powershell
# 查看 volume 大小
docker system df -v | Select-String "ollama"

# 查看容器内占用
docker exec multimodal-docqa-ollama du -sh /root/.ollama
```

### 清理空间

```powershell
# 删除未使用的模型
docker exec multimodal-docqa-ollama ollama rm model-name

# 清理 Docker volume（谨慎！）
docker volume prune
```

---

## 备份和恢复

### 备份到本地

```powershell
# 备份整个 volume
docker run --rm `
  -v multimodal-docqa_ollama_data:/data `
  -v ${PWD}:/backup `
  alpine tar czf /backup/ollama-backup-$(Get-Date -Format 'yyyyMMdd').tar.gz /data

# 备份特定模型
docker exec multimodal-docqa-ollama ollama show model-name --modelfile > model-backup.txt
```

### 从本地恢复

```powershell
# 恢复 volume
docker run --rm `
  -v multimodal-docqa_ollama_data:/data `
  -v ${PWD}:/backup `
  alpine tar xzf /backup/ollama-backup-20260228.tar.gz -C /
```

