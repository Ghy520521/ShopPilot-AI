"""全局配置：通过环境变量 / .env 注入，默认值保证本地无外部依赖即可启动。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ShopPilot AI"
    env: str = "dev"
    debug: bool = True

    # 数据库：本地默认 sqlite，Docker 下覆盖为 postgres
    database_url: str = "sqlite:///./shoppilot.db"

    # JWT
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120

    # Redis：留空自动降级为进程内缓存
    redis_url: str = ""

    # Celery
    celery_broker_url: str = ""
    celery_result_backend: str = ""

    # LLM / Embedding
    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = "gpt-4o-mini"
    embedding_provider: str = "local"
    embedding_model: str = "text-embedding-3-small"

    # 检索参数
    search_recall_k: int = 20
    search_rerank_k: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
