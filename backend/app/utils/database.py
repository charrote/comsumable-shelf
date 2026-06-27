"""Database setup and session management (PostgreSQL async)."""

from typing import AsyncGenerator

from sqlalchemy import text
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
    """Yield a database session.

    The handler is responsible for calling commit() on the session.
    This function only performs a final commit if there is still an
    active transaction (i.e. the handler did NOT already commit).
    """
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            # Only commit if the handler hasn't already committed
            if session.is_active:
                await session.commit()


async def init_db():
    """Initialize database tables and apply migrations."""
    from app.models import Base  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_session: Base.metadata.create_all(
                sync_session, checkfirst=True
            )
        )
        # Migration: add batch_no / date_code columns if not exist
        for table, column, col_type in [
            ("inventory_reels", "batch_no", "VARCHAR(100)"),
            ("inventory_reels", "date_code", "VARCHAR(100)"),
            ("inventory_reels", "reel_code", "VARCHAR(50)"),
            ("receipt_reels", "batch_no", "VARCHAR(100)"),
            ("receipt_reels", "date_code", "VARCHAR(100)"),
        ]:
            await conn.execute(
                text(f"""
                    DO $$ BEGIN
                        ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {col_type};
                    EXCEPTION WHEN duplicate_column THEN NULL;
                    END $$;
                """)
            )
        # Unique index for reel_code
        await conn.execute(
            text("""
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_indexes
                        WHERE tablename = 'inventory_reels' AND indexname = 'ix_inventory_reels_reel_code'
                    ) THEN
                        CREATE UNIQUE INDEX ix_inventory_reels_reel_code ON inventory_reels (reel_code);
                    END IF;
                END $$;
            """)
        )

        # Migration: add barcode_length column to barcode_definitions
        # (if table already exists without this column)
        await conn.execute(
            text("""
                DO $$ BEGIN
                    ALTER TABLE barcode_definitions ADD COLUMN IF NOT EXISTS barcode_length INTEGER NOT NULL DEFAULT 0;
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END $$;
            """)
        )
        # Backfill barcode_length for existing rows where it's still 0
        await conn.execute(
            text("""
                UPDATE barcode_definitions
                SET barcode_length = LENGTH(sample_barcode)
                WHERE barcode_length = 0 OR barcode_length IS NULL;
            """)
        )

        # Migration: add purchase_order_no to receipt table
        await conn.execute(
            text("""
                DO $$ BEGIN
                    ALTER TABLE receipt ADD COLUMN IF NOT EXISTS purchase_order_no VARCHAR(200);
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
            """)
        )

        # Migration: ensure barcode_definition_segments columns are nullable
        # (handle case where table was created with nullable=False in an earlier version)
        column_nullable_migrations = [
            ("barcode_definition_segments", "field_mapping"),
            ("barcode_definition_segments", "field_label"),
        ]
        for table, column in column_nullable_migrations:
            await conn.execute(
                text(f"""
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = '{table}'
                              AND column_name = '{column}'
                              AND is_nullable = 'NO'
                        ) THEN
                            EXECUTE 'ALTER TABLE {table} ALTER COLUMN {column} DROP NOT NULL';
                        END IF;
                END $$;
            """)
            )

        # Migration: add index on inventory_reels.customer_barcode (for duplicate scan check)
        await conn.execute(
            text("""
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_indexes
                        WHERE tablename = 'inventory_reels' AND indexname = 'idx_inv_barcode'
                    ) THEN
                        CREATE INDEX idx_inv_barcode ON inventory_reels (customer_barcode);
                    END IF;
                END $$;
            """)
        )
        # Migration: add index on receipt_reels.barcode (for duplicate scan check)
        await conn.execute(
            text("""
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_indexes
                        WHERE tablename = 'receipt_reels' AND indexname = 'idx_receipt_reel_barcode'
                    ) THEN
                        CREATE INDEX idx_receipt_reel_barcode ON receipt_reels (barcode);
                    END IF;
                END $$;
            """)
        )

        # Migration: create data_backups table if not exists
        await conn.execute(
            text("""
                CREATE TABLE IF NOT EXISTS data_backups (
                    id SERIAL PRIMARY KEY,
                    filename VARCHAR(255) NOT NULL,
                    filepath VARCHAR(1024) NOT NULL,
                    file_size INTEGER DEFAULT 0,
                    db_version VARCHAR(50) DEFAULT '',
                    status VARCHAR(20) DEFAULT 'completed',
                    error_message TEXT DEFAULT '',
                    operator VARCHAR(100) DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        )

        # Migration: create led_commands table if not exists
        await conn.execute(
            text("""
                CREATE TABLE IF NOT EXISTS led_commands (
                    id SERIAL PRIMARY KEY,
                    issue_order_id INTEGER REFERENCES issue_order(id),
                    material_id INTEGER NOT NULL,
                    shelf_id INTEGER NOT NULL REFERENCES shelves(id),
                    slot_id INTEGER NOT NULL REFERENCES shelf_slots(id),
                    color VARCHAR(20) DEFAULT 'green',
                    duration INTEGER DEFAULT 5,
                    status VARCHAR(20) DEFAULT 'queued',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sent_at TIMESTAMP,
                    cleared_at TIMESTAMP
                );
            """)
        )
        await conn.execute(
            text("""
                CREATE INDEX IF NOT EXISTS idx_led_status ON led_commands (status, created_at);
            """)
        )

        # ════════════════════════════════════════════════════════════════
        # 新料架 Schema 迁移（code + side + slot_on_board → cell_id）
        # ════════════════════════════════════════════════════════════════

        # -- shelf_slots 表：添加 code / name --
        for col, col_type in [
            ("code", "VARCHAR(64)"),
            ("name", "VARCHAR(128)"),
        ]:
            await conn.execute(text(f"""
                DO $$ BEGIN
                    ALTER TABLE shelf_slots ADD COLUMN IF NOT EXISTS {col} {col_type};
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
            """))

        # -- led_commands 表新增字段（保留） --
        for col, col_type in [
            ("is_blink", "BOOLEAN DEFAULT FALSE"),
            ("turn_on_time", "INTEGER DEFAULT 0"),
            ("voice_text", "VARCHAR(255)"),
        ]:
            await conn.execute(text(f"""
                DO $$ BEGIN
                    ALTER TABLE led_commands ADD COLUMN IF NOT EXISTS {col} {col_type};
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
            """))

        # -- shelf_slot_events 表新增字段（保留） --
        for col, col_type in [
            ("cell_id", "VARCHAR(32)"),
            ("raw_data", "TEXT"),
        ]:
            await conn.execute(text(f"""
                DO $$ BEGIN
                    ALTER TABLE shelf_slot_events ADD COLUMN IF NOT EXISTS {col} {col_type};
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
            """))

        # -- cell_id 唯一索引 --
        await conn.execute(text("""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE tablename = 'shelf_slots' AND indexname = 'ix_shelf_slots_cell_id'
                ) THEN
                    CREATE UNIQUE INDEX ix_shelf_slots_cell_id
                    ON shelf_slots (cell_id) WHERE cell_id IS NOT NULL;
                END IF;
            END $$;
        """))

        # -- Migration: add assigned_color to issue_order --
        try:
            await conn.execute(text(
                "ALTER TABLE issue_order ADD COLUMN assigned_color VARCHAR(50)"
            ))
        except Exception:
            # Column might already exist (PostgreSQL: use IF NOT EXISTS)
            try:
                await conn.execute(text("""
                    DO $$ BEGIN
                        ALTER TABLE issue_order ADD COLUMN IF NOT EXISTS assigned_color VARCHAR(50);
                    EXCEPTION WHEN duplicate_column THEN NULL;
                    END $$;
                """))
            except Exception:
                pass  # Column already exists, ignore


async def seed_db():
    """Seed default data (admin user, default customer, system settings)."""
    from app.models import User, SystemSetting, Customer
    from app.services.auth_service import get_password_hash
    from sqlalchemy import select

    async with async_session() as session:
        # ====================================================================
        # 1. Admin user
        # ====================================================================
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

        # ====================================================================
        # 2. Default customer
        # ====================================================================
        result = await session.execute(
            select(Customer).where(Customer.code == "DEFAULT")
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            customer = Customer(
                name="默认客户",
                code="DEFAULT",
                contact_name="管理员",
                active=1,
            )
            session.add(customer)
            await session.flush()
        else:
            session.expunge(customer)

        # ====================================================================
        # 3. System settings
        # ====================================================================
        default_settings = [
            {
                "key": "fifo_strategy",
                "value": settings.FIFO_STRATEGY,
                "description": "FIFO 出库策略 (tail_first | time_fifo | mixed)",
            },
            {
                "key": "duplicate_scan_behavior",
                "value": "force",
                "description": "重复扫码行为 (block=拦截 | warn=警告并放行 | force=不检查)",
            },
            {
                "key": "default_slot_capacity",
                "value": "",
                "description": "全局默认储位容量（空=不限制；各储位可单独覆盖）",
            },
            {
                "key": "rack_api_base_url",
                "value": "",
                "description": "智能料架服务器地址（如 http://192.168.1.200:8080）",
            },
            {
                "key": "rack_api_user_id",
                "value": "",
                "description": "智能料架 API 用户（全局默认，可被料架级配置覆盖）",
            },
            {
                "key": "rack_api_client_id",
                "value": "",
                "description": "智能料架 API 终端设备 ID（全局默认，可被料架级配置覆盖）",
            },
            {
                "key": "picking_task_colors",
                "value": '["red","green","yellow","blue"]',
                "description": "储位灯任务颜色配置（JSON数组，仅勾选的颜色可用于发料单亮灯任务）",
            },
        ]
        for s in default_settings:
            existing = await session.execute(
                select(SystemSetting).where(SystemSetting.key == s["key"])
            )
            if existing.scalar_one_or_none() is None:
                session.add(SystemSetting(**s))

        await session.commit()
