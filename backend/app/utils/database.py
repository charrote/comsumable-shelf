"""Database setup and session management (PostgreSQL async)."""

from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
import structlog

logger = structlog.get_logger()

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


async def _create_tables():
    """Phase 1: create all ORM tables in a separate, immediately-committed transaction.

    This prevents migration failures from rolling back the table creation.
    """
    from app.models import Base  # noqa: F401

    async with engine.begin() as conn:
        # ── Cleanup broken table state from previous failed runs ──
        await conn.execute(text("""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'suppliers' AND relkind = 'r')
                   AND NOT EXISTS (
                       SELECT 1 FROM pg_depend d
                       JOIN pg_class c ON c.oid = d.objid
                       WHERE d.refobjid = (
                           SELECT oid FROM pg_class WHERE relname = 'suppliers' AND relkind = 'r'
                       ) AND c.relname = 'suppliers_id_seq'
                   )
                THEN
                    DROP TABLE IF EXISTS suppliers CASCADE;
                END IF;
            END $$;
        """))

        # Cleanup orphaned composite types
        await conn.execute(text("""
            DO $$ DECLARE
                rec RECORD;
            BEGIN
                FOR rec IN
                    SELECT t.typname
                    FROM pg_type t
                    WHERE t.typtype = 'c'
                      AND t.typnamespace = (
                          SELECT oid FROM pg_namespace WHERE nspname = 'public'
                      )
                      AND NOT EXISTS (
                          SELECT 1 FROM pg_class c
                          WHERE c.relname = t.typname AND c.relkind = 'r'
                      )
                LOOP
                    EXECUTE 'DROP TYPE IF EXISTS ' || quote_ident(rec.typname) || ' CASCADE';
                END LOOP;
            END $$;
        """))

        await conn.run_sync(
            lambda sync_session: Base.metadata.create_all(
                sync_session, checkfirst=True
            )
        )

        # Safety check: force-create core tables if missing
        core_tables = ["users", "customers", "material_master"]
        for tbl in core_tables:
            result = await conn.execute(
                text(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{tbl}')")
            )
            if not result.scalar():
                logger.warning(f"Core table '{tbl}' missing after create_all — force-creating")
                await conn.run_sync(
                    lambda sync_session: Base.metadata.create_all(
                        sync_session, checkfirst=False, tables=[Base.metadata.tables[tbl]]
                    )
                )


_LOCK_ID = 42_000_101  # arbitrary advisory lock ID for DB init


async def init_db():
    """Initialize database tables and apply migrations.

    Uses a PostgreSQL advisory lock so that only one uvicorn worker
    performs DDL — the others skip.  The lock is released when the
    transaction commits.

    Split into two separate transactions so that table creation is
    committed before migrations run — a migration failure won't
    roll back the just-created tables.
    """
    # Try to acquire an advisory lock (non-blocking).
    # Only the first worker proceeds; others skip init entirely.
    async with engine.begin() as conn:
        acquired = await conn.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": _LOCK_ID},
        )
        if not acquired.scalar():
            logger.info("DB init lock held by another worker — skipping")
            return

    try:
        logger.info("Acquired DB init lock — creating tables")
        await _create_tables()
    except Exception:
        logger.exception("Table creation failed")
        raise
    try:
        logger.info("Running schema migrations")
        await _run_migrations()
    except Exception:
        logger.exception("Schema migrations failed (tables already created)")
    finally:
        # Release the advisory lock
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": _LOCK_ID},
            )


