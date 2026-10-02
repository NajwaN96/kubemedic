"""Runtime configuration loaded from environment variables."""

from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Database credentials and feature flags.

    Passwords are read from the environment. Nothing here is a production secret.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "taskflow"
    database_user: str = "taskflow"
    database_password: str = ""
    database_connect_timeout: int = 3
    service_name: str = "taskflow-api"
    log_level: str = "INFO"
    cors_origins: str = "*"
    fault_injection_enabled: bool = False
    # Test-only override. Production uses DATABASE_* above.
    sqlalchemy_url: str | None = Field(default=None)

    def resolved_database_url(self) -> str:
        if self.sqlalchemy_url:
            return self.sqlalchemy_url
        user = quote_plus(self.database_user)
        password = quote_plus(self.database_password)
        return (
            f"postgresql+psycopg://{user}:{password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )
