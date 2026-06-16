"""Central configuration, loaded from environment / .env.

Note: env reads happen here (in plain Python), never inside a Temporal
workflow. Workflows receive everything they need via arguments/activities.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = (
        "postgresql+asyncpg://supervisor:supervisor@localhost:5432/order_supervisor"
    )

    # Temporal
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "order-supervisor"

    # LLM
    llm_provider: str = "mock"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_api_key: str = ""

    # Demo time scaling: "hours" * time_scale (in this many real seconds per hour)
    # is computed as seconds = hours * 3600 / time_scale_divisor.  We keep it
    # simple: TIME_SCALE is "real seconds per sim-hour".
    time_scale: float = 1.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
