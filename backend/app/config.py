from functools import lru_cache
import json
from typing import List, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_DEV_CORS_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

DEFAULT_SECRET_PLACEHOLDERS = {
    "",
    "your-secret-key-change-in-production",
    "your-secret-key-change-in-production-use-long-random-string",
}


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "多模态文档智能问答系统"
    app_version: str = "1.0.0"
    environment: Literal["development", "testing", "production"] = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    cors_allowed_origins: List[str] = Field(default_factory=lambda: DEFAULT_DEV_CORS_ORIGINS.copy())

    ollama_base_url: str = "http://127.0.0.1:11434/api"
    ollama_llm_model: str = "qwen3-vl:2b-thinking-q4_K_M"
    ollama_embedding_model: str = "qwen3-embedding:0.6b-fp16"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "multimodal_docqa"

    @property
    def database_url(self) -> str:
        return (
            "postgresql+asyncpg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    chroma_persist_dir: str = "./data/vector_db/chroma"

    milvus_host: str = "localhost"
    milvus_port: int = 19530

    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080
    refresh_token_expire_days: int = 7

    rate_limit_enabled: bool = True
    rate_limit_login: str = "5/minute"
    rate_limit_register: str = "3/minute"
    rate_limit_default: str = "60/minute"

    max_file_size: int = 10485760
    allowed_file_types: List[str] = Field(
        default_factory=lambda: [
            ".pdf",
            ".docx",
            ".txt",
            ".md",
            ".csv",
            ".tsv",
            ".json",
            ".jsonl",
            ".html",
            ".htm",
            ".xml",
            ".yaml",
            ".yml",
            ".log",
            ".ini",
        ]
    )
    chunk_size: int = 500
    chunk_overlap: int = 50

    log_level: str = "INFO"
    log_file: str = "./logs/app.log"

    timezone: str = "Asia/Shanghai"

    cache_enabled: bool = True
    cache_default_expire: int = 1800
    cache_query_expire: int = 1800
    cache_document_expire: int = 3600
    cache_user_expire: int = 7200
    cache_max_keys: int = 10000

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _parse_cors_allowed_origins(cls, value):
        if value is None:
            return DEFAULT_DEV_CORS_ORIGINS.copy()

        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return DEFAULT_DEV_CORS_ORIGINS.copy()
            if raw == "*":
                return ["*"]
            if raw.startswith("["):
                parsed = json.loads(raw)
                return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in raw.split(",") if item.strip()]

        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]

        raise TypeError("cors_allowed_origins 必须是字符串或字符串列表")

    @field_validator("allowed_file_types", mode="before")
    @classmethod
    def _parse_allowed_file_types(cls, value):
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("["):
                parsed = json.loads(raw)
                return [str(item).strip().lower() for item in parsed if str(item).strip()]
            return [item.strip().lower() for item in raw.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def _validate_production_settings(self):
        if self.environment == "production":
            if self.secret_key.strip() in DEFAULT_SECRET_PLACEHOLDERS:
                raise ValueError("生产环境必须配置强随机 SECRET_KEY")
            if "*" in self.cors_allowed_origins:
                raise ValueError("生产环境禁止使用通配符 CORS_ALLOWED_ORIGINS")
        return self


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
