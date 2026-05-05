from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Base de datos
    database_url: str = "sqlite+aiosqlite:///./inteliaudit.db"

    # Claude API
    anthropic_api_key: str = ""

    # App
    secret_key: str = "dev-secret-change-in-production"
    debug: bool = False

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 480  # 8 horas

    # Eslogan para informes
    eslogan: str = "Auditoría impositiva inteligente para Paraguay"

    # Storage para archivos descargados de SET
    storage_path: str = "./storage"

    # Cifrado de credenciales Marangatú en DB
    encryption_key: str = ""

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


settings = Settings()
