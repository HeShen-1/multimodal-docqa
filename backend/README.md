# 多模态文档智能问答系统 - 后端

基于FastAPI + Ollama + ChromaDB的本地化文档问答系统后端。

## 功能特性

- 📄 支持PDF、DOCX文档上传和解析
- 🔍 混合检索（向量检索 + BM25）
- 🤖 基于Qwen3-VL的智能问答
- 🧠 Thinking Chain推理可视化
- 🎯 本地化部署，数据安全

## 快速开始

### 环境要求

- Python 3.11+
- Ollama 0.5.0+
- 8GB+ RAM

### 安装步骤

1. **创建虚拟环境**

```bash
conda create -n multimodal-docqa python=3.11 -y
conda activate multimodal-docqa
```

2. **安装依赖**

```bash
pip install -r requirements.txt
```

3. **配置环境变量**

```bash
cp .env.example .env
# 编辑.env文件
```

4. **启动Ollama并拉取模型**

```bash
ollama serve
ollama pull qwen3-vl:2b-thinking
ollama pull qwen3-embedding:0.6b-fp16
```

5. **启动后端服务**

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

6. **访问API文档**

打开浏览器访问: http://localhost:8000/docs

## 项目结构

```
backend/
├── app/
│   ├── api/v1/          # API路由
│   ├── models/          # 数据模型
│   ├── services/        # 业务逻辑
│   ├── prompts/         # 提示词
│   ├── utils/           # 工具函数
│   ├── config.py        # 配置
│   └── main.py          # 应用入口
├── tests/               # 测试
├── data/                # 数据目录
└── requirements.txt     # 依赖
```

## API接口

### 文档管理

- `POST /api/v1/documents/upload` - 上传文档
- `GET /api/v1/documents` - 获取文档列表
- `GET /api/v1/documents/{id}` - 获取文档详情
- `DELETE /api/v1/documents/{id}` - 删除文档
- `GET /api/v1/documents/{id}/status` - 获取处理状态

### 查询问答

- `POST /api/v1/query` - 执行问答
- `POST /api/v1/query/stream` - 流式问答
- `GET /api/v1/query/history` - 获取历史记录

### 系统管理

- `GET /api/v1/health` - 健康检查
- `GET /api/v1/stats` - 统计信息

## 开发指南

### 运行测试

```bash
pytest tests/
```

### 代码格式化

```bash
black app/
isort app/
```

## 技术栈

- **Web框架**: FastAPI 0.115.0
- **LLM**: Ollama (Qwen3-VL)
- **向量数据库**: ChromaDB
- **文档解析**: PyMuPDF, python-docx
- **OCR**: PaddleOCR
- **文本检索**: BM25

## 许可证

MIT License

