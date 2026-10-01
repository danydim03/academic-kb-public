from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Neo4j Config
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "YOUR_PASSWORD_HERE"
    neo4j_database: str = "neo4j"

    # Notion Config
    notion_api_key: Optional[str] = None
    notion_root_database_id: Optional[str] = None

    # LLM & Embedding Config
    embedding_provider: str = "mock"
    embedding_model: str = "text-embedding-004"
    embedding_dimension: int = 768
    embedding_api_key: Optional[str] = None
    embedding_base_url: Optional[str] = None

    llm_provider: str = "mock"
    llm_model: str = "gemini-2.0-flash"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None

    # Knowledge Source Root Directory
    magistrale_courses_dir: str = "/path/to/your/courses"

    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

def get_settings() -> Settings:
    return Settings()
