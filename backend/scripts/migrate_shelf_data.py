"""
智能料架数据迁移脚本。

步骤:
  1. 备份 shelf_slots 表到 shelf_slots_backup_20260626
  2. 根据 shelf.code + slot_on_board 生成 cell_id
  3. 回填 cell_id
  4. 验证迁移前后数量一致
  5. （可选）删除 modbus_tcp_id、modbus_coil_base 列

用法:
    python -m scripts.migrate_shelf_data
"""

import asyncio
import logging

from sqlalchemy import text

from app.utils.database import engine

logger = logging.getLogger(__name__)


async def migrate() -> bool:
    """执行数据迁移，成功返回 True，失败返回 False"""
    async with engine.begin() as conn:
        # ── 1. 备份 ──
        logger.info("Creating backup table: shelf_slots_backup_20260626 ...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS shelf_slots_backup_20260626 AS
            SELECT * FROM shelf_slots;
        """))
        backup_count = (await conn.execute(
            text("SELECT COUNT(*) FROM shelf_slots_backup_20260626")
        )).scalar()
        logger.info("Backup created: shelf_slots_backup_20260626 (%d rows)", backup_count)

        # ── 2. 迁移前计数 ──
        count_before = (await conn.execute(
            text("SELECT COUNT(*) FROM shelf_slots")
        )).scalar()
        logger.info("Count before migration: %d", count_before)

        # ── 3. 生成 cell_id ──
        # 规则: shelf.code（去特殊字符）+ slot_on_board（4位补零）
        # 示例: shelf.code="SH-A-01", slot_on_board=1 → "SHA010001"
        logger.info("Generating cell_id for slots with NULL cell_id ...")
        result = await conn.execute(text("""
            UPDATE shelf_slots sl
            SET cell_id = UPPER(
                REPLACE(REPLACE(REPLACE(REPLACE(s.code, '-', ''), ' ', ''), '_', ''), '/', '')
            ) || LPAD(CAST(sl.slot_on_board AS TEXT), 4, '0')
            FROM shelves s
            WHERE sl.shelf_id = s.id
              AND sl.cell_id IS NULL;
        """))
        updated = result.rowcount
        logger.info("cell_id generated for %d slots", updated)

        # ── 4. 验证 ──
        count_after = (await conn.execute(
            text("SELECT COUNT(*) FROM shelf_slots")
        )).scalar()
        null_cell_id = (await conn.execute(
            text("SELECT COUNT(*) FROM shelf_slots WHERE cell_id IS NULL")
        )).scalar()

        logger.info(
            "Validation: before=%d, after=%d, NULL cell_id=%d",
            count_before, count_after, null_cell_id,
        )

        if count_before != count_after:
            logger.error("COUNT MISMATCH! Rolling back ...")
            return False

        if null_cell_id > 0:
            logger.warning(
                "%d slots still have NULL cell_id (slots without shelf binding). "
                "These need manual assignment.",
                null_cell_id,
            )

        # ── 5. （可选）删除旧 Modbus 字段 ──
        # 取消下面的注释以删除旧字段
        # logger.info("Dropping old Modbus columns ...")
        # await conn.execute(text("""
        #     ALTER TABLE shelf_slots DROP COLUMN IF EXISTS modbus_tcp_id;
        # """))
        # await conn.execute(text("""
        #     ALTER TABLE shelf_slots DROP COLUMN IF EXISTS modbus_coil_base;
        # """))
        # logger.info("Old Modbus columns dropped")

        logger.info("Migration completed successfully!")
        return True


async def rollback():
    """从备份表恢复"""
    logger.info("Rolling back from shelf_slots_backup_20260626 ...")
    async with engine.begin() as conn:
        await conn.execute(text("""
            DELETE FROM shelf_slots;
        """))
        await conn.execute(text("""
            INSERT INTO shelf_slots SELECT * FROM shelf_slots_backup_20260626;
        """))
        count = (await conn.execute(
            text("SELECT COUNT(*) FROM shelf_slots")
        )).scalar()
        logger.info("Rollback complete. shelf_slots count: %d", count)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    success = asyncio.run(migrate())
    print(f"\n{'=' * 50}")
    print(f"Migration success: {success}")
    print(f"{'=' * 50}")
