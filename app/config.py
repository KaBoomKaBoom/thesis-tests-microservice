from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Create a .env file in the project root with these variables.
    """
    # Database - PostgreSQL credentials
    postgres_user: str
    postgres_password: str
    postgres_db: str
    database_url: str
    
    # API Settings
    api_title: str
    api_version: str
    
    # CORS
    cors_origins: str
    
    # Security
    jwt_secret: str
    jwt_issuer: str
    jwt_audience: str
    algorithm: str
    access_token_expire_minutes: int

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False
    )
    
    def get_cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Use this in dependencies.
    """
    return Settings()
