import os
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Configurações da aplicação CONFORME PDF"""
    
    # Redis CONFORME PDF
    REDIS_URL: str = Field(default="redis://localhost:6379")
    
    # LLM Providers CONFORME PDF
    OPENAI_API_KEY: str = Field(default="")
    GEMINI_API_KEY: str = Field(default="") 
    ANTHROPIC_API_KEY: str = Field(default="")
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    
    # Server
    PORT: int = Field(default=8000)
    ENVIRONMENT: str = Field(default="development")
    ALLOWED_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:3000", 
            "http://localhost:5173", 
            "http://localhost:8080",
            "http://localhost:8081"
        ]
    )
    
    # Rate Limiting CONFORME PDF (5 msgs/5s)
    RATE_LIMIT_REQUESTS: int = Field(default=5)   # 5 mensagens
    RATE_LIMIT_WINDOW: int = Field(default=5)     # em 5 segundos
    
    # Message Limits CONFORME PDF
    MAX_MESSAGE_LENGTH: int = Field(default=1000)  # 1000 caracteres
    MAX_HISTORY_SIZE: int = Field(default=50)      # 50 mensagens no histórico
    HISTORY_TTL: int = Field(default=86400)        # 24 horas
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
