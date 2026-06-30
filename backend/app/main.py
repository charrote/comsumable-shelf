"""FastAPI application entry point."""

import sys
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
from app.api.suppliers import router as suppliers_router

from app.api.dashboard import router as dashboard_router
from app.api.shelving import router as shelving_router
from app.api.barcode_definition import router as barcode_definition_router
from app.api.transactions import router as transactions_router
from app.api.backup import router as backup_router
from app.api.rack_callback import router as rack_callback_router
from app.api.ws import router as ws_router
from app.api.light_debug import router as light_debug_router
from app.api.app_version import router as app_version_router
from app.api.changelog import router as changelog_router
from app.api.roles import router as roles_router
from app.services.led_service import LedService
from app.services.rack_slot_poller import RackSlotPoller

_log_handler = logging.StreamHandler(sys.stderr)
_log_handler.setLevel(logging.INFO)
_log_handler.setFormatter(logging.Formatter("%(message)s"))
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(_log_handler)

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
    if settings.DB_AUTO_MIGRATE:
        try:
            await init_db()
            logger.info("Schema migration completed")
        except Exception as e:
            logger.error(f"Schema migration failed: {e}")
            logger.warning("Continuing startup — seed_db will attempt to run anyway")
    try:
        await seed_db()
    except Exception as e:
        logger.error(f"Seed data failed (tables may not exist yet): {e}")
    logger.info("Database initialized")

    # ── LED service ──
    led_service = LedService()
    try:
        await led_service.init()
        app.state.led_service = led_service
        logger.info("LED service started (HTTP API mode)")
    except Exception as e:
        logger.warning(f"LED service init failed: {e}")
        app.state.led_service = led_service

    # ── RackSlotPoller (智能料架 HTTP 轮询) ──
    rack_poller = RackSlotPoller()
    app.state.rack_poller = rack_poller
    try:
        await rack_poller.start()
        logger.info("RackSlotPoller started (HTTP polling for smart shelves)")
    except Exception as e:
        logger.warning(f"RackSlotPoller start failed: {e}")

    yield
    logger.info("Shutting down ConsumableShelf backend")
    try:
        await led_service.shutdown()
        logger.info("LED service stopped")
    except Exception as e:
        logger.warning(f"LED service shutdown error: {e}")
    try:
        await rack_poller.stop()
        logger.info("RackSlotPoller stopped")
    except Exception as e:
        logger.warning(f"RackSlotPoller stop error: {e}")


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
app.include_router(suppliers_router, prefix=settings.API_PREFIX)
app.include_router(dashboard_router, prefix=settings.API_PREFIX)
app.include_router(shelving_router, prefix=settings.API_PREFIX)
app.include_router(barcode_definition_router, prefix=settings.API_PREFIX)
app.include_router(transactions_router, prefix=settings.API_PREFIX)
app.include_router(backup_router, prefix=settings.API_PREFIX)
app.include_router(rack_callback_router, prefix=settings.API_PREFIX)
app.include_router(light_debug_router, prefix=settings.API_PREFIX)
app.include_router(app_version_router, prefix=settings.API_PREFIX)
app.include_router(changelog_router, prefix=settings.API_PREFIX)
app.include_router(roles_router, prefix=settings.API_PREFIX)
app.include_router(ws_router)  # WebSocket 无 prefix


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
