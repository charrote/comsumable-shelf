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


async def seed_db():
    """Seed default data (admin user, default customer, SMT materials, BOMs, system settings)."""
    from app.models import (
        User, SystemSetting, Customer, MaterialCategory, MaterialMaster,
        CustomerMaterialMapping, Bom, BomItem, BomAlternative,
    )
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
            session.expunge(customer)  # detach since it's from a closed result

        customer_id = customer.id

        # ====================================================================
        # 3. Material Categories (SMT)
        # ====================================================================
        from app.models import MaterialCategory
        categories_data = [
            ("RES", "电阻", "Resistor"),
            ("CAP", "电容", "Capacitor"),
            ("IND", "电感", "Inductor"),
            ("IC", "集成电路", "Integrated Circuit"),
            ("DIO", "二极管", "Diode"),
            ("TRANS", "晶体管", "Transistor / MOSFET"),
            ("CONNECTOR", "连接器", "Connector"),
            ("CRYSTAL", "晶振", "Crystal / Oscillator"),
            ("OTHER", "其他", "Other"),
        ]
        cat_code_to_id = {}
        for cat_code, cat_name, cat_desc in categories_data:
            existing = await session.execute(
                select(MaterialCategory).where(
                    MaterialCategory.customer_id == customer_id,
                    MaterialCategory.code == cat_code,
                )
            )
            cat = existing.scalar_one_or_none()
            if cat is None:
                cat = MaterialCategory(
                    customer_id=customer_id,
                    code=cat_code,
                    name=cat_name,
                )
                session.add(cat)
            cat_code_to_id[cat_code] = cat.id
        await session.flush()

        # ====================================================================
        # 4. Material Master Data (SMT components — ~60 parts)
        # ====================================================================
        from app.models import MaterialMaster, CustomerMaterialMapping

        materials_data = [
            # (code, name, spec, category_code, qty_per_pallet, customer_code)
            # --- Resistors ---
            ("R-0402-10K", "电阻 0402 10KΩ", "0402 10KΩ ±1%", "RES", 5000.0, "CUST-R-0402-10K"),
            ("R-0402-100K", "电阻 0402 100KΩ", "0402 100KΩ ±1%", "RES", 5000.0, "CUST-R-0402-100K"),
            ("R-0402-1K", "电阻 0402 1KΩ", "0402 1KΩ ±1%", "RES", 5000.0, "CUST-R-0402-1K"),
            ("R-0402-0R", "电阻 0402 0Ω", "0402 0Ω (跳线)", "RES", 5000.0, "CUST-R-0402-0R"),
            ("R-0603-10K", "电阻 0603 10KΩ", "0603 10KΩ ±1%", "RES", 4000.0, "CUST-R-0603-10K"),
            ("R-0603-4R7", "电阻 0603 4.7Ω", "0603 4.7Ω ±1%", "RES", 4000.0, "CUST-R-0603-4R7"),
            ("R-0805-100K", "电阻 0805 100KΩ", "0805 100KΩ ±1%", "RES", 4000.0, "CUST-R-0805-100K"),
            ("R-0805-10K", "电阻 0805 10KΩ", "0805 10KΩ ±1%", "RES", 5000.0, "CUST-R-0805-10K"),
            # --- Capacitors ---
            ("C-0402-100nF", "电容 0402 100nF", "0402 100nF (104) 16V X7R", "CAP", 10000.0, "CUST-C-0402-100N"),
            ("C-0402-10uF", "电容 0402 10uF", "0402 10uF 6.3V X5R", "CAP", 8000.0, "CUST-C-0402-10U"),
            ("C-0603-10nF", "电容 0603 10nF", "0603 10nF (103) 50V X7R", "CAP", 8000.0, "CUST-C-0603-10N"),
            ("C-0603-1uF", "电容 0603 1uF", "0603 1uF 25V X7R", "CAP", 6000.0, "CUST-C-0603-1U"),
            ("C-0805-10uF", "电容 0805 10uF", "0805 10uF 16V X5R", "CAP", 5000.0, "CUST-C-0805-10U"),
            ("C-0805-100uF", "电容 0805 100uF", "0805 100uF 6.3V X5R", "CAP", 2000.0, "CUST-C-0805-100U"),
            ("C-1206-47uF", "电容 1206 47uF", "1206 47uF 10V X5R", "CAP", 2000.0, "CUST-C-1206-47U"),
            ("C-0402-1pF", "电容 0402 1pF", "0402 1pF 50V C0G/NP0", "CAP", 10000.0, "CUST-C-0402-1P"),
            # --- Inductors ---
            ("L-0603-10uH", "电感 0603 10uH", "0603 10μH 0.5A 屏蔽", "IND", 4000.0, "CUST-L-0603-10U"),
            ("L-0805-100uH", "电感 0805 100uH", "0805 100μH 0.3A 屏蔽", "IND", 3000.0, "CUST-L-0805-100U"),
            ("L-1210-22uH", "电感 1210 22uH", "1210 22μH 1.5A 屏蔽", "IND", 2000.0, "CUST-L-1210-22U"),
            ("L-0603-220uH", "电感 0603 220uH", "0603 220μH 0.2A 屏蔽", "IND", 3000.0, "CUST-L-0603-220U"),
            # --- Diodes ---
            ("D-SM4S5.0", "TVS 二极管 SMA 5.0V", "SM4S5.0 双向 5V 400W SMA", "DIO", 2000.0, "CUST-D-SM4S5"),
            ("D-SCHOTTKY", "肖特基二极管 SMA 40V", "SS14 40V 1A SMA", "DIO", 3000.0, "CUST-D-SS14"),
            ("D-1N4148", "开关二极管 SOD-323", "1N4148WS 100V 0.15A SOD-323", "DIO", 5000.0, "CUST-D-1N4148"),
            # --- Transistors / MOSFETs ---
            ("Q-PMOSSO8", "N-MOSFET SO-8 30V", "SI2301DDS N-Channel 30V 4.2A SO-8", "TRANS", 2000.0, "CUST-Q-SI2301"),
            ("Q-PMOSDSO", "P-MOSFET SOT-23 60V", "BSS84 P-Channel 60V 0.2A SOT-23", "TRANS", 5000.0, "CUST-Q-BSS84"),
            ("Q-NMOS8SO", "N-MOSFET SOIC-8 60V", "AO4800 N-Channel 60V 4.2A SO-8", "TRANS", 2000.0, "CUST-Q-AO4800"),
            ("Q-LDO503", "LDO 500mA 3.3V", "ME6211 C5 3.3 SOT-23-5 LDO", "TRANS", 4000.0, "CUST-Q-ME6211"),
            # --- ICs ---
            ("IC-ESP32S3", "ESP32-S3WROOM4", "ESP32-S3WROOM4 Wi-Fi + BT5 MCU QFN-56", "IC", 500.0, "CUST-IC-ESP32S3"),
            ("IC-LDO33", "LDO 1A 3.3V", "AP2112K-3.3 TR8-8 SOIC-8 3.3V LDO", "IC", 3000.0, "CUST-IC-AP2112"),
            ("IC-PMOSDR", "PMOS 双路 MOS 驱动器", "TPIC6B595 8路 50V SOIC-24", "IC", 1500.0, "CUST-IC-TPIC6B"),
            ("IC-CONSTCUR", "LED 恒流驱动器", "PT4115 3.5A 宽电压输入 SOP-8", "IC", 1500.0, "CUST-IC-PT4115"),
            ("IC-USBHUB", "USB 2.0 HUB 4-Port", "VL812QG UQFN-40 USB3.0 HUB", "IC", 800.0, "CUST-IC-VL812"),
            ("IC-ETHPHY", "以太网 PHY 单口", "LAN8720A LQFP-48 Ethernet PHY 10/100", "IC", 1000.0, "CUST-IC-LAN8720"),
            ("IC-ISOVM", "隔离收发器 双通道", "ISO7741DR 3.0-5.5V SOIC-8 数字隔离器", "IC", 2000.0, "CUST-IC-ISO7741"),
            ("IC-SOCMETER", "高精度计量 IC", "ATR24C512A SOP-8 I2C 电表芯片", "IC", 1500.0, "CUST-IC-ATR24C5"),
            ("IC-REGULATOR", "Buck 开关稳压器 3A", "MP2451 DISO-8 1.75-12V 3A DC-DC", "IC", 2000.0, "CUST-IC-MP2451"),
            # --- Connectors ---
            ("CONN-USBC", "USB Type-C 母座 16Pin", "USB-C-31-SMT-16 USB Type-C 16P SMT", "CONNECTOR", 1000.0, "CUST-CON-USBC"),
            ("CONN-RJ45", "RJ45 母座 1×1 带磁性屏蔽", "8P8C RJ45 Jack 1×1 SMD 带变压器", "CONNECTOR", 500.0, "CUST-CON-RJ45"),
            ("CONN-PH20", "PH2.0 排针 4Pin", "PH2.0mm 4P 双排针 2.54mm", "CONNECTOR", 2000.0, "CUST-CON-PH204"),
            ("CONN-GPIO40", "GPIO 2×20 排针", "2.54mm 2×20 Pin Header Male Straight", "CONNECTOR", 1000.0, "CUST-CON-GPIO40"),
            ("CONN-TERM25", "接线端子 2.5mm² 2Pin", "PH2.41 2P Screw Terminal Block 2.5mm²", "CONNECTOR", 2000.0, "CUST-CON-TERM25"),
            ("CONN-USBAB", "USB-A 母座", "USB-A SMT Type-A 母座 四脚", "CONNECTOR", 2000.0, "CUST-CON-USBA"),
            ("CONN-DC55", "DC 5.5×2.1mm 电源插座", "DC-Jack-5.5×2.1mm SMT 立式", "CONNECTOR", 2000.0, "CUST-CON-DC55"),
            ("CONN-BAT4", "CR2032 电池座", "CR2032 SMD Coin Cell Holder", "CONNECTOR", 2000.0, "CUST-CON-BAT4"),
            # --- Crystals ---
            ("Y-16M", "晶振 16MHz", "16.000MHz HC-49S SMD 晶振 ±30ppm", "CRYSTAL", 2000.0, "CUST-Y-16M"),
            ("Y-32M", "晶振 32.768kHz", "32.768kHz 12.5×1.6mm SMD 晶体", "CRYSTAL", 2000.0, "CUST-Y-32K7"),
            # --- Other ---
            ("OT-BTN", "轻触开关 6×6mm", "SMD Push Button Switch 6×6×2.5mm", "OTHER", 3000.0, "CUST-OT-BTN66"),
            ("OT-FERRITE", "磁珠 600Ω 0402", "BAD1005B601T020 600Ω@100MHz 0402", "OTHER", 5000.0, "CUST-OT-FERRITE"),
            ("OT-OPAMP", "运算放大器 SOIC-8", "LM358DR SOIC-8 Dual Op-Amp", "IC", 3000.0, "CUST-OT-LM358"),
            ("OT-REF", "电压基准 1.25V", "TL431AIDBVR SOT-23-3 可调精密基准源", "IC", 3000.0, "CUST-OT-TL431"),
            ("OT-TEMP", "数字温度传感器 SOT-23-6", "TMP117AIDBVR SOT-23-6 I2C 温度传感器", "IC", 2000.0, "CUST-OT-TMP117"),
            ("OT-PWRMGR", "电源管理 PMIC", "TPS65010DCTR SOP-20 PMIC", "IC", 1000.0, "CUST-OT-TPS65010"),
            ("OT-PORTSEL", "USB 电源开关", "TPS2051BDWER SOIC-8 USB Power Switch", "IC", 3000.0, "CUST-OT-TPS2051"),
            ("OT-ICOMPAR", "比较器 SOT-23-5", "LMX301CM5X/NOPB SOT-23-5 比较器", "IC", 5000.0, "CUST-OT-LMX301"),
            ("OT-ETHIS", "以太网隔离变压器", "5091B1101NL 1×1 RJ45隔离变压器", "OTHER", 500.0, "CUST-OT-5091B11"),
        ]

        mat_code_to_id = {}
        for mat_code, mat_name, mat_spec, cat_code, qty_pp, cust_code in materials_data:
            existing = await session.execute(
                select(MaterialMaster).where(
                    MaterialMaster.customer_id == customer_id,
                    MaterialMaster.code == mat_code,
                )
            )
            mat = existing.scalar_one_or_none()
            if mat is None:
                mat = MaterialMaster(
                    customer_id=customer_id,
                    code=mat_code,
                    name=mat_name,
                    spec=mat_spec,
                    category_id=cat_code_to_id[cat_code],
                    qty_per_pallet=qty_pp,
                    unit="盘",
                    active=1,
                )
                session.add(mat)
                await session.flush()
            mat_code_to_id[mat_code] = mat

            # Customer mapping
            mapping = await session.execute(
                select(CustomerMaterialMapping).where(
                    CustomerMaterialMapping.customer_id == customer_id,
                    CustomerMaterialMapping.customer_material_code == cust_code,
                )
            )
            if mapping.scalar_one_or_none() is None:
                session.add(CustomerMaterialMapping(
                    customer_id=customer_id,
                    customer_material_code=cust_code,
                    internal_material_id=mat_code_to_id[mat_code].id,
                    active=1,
                ))
        await session.flush()

        # ====================================================================
        # 5. Product Materials (BOM target products)
        # ====================================================================
        products_data = [
            ("PROD-WIFI-GATEWAY", "WiFi 物联网网关主板", "IoT Gateway main board with ESP32-S3"),
            ("PROD-SMART-LEDDRIVER", "智能 LED 驱动板 V3", "Constant current LED driver with dimming"),
            ("PROD-SMART-METER", "智能电表主板 V2", "Single-phase smart meter with Ethernet"),
        ]
        prod_code_to_id = {}
        for prod_code, prod_name, prod_desc in products_data:
            existing = await session.execute(
                select(MaterialMaster).where(
                    MaterialMaster.customer_id == customer_id,
                    MaterialMaster.code == prod_code,
                )
            )
            mat = existing.scalar_one_or_none()
            if mat is None:
                mat = MaterialMaster(
                    customer_id=customer_id,
                    code=prod_code,
                    name=prod_name,
                    spec=prod_desc,
                    unit="套",
                    active=1,
                )
                session.add(mat)
                await session.flush()
            prod_code_to_id[prod_code] = mat
            cust_code = "CUST-" + prod_code
            dup_mapping = await session.execute(
                select(CustomerMaterialMapping).where(
                    CustomerMaterialMapping.customer_id == customer_id,
                    CustomerMaterialMapping.customer_material_code == cust_code,
                )
            )
            if dup_mapping.scalar_one_or_none() is None:
                session.add(CustomerMaterialMapping(
                    customer_id=customer_id,
                    customer_material_code=cust_code,
                    internal_material_id=prod_code_to_id[prod_code].id,
                    active=1,
                ))
        await session.flush()

        # ====================================================================
        # 6. BOM Seed Data — 3 SMT Products
        # ====================================================================
        from app.models import Bom, BomItem, BomAlternative

        boms_data = [
            # (bom_code, version, description, item_list)
            # ---------- BOM 1: WiFi IoT Gateway ----------
            (
                "PROD-WIFI-GATEWAY", "V1.0",
                "WiFi 物联网网关主板 — ESP32-S3 + USB HUB + RJ45",
                [
                    # (position, material_code, qty, remark, [alternatives])
                    (1, "IC-ESP32S3", 1, "WiFi+BT5 主控 MCU QFN-56", []),
                    (2, "IC-LDO33", 1, "3.3V LDO 电源 IC", [
                        ("IC-REGULATOR", 2, "Buck 开关稳压替代方案"),
                    ]),
                    (3, "Q-LDO503", 1, "LDO 3.3V 500mA 供电", [
                        ("Q-PMOSSO8", 2, "MOS + LDO 分立方案"),
                    ]),
                    (4, "Y-16M", 1, "16MHz 系统时钟晶振", []),
                    (5, "C-0402-100nF", 6, "去耦电容", []),
                    (6, "C-0402-10uF", 3, "电源滤波", []),
                    (7, "C-0402-1pF", 2, "晶振负载电容", []),
                    (8, "R-0402-10K", 8, "上拉 / 分压电阻", []),
                    (9, "R-0402-100K", 4, "上拉电阻", []),
                    (10, "R-0402-1K", 3, "GPIO 限流", []),
                    (11, "R-0402-0R", 4, "跳线电阻", []),
                    (12, "D-SM4S5.0", 2, "USB 端口 TVS 保护", []),
                    (13, "OT-FERRITE", 2, "信号线磁珠滤波", []),
                    (14, "CONN-USBC", 1, "USB Type-C 供电 + 调试", []),
                    (15, "CONN-GPIO40", 1, "40Pin GPIO 排针", []),
                    (16, "CONN-USBAB", 1, "USB-A 母座扩展", []),
                    (17, "OT-BTN", 1, "复位按钮", []),
                    (18, "CONN-RJ45", 1, "RJ45 网口", []),
                    (19, "IC-ISOVM", 1, "RJ45 信号隔离器", []),
                    (20, "IC-ETHPHY", 1, "以太网 PHY LAN8720A", []),
                ],
            ),
            # ---------- BOM 2: Smart LED Driver ----------
            (
                "PROD-SMART-LEDDRIVER", "V1.0",
                "智能 LED 恒流驱动板 V1 — PT4115 + 4路 PMOS 控制",
                [
                    (1, "IC-CONSTCUR", 4, "LED 恒流驱动 IC PT4115 × 4通道", []),
                    (2, "IC-PMOSDR", 1, "8路 50V MOS 驱动器 TPIC6B595", []),
                    (3, "Q-PMOSSO8", 4, "N-MOSFET SO-8 开关管", [
                        ("Q-NMOS8SO", 2, "AO4800 替代"),
                    ]),
                    (4, "L-0805-100uH", 4, "LED 驱动储能电感 100uH", [
                        ("L-1210-22uH", 2, "大电流替代"),
                    ]),
                    (5, "D-SCHOTTKY", 4, "肖特基续流二极管 SS14", []),
                    (6, "C-0805-10uF", 8, "驱动电源滤波", []),
                    (7, "C-0805-100uF", 2, "输入主滤波电容", []),
                    (8, "C-0603-1uF", 4, "PT4115 补偿电容", []),
                    (9, "C-0603-10nF", 4, "信号滤波", []),
                    (10, "R-0603-4R7", 4, "电流检测电阻 4.7Ω", [
                        ("R-0603-10K", 2, "测试跳线替代"),
                    ]),
                    (11, "R-0603-10K", 12, "偏置 / 分压电阻", []),
                    (12, "R-0805-100K", 4, "反馈电阻", []),
                    (13, "Y-32M", 1, "32.768kHz 实时时钟晶振", []),
                    (14, "C-0402-1pF", 2, "RTC 负载电容", []),
                    (15, "CONN-PH20", 4, "LED 输出 PH2.0 4Pin", []),
                    (16, "CONN-TERM25", 2, "输入端子 2Pin", []),
                    (17, "CONN-USBC", 1, "USB-C 控制供电", []),
                    (18, "OT-BTN", 2, "功能按键", []),
                    (19, "C-0402-100nF", 10, "去耦电容", []),
                    (20, "R-0402-10K", 6, "上拉 / 分压", []),
                ],
            ),
            # ---------- BOM 3: Smart Meter ----------
            (
                "PROD-SMART-METER", "V2.0",
                "单相智能电表主板 V2 — ARM Cortex-M4 + Ethernet + 计量",
                [
                    (1, "IC-ESP32S3", 0, "主控制器 (ARM Cortex-M4) — 替代方案", []),
                    (1, "IC-ESP32S3", 1, "主 MCU (预留, 正式BOM用 STM32 替代)", []),
                    (2, "IC-ETHPHY", 1, "以太网 PHY LAN8720A", []),
                    (3, "IC-ISOVM", 1, "数字隔离器 双通道", [
                        ("IC-ISOVM", 1, "自替代 (同料号多源)"),
                    ]),
                    (4, "OT-ETHIS", 1, "以太网隔离变压器", []),
                    (5, "IC-SOCMETER", 1, "高精度计量 IC", [
                        ("IC-REGULATOR", 2, "计量+电源整合方案"),
                    ]),
                    (6, "IC-REGULATOR", 1, "Buck DC-DC 3A 主电源", []),
                    (7, "Q-LDO503", 1, "LDO 3.3V 模拟电源", []),
                    (8, "Q-PMOSSO8", 1, "电源开关 MOSFET", []),
                    (9, "D-SCHOTTKY", 1, "电源防反接肖特基", []),
                    (10, "D-SM4S5.0", 2, "网络端口 TVS 保护", []),
                    (11, "D-1N4148", 2, "信号二极管", []),
                    (12, "Y-16M", 1, "系统时钟 16MHz 晶振", []),
                    (13, "Y-32M", 1, "RTC 32.768kHz 晶振", []),
                    (14, "C-0402-1pF", 4, "晶振负载电容 ×2", []),
                    (15, "C-0402-100nF", 16, "去耦电容全IC", []),
                    (16, "C-0402-10uF", 4, "IC 电源滤波", []),
                    (17, "C-0603-1uF", 3, "PHY + 隔离器滤波", []),
                    (18, "C-0805-10uF", 3, "电源输入滤波", []),
                    (19, "C-0805-100uF", 2, "主电源大容量滤波", []),
                    (20, "C-1206-47uF", 1, "计量 IC 参考电源滤波", []),
                    (21, "L-1210-22uH", 1, "Buck 电感 22uH", []),
                    (22, "L-0603-10uH", 2, "信号线共模滤波", []),
                    (23, "R-0805-10K", 6, "ETH 匹配 / 上拉", []),
                    (24, "R-0805-100K", 4, "分压 / 上拉", []),
                    (25, "R-0603-10K", 10, "GPIO / 信号电阻", []),
                    (26, "R-0402-10K", 8, "小板 / 测试点电阻", []),
                    (27, "R-0402-0R", 6, "跳线 / 预留", []),
                    (28, "OT-FERRITE", 3, "信号线磁珠", []),
                    (29, "OT-OPAMP", 1, "运算放大器 信号调理", []),
                    (30, "OT-REF", 1, "精密基准源 TL431", []),
                    (31, "OT-TEMP", 1, "温度传感器 环境监测", []),
                    (32, "CONN-RJ45", 1, "RJ45 网口 (带隔离变压器)", []),
                    (33, "CONN-TERM25", 2, "电源输入端子 2Pin", []),
                    (34, "CONN-USBC", 1, "USB-C 调试 + 供电", []),
                    (35, "CONN-GPIO40", 1, "40Pin 调试排针", []),
                    (36, "CONN-BAT4", 1, "CR2032 电池座 RTC 供电", []),
                    (37, "OT-BTN", 2, "按键 ×2 (复位 + 功能)", []),
                ],
            ),
        ]

        # --- Build BOMs ---
        bom_id_map = {}
        for bom_code, version, desc, item_list in boms_data:
            product_mat = prod_code_to_id[bom_code]

            # Check if BOM already exists
            existing = await session.execute(
                select(Bom).where(
                    Bom.customer_id == customer_id,
                    Bom.product_material_id == product_mat.id,
                    Bom.version == version,
                )
            )
            bom_obj = existing.scalar_one_or_none()
            if bom_obj is None:
                bom = Bom(
                    customer_id=customer_id,
                    product_material_id=product_mat.id,
                    version=version,
                    status="draft",
                    description=desc,
                )
                session.add(bom)
                await session.flush()
                bom_id_map[bom_code] = bom.id
                continue
            bom = bom_obj
            bom_id_map[bom_code] = bom.id

            # --- Build BOM item code map for parent references ---
            item_code_map = {}

            for position, mat_code, qty, remark, alternatives in item_list:
                material = mat_code_to_id.get(mat_code)
                if not material:
                    continue

                item = BomItem(
                    bom_id=bom.id,
                    material_id=material.id,
                    quantity=qty,
                    position=position,
                    remark=remark,
                )
                session.add(item)
                await session.flush()

                # Create code → id map for parent references
                item_code_map[(bom_code, mat_code)] = item.id

                # Create alternatives
                for alt_code, alt_priority, alt_remark in alternatives:
                    alt_material = mat_code_to_id.get(alt_code)
                    if alt_material:
                        alt = BomAlternative(
                            bom_item_id=item.id,
                            alternative_material_id=alt_material.id,
                            priority=alt_priority,
                            percentage=100.0,
                        )
                        session.add(alt)

        await session.flush()

        # ====================================================================
        # 7. System settings
        # ====================================================================
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
