from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用配置
    app_name: str = "多模态文档智能问答系统"
    app_version: str = "1.0.0"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Ollama配置
    ollama_base_url: str = "http://127.0.0.1:11434/api"
    ollama_llm_model: str = "qwen3-vl:2b-thinking-q4_K_M"
    ollama_embedding_model: str = "qwen3-embedding:0.6b-fp16"
    
    # 数据库配置
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "multimodal_docqa"
    
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    # Redis配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    
    # ChromaDB配置
    chroma_persist_dir: str = "./data/vector_db/chroma"
    
    # Milvus配置
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    
    # JWT配置
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24小时
    refresh_token_expire_days: int = 7  # 7天
    
    # 限流配置
    rate_limit_enabled: bool = True
    rate_limit_login: str = "5/minute"  # 登录接口限流
    rate_limit_register: str = "3/minute"  # 注册接口限流
    rate_limit_default: str = "60/minute"  # 默认限流
    
    # 文档配置
    max_file_size: int = 10485760  # 10MB
    allowed_file_types: List[str] = [".pdf", ".docx"]
    chunk_size: int = 500
    chunk_overlap: int = 50
    
    # 日志配置
    log_level: str = "INFO"
    log_file: str = "./logs/app.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()

