from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://jobflow:jobflow_secret@localhost:5432/jobflow_db"

    # Redis (general cache)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # App
    SECRET_KEY: str = "dev_secret_key"
    CACHE_TTL: int = 300  # seconds — how long to cache job stats

    class Config:
        env_file = ".env"


settings = Settings()
