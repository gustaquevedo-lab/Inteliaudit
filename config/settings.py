from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Base de datos
    # Railway inyecta DATABASE_URL como postgres://... — lo normalizamos a asyncpg
    database_url: str = "sqlite+aiosqlite:///./inteliaudit.db"

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        # Normalizar scheme para asyncpg
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        # asyncpg no acepta ?sslmode= — lo reemplazamos por ?ssl=
        url = url.replace("?sslmode=require", "?ssl=require")
        url = url.replace("&sslmode=require", "&ssl=require")
        return url

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
