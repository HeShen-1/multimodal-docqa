#!/usr/bin/env python3
"""数据库初始化脚本"""

from pathlib import Path
from loguru import logger


def init_directories():
    """初始化目录结构"""
    directories = [
        "data/documents",
        "data/processed",
        "data/vector_db/chroma",
        "logs"
    ]
    
    for directory in directories:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        logger.info(f"创建目录: {directory}")


def init_vector_db():
    """初始化向量数据库"""
    import chromadb
    
    client = chromadb.PersistentClient(path="./data/vector_db/chroma")
    
    # 删除旧的collection（如果存在）
    try:
        client.delete_collection(name="text_chunks")
        logger.info("删除旧的 text_chunks collection")
    except:
        pass
    
    # 创建collection，明确指定维度为 1024（qwen3-embedding:0.6b-fp16 的维度）
    collection = client.create_collection(
        name="text_chunks",
        metadata={
            "hnsw:space": "cosine",
            "dimension": 1024  # qwen3-embedding:0.6b-fp16 的向量维度
        }
    )
    
    logger.info("ChromaDB初始化完成（向量维度: 1024）")


if __name__ == "__main__":
    logger.info("开始初始化数据库...")
    
    init_directories()
    init_vector_db()
    
    logger.info("数据库初始化完成！")

