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


async def init_db():
    """Initialize database tables and apply migrations."""
    from app.models import Base  # noqa: F401

    async with engine.begin() as conn:
        # ── Cleanup broken table state from previous failed runs ──
        # DDL rollback in PostgreSQL removes tables but NOT sequences.
        # A previous init_db() that failed mid-transaction could leave the
        # `suppliers` table in a broken state (exists but missing the default
        # sequence on the id column).  Detect this and drop the broken table
        # so create_all() can rebuild it correctly.
        # This is a no-op on a healthy database or a clean install.
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

        # Cleanup orphaned composite types from failed DDL transactions.
        # PostgreSQL creates a composite type in pg_type when a table is created.
        # If create_all() fails mid-transaction, the type may remain orphaned
        # (table doesn't exist) and block future create_all() calls.
        for tbl in ["reel_reservations", "led_commands", "data_backups"]:
            await conn.execute(text(f"""
                DO $$ BEGIN
                    IF NOT EXISTS (SELECT FROM pg_class WHERE relname = '{tbl}' AND relkind = 'r')
                       AND EXISTS (SELECT 1 FROM pg_type WHERE typname = '{tbl}')
                    THEN
                        DROP TYPE IF EXISTS {tbl} CASCADE;
                    END IF;
                END $$;
            """))

        await conn.run_sync(
            lambda sync_session: Base.metadata.create_all(
                sync_session, checkfirst=True
            )
        )

        # ── Safety check: verify core tables actually exist ──
        # (handle stale volumes where checkfirst=True incorrectly skips creation)
        core_tables = ["users", "customers", "material_master"]
        for tbl in core_tables:
            result = await conn.execute(
                text(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{tbl}')")
            )
            if not result.scalar():
                logger.warning(f"Core table '{tbl}' missing after create_all — force-creating")
                # Re-run create_all without checkfirst for this specific case
                await conn.run_sync(
                    lambda sync_session: Base.metadata.create_all(
                        sync_session, checkfirst=False, tables=[Base.metadata.tables[tbl]]
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

        # Note: suppliers table is auto-created by Base.metadata.create_all()
        # via the Supplier model, so no raw CREATE TABLE is needed here.


async def seed_db():
    """Seed default data (admin user, default customer, system settings, roles & permissions)."""
    from app.models import User, SystemSetting, Customer, Role, Permission, RolePermission
    from app.services.auth_service import get_password_hash
    from sqlalchemy import select

    async with async_session() as session:
        # ====================================================================
        # 1. Permissions
        # ====================================================================
        all_permissions = [
            # Dashboard
            {"code": "dashboard:read", "name": "查看仪表盘", "module": "dashboard"},
            # Material
            {"code": "material:read", "name": "查看物料", "module": "material"},
            {"code": "material:create", "name": "新建物料", "module": "material"},
            {"code": "material:update", "name": "编辑物料", "module": "material"},
            {"code": "material:delete", "name": "删除物料", "module": "material"},
            {"code": "material:import", "name": "导入物料", "module": "material"},
            {"code": "material:mapping", "name": "物料映射管理", "module": "material"},
            # Shelf
            {"code": "shelf:read", "name": "查看料架", "module": "shelf"},
            {"code": "shelf:create", "name": "新建料架", "module": "shelf"},
            {"code": "shelf:update", "name": "编辑料架", "module": "shelf"},
            {"code": "shelf:delete", "name": "删除料架", "module": "shelf"},
            # Inventory
            {"code": "inventory:read", "name": "查看库存", "module": "inventory"},
            {"code": "inventory:update", "name": "编辑库存", "module": "inventory"},
            {"code": "inventory:export", "name": "导出库存", "module": "inventory"},
            {"code": "inventory:direct-out", "name": "直接出库", "module": "inventory"},
            # Receipt
            {"code": "receipt:read", "name": "查看入库单", "module": "receipt"},
            {"code": "receipt:create", "name": "新建入库单", "module": "receipt"},
            {"code": "receipt:update", "name": "编辑入库单", "module": "receipt"},
            {"code": "receipt:delete", "name": "删除入库单", "module": "receipt"},
            {"code": "receipt:scan", "name": "扫码入库", "module": "receipt"},
            {"code": "receipt:manual-entry", "name": "手工录入", "module": "receipt"},
            # Issue
            {"code": "issue:read", "name": "查看发料单", "module": "issue"},
            {"code": "issue:create", "name": "新建发料单", "module": "issue"},
            {"code": "issue:update", "name": "编辑发料单", "module": "issue"},
            {"code": "issue:delete", "name": "删除发料单", "module": "issue"},
            {"code": "issue:assign", "name": "分配亮灯", "module": "issue"},
            {"code": "issue:pick", "name": "确认捡料", "module": "issue"},
            # XR
            {"code": "xr:read", "name": "查看点料机", "module": "xr"},
            {"code": "xr:upload", "name": "上传点料数据", "module": "xr"},
            {"code": "xr:match", "name": "匹配料盘", "module": "xr"},
            # BOM
            {"code": "bom:read", "name": "查看BOM", "module": "bom"},
            {"code": "bom:create", "name": "新建BOM", "module": "bom"},
            {"code": "bom:update", "name": "编辑BOM", "module": "bom"},
            {"code": "bom:delete", "name": "删除BOM", "module": "bom"},
            {"code": "bom:import", "name": "导入BOM", "module": "bom"},
            {"code": "bom:export", "name": "导出BOM", "module": "bom"},
            # Report
            {"code": "report:read", "name": "查看报表", "module": "report"},
            # Settings
            {"code": "settings:read", "name": "查看设置", "module": "settings"},
            {"code": "settings:update", "name": "编辑设置", "module": "settings"},
            # Barcode
            {"code": "barcode:read", "name": "查看条码定义", "module": "barcode"},
            {"code": "barcode:create", "name": "新建条码定义", "module": "barcode"},
            {"code": "barcode:update", "name": "编辑条码定义", "module": "barcode"},
            {"code": "barcode:delete", "name": "删除条码定义", "module": "barcode"},
            # User
            {"code": "user:read", "name": "查看用户", "module": "user"},
            {"code": "user:create", "name": "新建用户", "module": "user"},
            {"code": "user:update", "name": "编辑用户", "module": "user"},
            {"code": "user:delete", "name": "删除用户", "module": "user"},
            # Customer
            {"code": "customer:read", "name": "查看客户", "module": "customer"},
            {"code": "customer:create", "name": "新建客户", "module": "customer"},
            {"code": "customer:update", "name": "编辑客户", "module": "customer"},
            {"code": "customer:delete", "name": "删除客户", "module": "customer"},
            # Supplier
            {"code": "supplier:read", "name": "查看供应商", "module": "supplier"},
            {"code": "supplier:create", "name": "新建供应商", "module": "supplier"},
            {"code": "supplier:update", "name": "编辑供应商", "module": "supplier"},
            {"code": "supplier:delete", "name": "删除供应商", "module": "supplier"},
            {"code": "supplier:import", "name": "导入供应商", "module": "supplier"},
            # App Download
            {"code": "app-download:read", "name": "查看PDA下载", "module": "app-download"},
            # App Version
            {"code": "app-version:read", "name": "查看APP版本", "module": "app-version"},
            {"code": "app-version:update", "name": "更新APP版本", "module": "app-version"},
            # Backup
            {"code": "backup:read", "name": "查看备份", "module": "backup"},
            {"code": "backup:create", "name": "创建备份", "module": "backup"},
            {"code": "backup:restore", "name": "恢复备份", "module": "backup"},
            {"code": "backup:delete", "name": "删除备份", "module": "backup"},
            # Light Debug
            {"code": "light-debug:read", "name": "查看灯控调试", "module": "light-debug"},
            {"code": "light-debug:control", "name": "灯控调试操作", "module": "light-debug"},
            # Role
            {"code": "role:read", "name": "查看角色", "module": "role"},
            {"code": "role:create", "name": "新建角色", "module": "role"},
            {"code": "role:update", "name": "编辑角色", "module": "role"},
            {"code": "role:delete", "name": "删除角色", "module": "role"},
            # Permission
            {"code": "permission:read", "name": "查看权限", "module": "permission"},
        ]

        # Insert permissions if not exist
        permission_map = {}
        for p_def in all_permissions:
            existing = await session.execute(
                select(Permission).where(Permission.code == p_def["code"])
            )
            perm = existing.scalar_one_or_none()
            if perm is None:
                perm = Permission(
                    code=p_def["code"],
                    name=p_def["name"],
                    module=p_def["module"],
                    description=p_def["name"],
                )
                session.add(perm)
                await session.flush()
            permission_map[p_def["code"]] = perm.id

        # ====================================================================
        # 2. Default Roles
        # ====================================================================
        admin_permissions = [p["code"] for p in all_permissions]

        supervisor_permissions = [
            "dashboard:read",
            "material:read", "material:create", "material:update",
            "shelf:read", "shelf:create", "shelf:update",
            "inventory:read", "inventory:update", "inventory:export", "inventory:direct-out",
            "receipt:read", "receipt:create", "receipt:scan", "receipt:manual-entry",
            "issue:read", "issue:create", "issue:update", "issue:assign", "issue:pick",
            "xr:read", "xr:upload", "xr:match",
            "bom:read", "bom:create", "bom:update",
            "report:read",
            "settings:read",
            "barcode:read",
            "customer:read",
            "supplier:read", "supplier:create", "supplier:update",
            "user:read",
            "role:read",
            "permission:read",
            "app-download:read",
            "backup:read",
        ]

        operator_permissions = [
            "dashboard:read",
            "material:read",
            "shelf:read",
            "inventory:read", "inventory:update", "inventory:export",
            "receipt:read", "receipt:create", "receipt:scan", "receipt:manual-entry",
            "issue:read", "issue:create", "issue:update", "issue:assign", "issue:pick",
            "xr:read", "xr:upload", "xr:match",
            "bom:read",
            "report:read",
        ]

        readonly_permissions = [
            "dashboard:read",
            "material:read",
            "shelf:read",
            "inventory:read",
            "receipt:read",
            "issue:read",
            "xr:read",
            "bom:read",
            "report:read",
            "customer:read",
            "supplier:read",
            "settings:read",
            "barcode:read",
            "app-download:read",
            "backup:read",
        ]

        role_defs = [
            {
                "name": "管理员",
                "code": "admin",
                "description": "系统管理员，拥有全部权限",
                "is_system": 1,
                "perms": admin_permissions,
            },
            {
                "name": "主管",
                "code": "supervisor",
                "description": "主管，拥有大部分管理和操作权限",
                "is_system": 1,
                "perms": supervisor_permissions,
            },
            {
                "name": "操作员",
                "code": "operator",
                "description": "操作员，拥有日常操作所需权限",
                "is_system": 1,
                "perms": operator_permissions,
            },
            {
                "name": "只读用户",
                "code": "readonly",
                "description": "只读用户，仅可查看数据",
                "is_system": 1,
                "perms": readonly_permissions,
            },
        ]

        role_id_map = {}
        for rd in role_defs:
            existing = await session.execute(
                select(Role).where(Role.code == rd["code"])
            )
            role = existing.scalar_one_or_none()
            if role is None:
                role = Role(
                    name=rd["name"],
                    code=rd["code"],
                    description=rd["description"],
                    is_system=rd["is_system"],
                    active=1,
                )
                session.add(role)
                await session.flush()
            role_id_map[rd["code"]] = role.id

            # Assign permissions to role (only if role was just created)
            if role:
                # Check if permissions already assigned
                existing_rp = await session.execute(
                    select(RolePermission).where(RolePermission.role_id == role.id).limit(1)
                )
                if existing_rp.scalar_one_or_none() is None:
                    for perm_code in rd["perms"]:
                        perm_id = permission_map.get(perm_code)
                        if perm_id:
                            session.add(RolePermission(
                                role_id=role.id,
                                permission_id=perm_id,
                            ))

        # ====================================================================
        # 3. Admin user
        # ====================================================================
        result = await session.execute(
            select(User).where(User.username == "admin")
        )
        admin_user = result.scalar_one_or_none()
        if admin_user is None:
            admin_user = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                role="admin",
                role_id=role_id_map.get("admin"),
                active=1,
            )
            session.add(admin_user)
        elif admin_user.role_id is None:
            admin_user.role_id = role_id_map.get("admin")

        # ====================================================================
        # 4. Default customer
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
        # 5. System settings
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
            # ── App version (PDA update check) ──
            {
                "key": "app_latest_version",
                "value": "3.0.0",
                "description": "PDA App 最新版本号",
            },
            {
                "key": "app_min_version",
                "value": "3.0.0",
                "description": "PDA App 最低兼容版本号（低于此版本的 APP 将被强制更新）",
            },
            {
                "key": "app_download_url",
                "value": "",
                "description": "PDA App APK 下载地址",
            },
            {
                "key": "app_release_notes",
                "value": "",
                "description": "PDA App 更新说明",
            },
        ]
        for s in default_settings:
            existing = await session.execute(
                select(SystemSetting).where(SystemSetting.key == s["key"])
            )
            if existing.scalar_one_or_none() is None:
                session.add(SystemSetting(**s))

        await session.commit()
