from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    app_env: str = "development"
    app_name: str = "ResearchGraph"
    log_level: str = "INFO"
    api_port: int = 8000

    llm_provider: str = "groq"
    llm_model: str = "llama-3.1-8b-instant"
    groq_api_key: str

    embedding_provider: str = "sentence_transformers"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str

    qdrant_host: str
    qdrant_port: int = 6333
    qdrant_api_key: str = ""
    qdrant_https: bool = False
    qdrant_collection: str = "papers"

    openalex_polite_email: str = "you@example.com"
    openalex_base_url: str = "https://api.openalex.org"

    ingest_default_topic: str = "retrieval augmented generation"
    ingest_default_limit: int = 200


@lru_cache
def get_settings() -> Settings:
    return Settings()
