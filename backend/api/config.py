from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "PropriétéGraph"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://propriete:propriete@localhost:5432/propriete_graph"
    DATABASE_URL_SYNC: str = "postgresql://propriete:propriete@localhost:5432/propriete_graph"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Data sources
    DVF_BASE_URL: str = "https://files.data.gouv.fr/geo-dvf/latest/csv"
    BAN_BASE_URL: str = "https://adresse.data.gouv.fr/data/ban/adresses/latest/csv"
    CADASTRE_BASE_URL: str = "https://cadastre.data.gouv.fr/data/etalab-cadastre/latest/geojson/communes"

    # Cache TTL (seconds)
    CACHE_TTL_SHORT: int = 300       # 5 min
    CACHE_TTL_MEDIUM: int = 3600     # 1 hour
    CACHE_TTL_LONG: int = 86400      # 24 hours

    # Pagination
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 500

    # ML Model paths
    MODEL_DIR: str = "/app/models"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
