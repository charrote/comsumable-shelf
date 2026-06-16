"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "ConsumableShelf"
    APP_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"

    # Database (PostgreSQL)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/smes"

    # Hardware — AMKN8702G Master (Modbus TCP)
    MASTER_IP: str = "192.168.1.100"
    MASTER_PORT: int = 502
    MASTER_STATION: int = 200  # fixed station ID

    # Hardware — AMKN7141-CHXX LED (Modbus RTU via master relay)
    LED_PROTOCOL: str = "protocol2"  # 4-coil per LED, local update
    SLOT_BITS_PER_BOARD: int = 20  # max 20 slots per LED board

    # Hardware — Modbus RTU (for future direct serial use)
    RTU_BAUDRATE: int = 38400
    RTU_DATABITS: int = 8
    RTU_STOPBITS: int = 1
    RTU_PARITY: str = "N"

    # XR auto-match time window
    XR_MATCH_WINDOW_SECONDS: int = 10

    # LED command workers
    LED_WORKER_COUNT: int = 4

    LOG_LEVEL: str = "info"


# Create a global settings instance
settings = Settings()
