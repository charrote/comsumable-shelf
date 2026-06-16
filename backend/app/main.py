"""FastAPI application entry point."""

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.utils.database import init_db
from app.api.auth import router as auth_router
from app.api.receipt import router as receipt_router
from app.api.issue import router as issue_router
from app.api.inventory import router as inventory_router
from app.api.xr import router as xr_router
from app.api.bom import router as bom_router
from app.api import report

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(structlog.stdlib.INFO),
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=False,
)
logger = structlog.get_logger()


async def lifespan(app: FastAPI):
    """Application startup/shutdown."""
    logger.info("Starting up ConsumableShelf backend")
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down ConsumableShelf backend")


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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
    }
