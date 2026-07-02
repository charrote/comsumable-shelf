"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "智能物料管理系统"
    APP_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"

    # Database (PostgreSQL)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:~Jonly171299~@localhost:5432/smes"

    # XR auto-match time window
    XR_MATCH_WINDOW_SECONDS: int = 10

    # ── 智能料架 HTTP API ──
    RACK_API_TIMEOUT: int = 5  # HTTP 请求超时秒数
    RACK_API_MAX_RETRIES: int = 3  # 最大重试次数
    RACK_SLOT_POLL_INTERVAL: int = 10  # 储位轮询间隔秒数

    # FIFO strategy (tail_first | time_fifo | mixed)
    FIFO_STRATEGY: str = "tail_first"

    # BOM auto-create materials
    BOM_AUTO_CREATE_MATERIAL: bool = True

    SECRET_KEY: str = "changeme-secret-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Auto-run schema migrations on startup (disable in production)
    DB_AUTO_MIGRATE: bool = True

    LOG_LEVEL: str = "info"

    # Backup
    BACKUP_DIR: str = "/app/backups"
    BACKUP_DB_HOST: str = "localhost"
    BACKUP_DB_PORT: int = 15212
    BACKUP_DB_NAME: str = "smes"
    BACKUP_DB_USER: str = "postgres"
    BACKUP_DB_PASSWORD: str = "~Jonly171299~"


# Create a global settings instance
settings = Settings()
