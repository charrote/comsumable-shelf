#!/usr/bin/env python3
"""E2E 测试环境初始化脚本 — 操作 PostgreSQL 创建料架+储位（智能料架 HTTP API 版本）。"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.utils.database import async_session_factory, engine
from app.models import Shelf, ShelfSlot, SystemSetting
from sqlalchemy import select, text


async def main():
    print("=" * 60)
    print("E2E 测试环境初始化（智能料架 HTTP API）")
    print("=" * 60)

    # ── 先独立创建料架并提交 ──
    print("\n[1/3] 创建料架...")
    async with async_session_factory() as db:
        result = await db.execute(select(Shelf).where(Shelf.code == "SMT-01"))
        shelf = result.scalar_one_or_none()
        if shelf:
            print(f"  ✅ 料架已存在: id={shelf.id} code={shelf.code}")
        else:
            shelf = Shelf(
                code="SMT-01", name="SMT 料架 1号",
                location="SMT车间 A区", active=1,
            )
            db.add(shelf)
            await db.commit()
            await db.refresh(shelf)
            print(f"  ✅ 料架已创建: id={shelf.id} code={shelf.code}")

    # ── 新会话创建储位（使用 ORM 批量 INSERT） ──
    print("\n[2/3] 创建储位...")
    async with async_session_factory() as db:
        result = await db.execute(select(Shelf).where(Shelf.code == "SMT-01"))
        shelf = result.scalar_one()
        shelf_id = shelf.id

        # 清空旧储位并提交
        await db.execute(ShelfSlot.__table__.delete().where(ShelfSlot.shelf_id == shelf_id))
        await db.commit()
        print(f"  🧹 已清除 shelf_id={shelf_id} 旧储位")

    # 重新开一个会话批量插入储位
    async with async_session_factory() as db:
        result = await db.execute(select(Shelf).where(Shelf.code == "SMT-01"))
        shelf = result.scalar_one()
        shelf_id = shelf.id

        slots = []
        count = 0
        for side in ["A", "B"]:
            for slot_num in range(1, 41):
                cell_id = f"{shelf.code}{side}{slot_num:04d}".upper()
                slot = ShelfSlot(
                    shelf_id=shelf_id,
                    side=side,
                    slot_on_board=slot_num,
                    cell_id=cell_id,
                    last_sensor_state=0,
                )
                slots.append(slot)
                count += 1

        db.add_all(slots)
        await db.commit()
        print(f"  ✅ 创建了 {count} 个储位")

    # ── 确认前5个储位 ──
    print("\n[3/3] 储位清单 (前5个):")
    async with async_session_factory() as db:
        result = await db.execute(select(Shelf).where(Shelf.code == "SMT-01"))
        shelf = result.scalar_one()
        slots_result = await db.execute(
            select(ShelfSlot)
            .where(ShelfSlot.shelf_id == shelf.id)
            .order_by(ShelfSlot.side, ShelfSlot.slot_on_board)
            .limit(5)
        )
        slots = slots_result.scalars().all()
        for s in slots:
            print(f"     slot_id={s.id:3d}  side={s.side}  slot_on_board={s.slot_on_board:2d}  "
                  f"cell_id={s.cell_id}")

        # System settings
        dup_setting = await db.execute(
            select(SystemSetting).where(SystemSetting.key == "duplicate_scan_behavior")
        )
        dup = dup_setting.scalar_one_or_none()
        if dup and dup.value == "block":
            print("\n  ⚠️ 当前重复扫码策略为 'block'，测试时同一条码只能扫一次")

    print("\n" + "=" * 60)
    print("环境初始化完成！")
    print("=" * 60)
    print("""
PDA 模拟器操作步骤:
  1. 登录        → admin / admin123
  2. 首页        → 确认 Dashboard 有料架信息
  3. 扫码入库     → 操作员 → 扫条码(如 CUST-R-0402-10K)
                     → 预览确认 → 入库
  4. 补料上架     → 扫料盘 → 选储位 → 绑定
  5. 扫码出库     → 选 BOM → 计算 → LED → 拣料确认
""")


if __name__ == "__main__":
    asyncio.run(main())
