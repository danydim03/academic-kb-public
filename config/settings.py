from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os


class Settings(BaseSettings):
    # Neo4j Config
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "YOUR_PASSWORD_HERE"
    neo4j_database: str = "neo4j"

    # Notion Config
    notion_api_key: Optional[str] = None
    notion_root_database_id: Optional[str] = None

    # Embedding Config
    embedding_provider: str = "mock"  # "mock", "gemini", "openai", "ollama"
    embedding_model: str = "text-embedding-004"
    embedding_dimension: int = 768
    embedding_api_key: Optional[str] = None
    embedding_base_url: Optional[str] = None

    # LLM Config (Provider-Agnostic)
    # Supported providers: "mock", "gemini", "openai", "deepseek", "ollama"
    llm_provider: str = "mock"
    llm_model: str = "gemini-2.0-flash"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None

    # Provider-specific fallback / alias keys
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None

    # Gemini Live Voice Config
    gemini_live_voice: str = "Charon"  # Charon (male, calm/authoritative), Puck (male), Fenrir (male)
    gemini_live_model: str = "gemini-3.8-live"

    # Knowledge Source Root Directory
    magistrale_courses_dir: str = "/path/to/your/courses"

    log_level: str = "INFO"

    @property
    def effective_llm_api_key(self) -> Optional[str]:
        """
        Resolves active API key by checking LLM_API_KEY first,
        then falling back to provider-specific environment variables.
        """
        if self.llm_api_key:
            return self.llm_api_key

        provider = (self.llm_provider or "").lower().strip()
        if provider == "gemini":
            return self.gemini_api_key or os.getenv("GEMINI_API_KEY")
        elif provider == "openai":
            return self.openai_api_key or os.getenv("OPENAI_API_KEY")
        elif provider == "deepseek":
            return self.deepseek_api_key or self.openai_api_key or os.getenv("DEEPSEEK_API_KEY")
        return None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


def get_settings() -> Settings:
    return Settings()
