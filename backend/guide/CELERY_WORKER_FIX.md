# Celery Worker OpenCV 依赖修复指南

## 问题描述

在之前的测试中，Celery Worker 容器缺少 OpenCV 所需的系统库，导致批量上传文档处理失败，出现以下错误：

```
ImportError: libGL.so.1: cannot open shared object file: No such file or directory
```

这是因为 `opencv-python` 或 `opencv-python-headless` 需要特定的系统库支持，而原始的 Dockerfile 只安装了基本的编译工具。

## 修复内容

### 1. 系统依赖修复

在 `Dockerfile.celery` 中添加了 OpenCV 所需的系统库：

```dockerfile
# 安装系统依赖（包括 OpenCV 所需的库）
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libgl1-mesa-glx \      # OpenGL 库
    libglib2.0-0 \         # GLib 库
    libsm6 \               # X11 Session Management 库
    libxext6 \             # X11 扩展库
    libxrender-dev \       # X Rendering 扩展库
    libgomp1 \             # OpenMP 运行时库
    && rm -rf /var/lib/apt/lists/*
```

### 2. Python 依赖补充

添加了文档处理所需的完整 Python 依赖：

```dockerfile
RUN pip install --no-cache-dir \
    celery==5.3.6 \
    redis==5.0.7 \
    sqlalchemy==2.0.31 \
    asyncpg==0.29.0 \
    psycopg2-binary==2.9.9 \
    pydantic==2.8.0 \
    pydantic-settings==2.4.0 \
    loguru==0.7.2 \
    python-dotenv==1.0.1 \
    PyMuPDF==1.24.5 \
    python-docx==1.1.2 \
    opencv-python-headless==4.10.0.84 \  # 新增
    Pillow==11.0.0 \                      # 新增
    paddleocr==2.8.1 \                    # 新增
    -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 重新构建和部署

### 步骤 1: 停止现有容器

```bash
cd backend
docker-compose down
```

### 步骤 2: 重新构建 Celery Worker 镜像

```bash
# 强制重新构建（不使用缓存）
docker-compose build --no-cache celery-worker
```

或者只重新构建 Celery Worker：

```bash
docker build --no-cache -f Dockerfile.celery -t multimodal-docqa-celery .
```

### 步骤 3: 启动所有服务

```bash
docker-compose up -d
```

### 步骤 4: 验证 Celery Worker 状态

```bash
# 查看容器日志
docker-compose logs -f celery-worker

# 检查容器状态
docker-compose ps

# 进入容器验证依赖
docker exec -it multimodal-docqa-celery python -c "import cv2; print(cv2.__version__)"
```

## 验证修复

### 方法 1: 使用测试脚本

运行批量上传测试脚本：

```bash
cd backend
python tests/test_batch_upload.py
```

### 方法 2: 手动测试

1. 启动后端服务：
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

2. 使用 API 测试工具（如 Postman）或 curl 测试批量上传：

```bash
curl -X POST "http://localhost:8000/api/v1/documents/batch-upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "files=@test1.pdf" \
  -F "files=@test2.pdf"
```

3. 检查任务状态：

```bash
curl -X GET "http://localhost:8000/api/v1/documents/batch-upload/TASK_ID/status" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 预期结果

修复后，Celery Worker 应该能够：

1. ✅ 成功导入 OpenCV 库
2. ✅ 处理包含图像的 PDF 文档
3. ✅ 执行 OCR 文本识别
4. ✅ 完成批量文档上传任务

## 故障排查

### 问题 1: 构建失败

如果构建过程中出现网络问题：

```bash
# 使用国内镜像源
docker build --no-cache \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  -f Dockerfile.celery -t multimodal-docqa-celery .
```

### 问题 2: 容器启动失败

检查日志：

```bash
docker-compose logs celery-worker
```

常见问题：
- Redis 连接失败：检查 Redis 容器是否正常运行
- PostgreSQL 连接失败：检查数据库容器是否正常运行
- Ollama 连接失败：检查 Ollama 服务是否可访问

### 问题 3: 依赖仍然缺失

进入容器手动检查：

```bash
docker exec -it multimodal-docqa-celery bash

# 检查系统库
ldconfig -p | grep libGL
ldconfig -p | grep libglib

# 检查 Python 包
pip list | grep opencv
pip list | grep paddleocr
```

## 性能优化建议

### 1. 调整并发数

根据服务器资源调整 Celery Worker 并发数：

```yaml
# docker-compose.yml
celery-worker:
  command: celery -A app.celery_app worker --loglevel=info --concurrency=4
```

### 2. 资源限制

为容器设置资源限制：

```yaml
celery-worker:
  deploy:
    resources:
      limits:
        cpus: '2.0'
        memory: 4G
      reservations:
        cpus: '1.0'
        memory: 2G
```

### 3. 监控和日志

启用 Celery Flower 监控：

```bash
# 安装 Flower
pip install flower

# 启动监控
celery -A app.celery_app flower --port=5555
```

## 相关文档

- [Phase 4 API 测试指南](PHASE4_API_TEST_GUIDE.md)
- [Phase 4 测试报告](../PHASE4_TEST_REPORT.md)
- [Docker Compose 配置](../docker-compose.yml)
- [Celery Worker Dockerfile](../Dockerfile.celery)

## 更新日志

- **2025-01-XX**: 初始版本，修复 OpenCV 依赖问题
- 添加了完整的系统库支持
- 补充了文档处理所需的 Python 包
- 提供了详细的验证和故障排查指南