async def _run_migrations():
    """Phase 2: run schema migrations in a separate transaction.

    Each migration is wrapped in DO $$ … EXCEPTION … END $$ so individual
    steps can fail without aborting the whole batch.
    """
    async with engine.begin() as conn:

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

        # -- shelf_slots 表：添加 cell_id --
        await conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE shelf_slots ADD COLUMN IF NOT EXISTS cell_id VARCHAR(32);
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

        # -- Migration: add defaults for modbus-related NOT NULL columns --
        for col in ["board_address", "global_index", "modbus_tcp_id", "modbus_coil_base"]:
            await conn.execute(text(f"""
                DO $$ BEGIN
                    ALTER TABLE shelf_slots ALTER COLUMN {col} SET DEFAULT 0;
                EXCEPTION WHEN undefined_column THEN NULL;
                END $$;
            """))

        # -- Migration: add assigned_color to issue_order --
        # NOTE: Must use DO $$ ... $$ block with IF NOT EXISTS from the start,
        # because a bare ALTER TABLE that fails will abort the entire transaction,
        # causing all subsequent migrations to fail with InFailedSQLTransactionError.
        await conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE issue_order ADD COLUMN IF NOT EXISTS assigned_color VARCHAR(50);
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$;
        """))

        # Migration: add supplier_code to material_master
        await conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE material_master ADD COLUMN IF NOT EXISTS supplier_code VARCHAR(100);
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$;
        """))

        # -- Drop side column and unique constraint from shelf_slots --
        await conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE shelf_slots DROP CONSTRAINT IF EXISTS uq_slot_pos;
            EXCEPTION WHEN undefined_object THEN NULL;
            END $$;
        """))
        await conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE shelf_slots DROP COLUMN IF EXISTS side;
            EXCEPTION WHEN undefined_column THEN NULL;
            END $$;
        """))

        # ════════════════════════════════════════════════════════════════
        # 角色权限系统迁移 — roles, permissions, role_permissions 表由
        # Base.metadata.create_all() 自动创建，这里只迁移 users.role_id
        # ════════════════════════════════════════════════════════════════

        # Add role_id to users table (FK to roles)
        await conn.execute(
            text("""
                DO $$ BEGIN
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS role_id INTEGER REFERENCES roles(id);
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
            """)
        )

        # ════════════════════════════════════════════════════════════════
        # PDA 版本更新日志表
        # ════════════════════════════════════════════════════════════════
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS app_changelog (
                id SERIAL PRIMARY KEY,
                version VARCHAR(50) NOT NULL,
                notes TEXT NOT NULL,
                date VARCHAR(20) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_app_changelog_version
            ON app_changelog (version);
        """))

        # Seed existing data from CHANGELOG.md if table is empty
        result = await conn.execute(text("SELECT COUNT(*) FROM app_changelog"))
        count = result.scalar()
        if count == 0:
            import re
            from pathlib import Path

            from pathlib import Path
            changelog_path = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
            if changelog_path.exists():
                content = changelog_path.read_text(encoding="utf-8")
                sections = re.split(r'\n\s*---\s*\n', content)
                inserted = 0
                for section in sections:
                    lines = section.strip().split('\n')
                    title_line = next((l for l in lines if re.match(r'^##\s+v', l)), None)
                    if not title_line:
                        continue
                    title = re.sub(r'^##\s+', '', title_line).strip()
                    match = re.match(r'^v?([\d.]+)\s*[（(]([^）)]+)[）)]', title)
                    if not match:
                        continue
                    version = match.group(1)
                    date_str = match.group(2)
                    items = [
                        re.sub(r'^\s*[-*]\s', '', l).strip()
                        for l in lines if re.match(r'^\s*[-*]\s', l)
                    ]
                    notes = "\n".join(f"- {item}" for item in items) if items else ""
                    if version and notes:
                        await conn.execute(
                            text("""
                                INSERT INTO app_changelog (version, notes, date)
                                VALUES (:version, :notes, :date)
                            """),
                            {"version": version, "notes": notes, "date": date_str}
                        )
                        inserted += 1
                if inserted:
                    logger.info(f"从 CHANGELOG.md 导入 {inserted} 条版本记录")
                else:
                    logger.info("CHANGELOG.md 存在但无有效记录")

        # Note: suppliers table is auto-created by Base.metadata.create_all()
        # via the Supplier model, so no raw CREATE TABLE is needed here.


async def seed_db():
    """Seed default data (admin user, default customer, system settings, roles & permissions).

    Thread-safe for concurrent uvicorn workers:
    - Uses INSERT … ON CONFLICT DO NOTHING to avoid duplicate-key errors
    - Advisory lock ensures only one worker seeds (others skip)
    """
    # Only one worker should seed — others skip
    async with engine.begin() as conn:
        acquired = await conn.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": _LOCK_ID},
        )
        if not acquired.scalar():
            logger.info("seed_db lock held by another worker — skipping")
            return

    try:
        from app.models import User, SystemSetting, Customer, Role, Permission, RolePermission
        from app.services.auth_service import get_password_hash
        from sqlalchemy import select, text as sa_text
        from sqlalchemy.exc import IntegrityError

        async with async_session() as session:
            # ====================================================================
            # 1. Permissions
            # ====================================================================
            all_permissions = [
                {"code": "dashboard:read", "name": "查看仪表盘", "module": "dashboard"},
                {"code": "material:read", "name": "查看物料", "module": "material"},
                {"code": "material:create", "name": "新建物料", "module": "material"},
                {"code": "material:update", "name": "编辑物料", "module": "material"},
                {"code": "material:delete", "name": "删除物料", "module": "material"},
                {"code": "material:import", "name": "导入物料", "module": "material"},
                {"code": "material:mapping", "name": "物料映射管理", "module": "material"},
                {"code": "shelf:read", "name": "查看料架", "module": "shelf"},
                {"code": "shelf:create", "name": "新建料架", "module": "shelf"},
                {"code": "shelf:update", "name": "编辑料架", "module": "shelf"},
                {"code": "shelf:delete", "name": "删除料架", "module": "shelf"},
                {"code": "inventory:read", "name": "查看库存", "module": "inventory"},
                {"code": "inventory:update", "name": "编辑库存", "module": "inventory"},
                {"code": "inventory:export", "name": "导出库存", "module": "inventory"},
                {"code": "inventory:direct-out", "name": "直接出库", "module": "inventory"},
                {"code": "receipt:read", "name": "查看入库单", "module": "receipt"},
                {"code": "receipt:create", "name": "新建入库单", "module": "receipt"},
                {"code": "receipt:update", "name": "编辑入库单", "module": "receipt"},
                {"code": "receipt:delete", "name": "删除入库单", "module": "receipt"},
                {"code": "receipt:scan", "name": "扫码入库", "module": "receipt"},
                {"code": "receipt:manual-entry", "name": "手工录入", "module": "receipt"},
                {"code": "issue:read", "name": "查看发料单", "module": "issue"},
                {"code": "issue:create", "name": "新建发料单", "module": "issue"},
                {"code": "issue:update", "name": "编辑发料单", "module": "issue"},
                {"code": "issue:delete", "name": "删除发料单", "module": "issue"},
                {"code": "issue:assign", "name": "分配亮灯", "module": "issue"},
                {"code": "issue:pick", "name": "确认捡料", "module": "issue"},
                {"code": "xr:read", "name": "查看点料机", "module": "xr"},
                {"code": "xr:upload", "name": "上传点料数据", "module": "xr"},
                {"code": "xr:match", "name": "匹配料盘", "module": "xr"},
                {"code": "bom:read", "name": "查看BOM", "module": "bom"},
                {"code": "bom:create", "name": "新建BOM", "module": "bom"},
                {"code": "bom:update", "name": "编辑BOM", "module": "bom"},
                {"code": "bom:delete", "name": "删除BOM", "module": "bom"},
                {"code": "bom:import", "name": "导入BOM", "module": "bom"},
                {"code": "bom:export", "name": "导出BOM", "module": "bom"},
                {"code": "report:read", "name": "查看报表", "module": "report"},
                {"code": "settings:read", "name": "查看设置", "module": "settings"},
                {"code": "settings:update", "name": "编辑设置", "module": "settings"},
                {"code": "barcode:read", "name": "查看条码定义", "module": "barcode"},
                {"code": "barcode:create", "name": "新建条码定义", "module": "barcode"},
                {"code": "barcode:update", "name": "编辑条码定义", "module": "barcode"},
                {"code": "barcode:delete", "name": "删除条码定义", "module": "barcode"},
                {"code": "user:read", "name": "查看用户", "module": "user"},
                {"code": "user:create", "name": "新建用户", "module": "user"},
                {"code": "user:update", "name": "编辑用户", "module": "user"},
                {"code": "user:delete", "name": "删除用户", "module": "user"},
                {"code": "customer:read", "name": "查看客户", "module": "customer"},
                {"code": "customer:create", "name": "新建客户", "module": "customer"},
                {"code": "customer:update", "name": "编辑客户", "module": "customer"},
                {"code": "customer:delete", "name": "删除客户", "module": "customer"},
                {"code": "supplier:read", "name": "查看供应商", "module": "supplier"},
                {"code": "supplier:create", "name": "新建供应商", "module": "supplier"},
                {"code": "supplier:update", "name": "编辑供应商", "module": "supplier"},
                {"code": "supplier:delete", "name": "删除供应商", "module": "supplier"},
                {"code": "supplier:import", "name": "导入供应商", "module": "supplier"},
                {"code": "app-download:read", "name": "查看PDA下载", "module": "app-download"},
                {"code": "app-version:read", "name": "查看APP版本", "module": "app-version"},
                {"code": "app-version:update", "name": "更新APP版本", "module": "app-version"},
                {"code": "backup:read", "name": "查看备份", "module": "backup"},
                {"code": "backup:create", "name": "创建备份", "module": "backup"},
                {"code": "backup:restore", "name": "恢复备份", "module": "backup"},
                {"code": "backup:delete", "name": "删除备份", "module": "backup"},
                {"code": "light-debug:read", "name": "查看灯控调试", "module": "light-debug"},
                {"code": "light-debug:control", "name": "灯控调试操作", "module": "light-debug"},
                {"code": "role:read", "name": "查看角色", "module": "role"},
                {"code": "role:create", "name": "新建角色", "module": "role"},
                {"code": "role:update", "name": "编辑角色", "module": "role"},
                {"code": "role:delete", "name": "删除角色", "module": "role"},
                {"code": "permission:read", "name": "查看权限", "module": "permission"},
            ]

            # Insert permissions — use ON CONFLICT for concurrent safety
            permission_map = {}
            for p_def in all_permissions:
                try:
                    await session.execute(
                        sa_text("""
                            INSERT INTO permissions (code, name, module, description, created_at)
                            VALUES (:code, :name, :module, :description, NOW())
                            ON CONFLICT (code) DO NOTHING
                        """),
                        {"code": p_def["code"], "name": p_def["name"],
                         "module": p_def["module"], "description": p_def["name"]},
                    )
                except IntegrityError:
                    await session.rollback()
                existing = await session.execute(
                    select(Permission).where(Permission.code == p_def["code"])
                )
                perm = existing.scalar_one_or_none()
                permission_map[p_def["code"]] = perm.id if perm else None

            # ====================================================================
            # 2. Default Roles
            # ====================================================================
            admin_permissions = [p["code"] for p in all_permissions]
            supervisor_permissions = [
                "dashboard:read", "material:read", "material:create", "material:update",
                "shelf:read", "shelf:create", "shelf:update",
                "inventory:read", "inventory:update", "inventory:export", "inventory:direct-out",
                "receipt:read", "receipt:create", "receipt:scan", "receipt:manual-entry",
                "issue:read", "issue:create", "issue:update", "issue:assign", "issue:pick",
                "xr:read", "xr:upload", "xr:match",
                "bom:read", "bom:create", "bom:update", "report:read",
                "settings:read", "barcode:read", "customer:read",
                "supplier:read", "supplier:create", "supplier:update",
                "user:read", "role:read", "permission:read", "app-download:read", "backup:read",
            ]
            operator_permissions = [
                "dashboard:read", "material:read", "shelf:read",
                "inventory:read", "inventory:update", "inventory:export",
                "receipt:read", "receipt:create", "receipt:scan", "receipt:manual-entry",
                "issue:read", "issue:create", "issue:update", "issue:assign", "issue:pick",
                "xr:read", "xr:upload", "xr:match", "bom:read", "report:read",
            ]
            readonly_permissions = [
                "dashboard:read", "material:read", "shelf:read", "inventory:read",
                "receipt:read", "issue:read", "xr:read", "bom:read", "report:read",
                "customer:read", "supplier:read", "settings:read", "barcode:read",
                "app-download:read", "backup:read",
            ]
            role_defs = [
                {"name": "管理员", "code": "admin", "description": "系统管理员，拥有全部权限",
                 "is_system": 1, "perms": admin_permissions},
                {"name": "主管", "code": "supervisor", "description": "主管，拥有大部分管理和操作权限",
                 "is_system": 1, "perms": supervisor_permissions},
                {"name": "操作员", "code": "operator", "description": "操作员，拥有日常操作所需权限",
                 "is_system": 1, "perms": operator_permissions},
                {"name": "只读用户", "code": "readonly", "description": "只读用户，仅可查看数据",
                 "is_system": 1, "perms": readonly_permissions},
            ]

            role_id_map = {}
            for rd in role_defs:
                try:
                    await session.execute(
                        sa_text("""
                            INSERT INTO roles (name, code, description, is_system, active, created_at, updated_at)
                            VALUES (:name, :code, :description, :is_system, 1, NOW(), NOW())
                            ON CONFLICT (code) DO NOTHING
                        """),
                        {"name": rd["name"], "code": rd["code"],
                         "description": rd["description"], "is_system": rd["is_system"]},
                    )
                except IntegrityError:
                    await session.rollback()
                existing = await session.execute(
                    select(Role).where(Role.code == rd["code"])
                )
                role = existing.scalar_one_or_none()
                role_id_map[rd["code"]] = role.id if role else None

                if role:
                    existing_rp = await session.execute(
                        select(RolePermission).where(RolePermission.role_id == role.id).limit(1)
                    )
                    if existing_rp.scalar_one_or_none() is None:
                        for perm_code in rd["perms"]:
                            perm_id = permission_map.get(perm_code)
                            if perm_id:
                                session.add(RolePermission(role_id=role.id, permission_id=perm_id))

            # ====================================================================
            # 3. Admin user
            # ====================================================================
            try:
                await session.execute(
                    sa_text("""
                        INSERT INTO users (username, password_hash, role, role_id, active, created_at)
                        VALUES (:username, :pwd, :role, :role_id, 1, NOW())
                        ON CONFLICT (username) DO NOTHING
                    """),
                    {"username": "admin", "pwd": get_password_hash("admin123"),
                     "role": "admin", "role_id": role_id_map.get("admin")},
                )
            except IntegrityError:
                await session.rollback()
            else:
                await session.execute(
                    sa_text("UPDATE users SET role_id = :role_id WHERE username = 'admin' AND role_id IS NULL"),
                    {"role_id": role_id_map.get("admin")},
                )

            # ====================================================================
            # 4. Default customer
            # ====================================================================
            try:
                await session.execute(
                    sa_text("""
                        INSERT INTO customers (name, code, contact_name, active, created_at, updated_at)
                        VALUES (:name, :code, :contact, 1, NOW(), NOW())
                        ON CONFLICT (code) DO NOTHING
                    """),
                    {"name": "默认客户", "code": "DEFAULT", "contact": "管理员"},
                )
            except IntegrityError:
                await session.rollback()

            # ====================================================================
            # 5. System settings
            # ====================================================================
            default_settings = [
                {"key": "fifo_strategy", "value": settings.FIFO_STRATEGY,
                 "description": "FIFO 出库策略 (tail_first | time_fifo | mixed)"},
                {"key": "duplicate_scan_behavior", "value": "force",
                 "description": "重复扫码行为 (block=拦截 | warn=警告并放行 | force=不检查)"},
                {"key": "default_slot_capacity", "value": "",
                 "description": "全局默认储位容量（空=不限制；各储位可单独覆盖）"},
                {"key": "rack_api_base_url", "value": "",
                 "description": "智能料架服务器地址（如 http://192.168.1.200:8080）"},
                {"key": "rack_api_user_id", "value": "",
                 "description": "智能料架 API 用户（全局默认，可被料架级配置覆盖）"},
                {"key": "rack_api_client_id", "value": "",
                 "description": "智能料架 API 终端设备 ID（全局默认，可被料架级配置覆盖）"},
                {"key": "picking_task_colors", "value": '["red","green","yellow","blue"]',
                 "description": "储位灯任务颜色配置（JSON数组）"},
                {"key": "app_latest_version", "value": "3.0.0",
                 "description": "PDA App 最新版本号"},
                {"key": "app_min_version", "value": "3.0.0",
                 "description": "PDA App 最低兼容版本号"},
                {"key": "app_download_url", "value": "",
                 "description": "PDA App APK 下载地址"},
                {"key": "app_release_notes", "value": "",
                 "description": "PDA App 更新说明"},
            ]
            for s in default_settings:
                try:
                    await session.execute(
                        sa_text("""
                            INSERT INTO system_settings (key, value, description, updated_at)
                            VALUES (:key, :value, :description, NOW())
                            ON CONFLICT (key) DO NOTHING
                        """),
                        s,
                    )
                except IntegrityError:
                    await session.rollback()

            await session.commit()
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": _LOCK_ID},
            )
