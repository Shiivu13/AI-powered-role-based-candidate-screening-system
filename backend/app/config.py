from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "AI Interview System"
    DEBUG: bool = False

    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    DATABASE_URL: str = "sqlite+aiosqlite:///./interview.db"
    CHROMA_DB_PATH: str = "./chroma_db"

    MAX_QUESTIONS: int = 7
    FRONTEND_URL: str = "http://localhost:3000"

    class Config:
        env_file = ".env"


settings = Settings()
