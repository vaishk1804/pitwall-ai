# app/core/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
  app_name: str = "PitWall AI"
  app_version: str = "1.0.0"
  debug: bool = False

  # Database
  database_url: str = "postgresql://pitwall:pitwall@db:5432/pitwall"
  database_url_test: str = "postgresql://pitwall:pitwall@db:5432/pitwall_test"

  # Redis / Celery
  redis_url: str = "redis://redis:6379/0"
  celery_broker_url: str = "redis://redis:6379/0"
  celery_broker_backend: str = "redis://redis:6379/1"

  # Anthropic
  anthropic_api_key: str = ""
  claude_model: str = "claude-sonnet-4-6"
  max_tokens: int = 2048

  # OpenF1
  openf1_base_url: str = "https://api.openf1.org/v1"

  # Observability
  log_level: str = "INFO"
  log_llm_inputs: bool = True
  log_llm_outputs: bool = True

  class Config:
    env_file = ".env"
    extra = "ignore"

@lru_cache
def get_settings() -> Settings:
  return Settings()