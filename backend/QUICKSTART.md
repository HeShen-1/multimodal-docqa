# 快速启动指南

## 1. 安装Ollama并拉取模型

```bash
# 启动Ollama服务
ollama serve

# 在新终端中拉取模型
ollama pull qwen3-vl:2b-thinking
ollama pull qwen3-embedding:0.6b-fp16
```

## 2. 安装Python依赖

```bash
# 创建虚拟环境
conda create -n multimodal-docqa python=3.11 -y
conda activate multimodal-docqa

# 安装依赖
pip install -r requirements.txt
```

## 3. 初始化数据库

```bash
python scripts/init_db.py
```

## 4. 启动后端服务

```bash
# 开发模式
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或直接运行
python app/main.py
```

## 5. 访问API文档

打开浏览器访问: http://localhost:8000/docs

## 测试API

### 上传文档
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@test.pdf" \
  -F "description=测试文档"
```

### 执行问答
```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "这份文档的主要内容是什么？",
    "topK": 5,
    "enableThinking": true
  }'
```

### 健康检查
```bash
curl http://localhost:8000/api/v1/health
```

## 常见问题

### 1. Ollama连接失败
确保Ollama服务正在运行：
```bash
ollama serve
```

### 2. 模型未找到
拉取所需模型：
```bash
ollama pull qwen3-vl:2b-thinking
ollama pull qwen3-embedding:0.6b-fp16
```

### 3. 端口被占用
修改`.env`文件中的`PORT`配置，或使用其他端口启动：
```bash
uvicorn app.main:app --port 8001
```

