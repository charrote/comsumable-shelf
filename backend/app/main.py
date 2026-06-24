"""FastAPI application entry point."""

import structlog
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.utils.database import init_db, seed_db
from app.api.auth import router as auth_router
from app.api.receipt import router as receipt_router
from app.api.issue import router as issue_router
from app.api.inventory import router as inventory_router
from app.api.xr import router as xr_router
from app.api.bom import router as bom_router
from app.api import report
from app.api.shelves import router as shelves_router
from app.api.materials import router as materials_router
from app.api.users import router as users_router
from app.api.settings import router as settings_router
from app.api.customers import router as customers_router
from app.api.hardware_debug import router as hardware_debug_router
from app.api.dashboard import router as dashboard_router
from app.api.shelving import router as shelving_router
from app.api.barcode_definition import router as barcode_definition_router
from app.api.transactions import router as transactions_router
from app.api.backup import router as backup_router
from app.services.led_service import LedService
from app.services.shelf_service import SlotPollingService

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=False,
)
logger = structlog.get_logger()


async def lifespan(app: FastAPI):
    """Application startup/shutdown."""
    logger.info("Starting up ConsumableShelf backend")
    await init_db()
    await seed_db()
    logger.info("Database initialized")

    # ── LED service ──
    led_service = LedService()
    try:
        await led_service.init(
            master_ip=settings.MASTER_IP,
            port=settings.MASTER_PORT,
        )
        app.state.led_service = led_service
        logger.info("LED service started")
    except Exception as e:
        logger.warning(f"LED service init failed (hardware may be offline): {e}")
        app.state.led_service = led_service

    # ── Slot polling service (hardware sensor auto-assign) ──
    slot_service = SlotPollingService()
    app.state.slot_service = slot_service
    logger.info("Slot polling service initialized (idle, start via API)")

    yield
    logger.info("Shutting down ConsumableShelf backend")
    try:
        await led_service.shutdown()
        logger.info("LED service stopped")
    except Exception as e:
        logger.warning(f"LED service shutdown error: {e}")
    try:
        await slot_service.stop()
        logger.info("Slot polling service stopped")
    except Exception as e:
        logger.warning(f"Slot polling service shutdown error: {e}")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(receipt_router, prefix=settings.API_PREFIX)
app.include_router(issue_router, prefix=settings.API_PREFIX)
app.include_router(inventory_router, prefix=settings.API_PREFIX)
app.include_router(xr_router, prefix=settings.API_PREFIX)
app.include_router(bom_router, prefix=settings.API_PREFIX)
app.include_router(report.router, prefix=settings.API_PREFIX)
app.include_router(shelves_router, prefix=settings.API_PREFIX)
app.include_router(materials_router, prefix=settings.API_PREFIX)
app.include_router(users_router, prefix=settings.API_PREFIX)
app.include_router(settings_router, prefix=settings.API_PREFIX)
app.include_router(customers_router, prefix=settings.API_PREFIX)
app.include_router(hardware_debug_router, prefix=settings.API_PREFIX)
app.include_router(dashboard_router, prefix=settings.API_PREFIX)
app.include_router(shelving_router, prefix=settings.API_PREFIX)
app.include_router(barcode_definition_router, prefix=settings.API_PREFIX)
app.include_router(transactions_router, prefix=settings.API_PREFIX)
app.include_router(backup_router, prefix=settings.API_PREFIX)


@app.get(f"{settings.API_PREFIX}/system/info")
async def get_system_info():
    """Public endpoint: system info (no auth required)."""
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "app_name": settings.APP_NAME,
    }
