FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    libgomp1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# 配置 pip 使用清华源,增加超时时间
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.timeout 300

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖(增加超时和重试)
RUN pip install --no-cache-dir --timeout=300 --retries=5 -r requirements.txt

# Phase 5: 预下载 Sentence Transformer 模型(跳过,容器启动时自动下载)
# 注意: 模型会在首次使用时自动下载到挂载的 volume
RUN mkdir -p /app/models/cache

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p data/documents data/processed data/vector_db logs

# 设置环境变量
ENV SENTENCE_TRANSFORMERS_HOME=/app/models/cache
ENV TRANSFORMERS_CACHE=/app/models/cache
ENV HF_HOME=/app/models/cache

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

