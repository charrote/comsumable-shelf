"""Database setup and session management (PostgreSQL async)."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600,
    echo=False,
)

async_session = async_sessionmaker(engine, expire_on_commit=False)
async_session_factory = async_session  # alias for external use


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Initialize database tables."""
    from app.models import Base  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_session: Base.metadata.create_all(
                sync_session, checkfirst=True
            )
        )


async def seed_db():
    """Seed default data (admin user, default customer, sample mapping, system settings)."""
    from app.models import User, SystemSetting, Customer, MaterialMaster, CustomerMaterialMapping
    from app.services.auth_service import get_password_hash
    from sqlalchemy import select

    async with async_session() as session:
        # --- Admin user ---
        result = await session.execute(
            select(User).where(User.username == "admin")
        )
        if result.scalar_one_or_none() is None:
            admin = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                role="admin",
                active=1,
            )
            session.add(admin)

        # --- Default customer ---
        result = await session.execute(
            select(Customer).where(Customer.code == "DEFAULT")
        )
        if result.scalar_one_or_none() is None:
            customer = Customer(
                name="默认客户",
                code="DEFAULT",
                contact_name="管理员",
                active=1,
            )
            session.add(customer)
            await session.flush()  # get customer.id

            # Default material (so mapping seed has a target)
            mat = MaterialMaster(
                customer_id=customer.id,
                code="RES-0001",
                name="电阻 0805 10KΩ",
                unit="盘",
                active=1,
            )
            session.add(mat)
            await session.flush()

            # Sample mapping
            mapping = CustomerMaterialMapping(
                customer_id=customer.id,
                customer_material_code="CUST-RES-0001",
                internal_material_id=mat.id,
                active=1,
            )
            session.add(mapping)

        # --- Default system settings ---
        default_settings = [
            {
                "key": "fifo_strategy",
                "value": settings.FIFO_STRATEGY,
                "description": "FIFO 出库策略 (tail_first | time_fifo | mixed)",
            },
            {
                "key": "duplicate_scan_behavior",
                "value": "block",
                "description": "重复扫码行为 (block=拦截 | warn=警告并放行 | force=不检查)",
            },
            {
                "key": "default_slot_capacity",
                "value": "",
                "description": "全局默认储位容量（空=不限制；各储位可单独覆盖）",
            },
        ]
        for s in default_settings:
            existing = await session.execute(
                select(SystemSetting).where(SystemSetting.key == s["key"])
            )
            if existing.scalar_one_or_none() is None:
                session.add(SystemSetting(**s))

        await session.commit()
