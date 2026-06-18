"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "智能物料管理系统"
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

    # Slot auto-assign polling
    SLOT_POLL_INTERVAL: int = 3  # seconds between sensor polls
    AUTO_ASSIGN_ENABLED: bool = True

    # Hardware — Label Printer (ZPL over TCP)
    LABEL_PRINTER_IP: str = ""
    LABEL_PRINTER_PORT: int = 9100

    # FIFO strategy (tail_first | time_fifo | mixed)
    # Simulation mode (no real hardware needed for testing)
    HARDWARE_SIMULATION: bool = False

    FIFO_STRATEGY: str = "tail_first"

    # BOM auto-create materials
    BOM_AUTO_CREATE_MATERIAL: bool = True

    SECRET_KEY: str = "changeme-secret-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    LOG_LEVEL: str = "info"


# Create a global settings instance
settings = Settings()
