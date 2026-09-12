"""
settings.py
-----------
Centralized configuration using Pydantic BaseSettings.
All environment variables are validated at startup.
"""

from typing import List
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Required
    google_api_key: str = ""

    # Chatbot LLM (Gemini); must support function calling
    llm_model: str = "gemini-3.5-flash-lite"

    # CORS
    allowed_origins: str = "http://localhost:3000"

    # Rate limiting
    rate_limit_per_minute: int = 30

    @property
    def cors_origins(self) -> List[str]:
        """Parse comma-separated origins into a list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @field_validator("google_api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == "your_google_api_key_here":
            raise ValueError(
                "GOOGLE_API_KEY is not set or is still the placeholder. "
                "Get a key at https://aistudio.google.com/app/apikey "
                "and add it to backend/.env"
            )
        return v


settings = Settings()
