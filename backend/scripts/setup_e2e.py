#!/usr/bin/env python3
"""E2E 测试环境初始化脚本 — 操作 PostgreSQL 创建料架+储位。"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.utils.database import async_session_factory, engine
from app.models import Shelf, ShelfSlot, SystemSetting
from sqlalchemy import select, text


async def main():
    print("=" * 60)
    print("E2E 测试环境初始化")
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
                a_sides=2, b_sides=2, total_slots=80,
                controller_ip="192.168.1.100", controller_port=502,
                a_side_count=2, b_side_count=2,
                location="SMT车间 A区", active=1,
            )
            db.add(shelf)
            await db.commit()
            await db.refresh(shelf)
            print(f"  ✅ 料架已创建: id={shelf.id} code={shelf.code}")

    # ── 新会话创建储位 ──
    print("\n[2/3] 创建储位...")
    async with async_session_factory() as db:
        # 读取料架
        result = await db.execute(select(Shelf).where(Shelf.code == "SMT-01"))
        shelf = result.scalar_one()
        shelf_id = shelf.id

        # 清空旧储位并提交
        await db.execute(ShelfSlot.__table__.delete().where(ShelfSlot.shelf_id == shelf_id))
        await db.commit()
        print(f"  🧹 已清除 shelf_id={shelf_id} 旧储位")

    # 重新开一个会话插入储位（用原始 SQL 避免 ORM 批量 INSERT 问题）
    async with async_session_factory() as db:
        result = await db.execute(select(Shelf).where(Shelf.code == "SMT-01"))
        shelf = result.scalar_one()
        shelf_id = shelf.id

        count = 0
        for side in ["A", "B"]:
            for board in [1, 2]:
                for slot_num in range(1, 21):
                    side_offset = 0 if side == "A" else 40
                    # NOTE: board 2 的 slot_on_board 偏移 20 避免 UniqueConstraint 冲突
                    # (约束 "uq_slot_pos" = shelf_id + side + slot_on_board, 缺少 board_address)
                    db_slot = slot_num + (20 if board == 2 else 0)
                    global_idx = side_offset + (board - 1) * 20 + slot_num
                    coil_base = 10000 + (global_idx - 1) * 4
                    modbus_tcp_id = board if side == "A" else 63 + board

                    await db.execute(
                        text("""
                            INSERT INTO shelf_slots
                                (shelf_id, side, board_address, slot_on_board,
                                 global_index, modbus_tcp_id, modbus_coil_base,
                                 last_sensor_state)
                            VALUES
                                (:shelf_id, :side, :board, :slot,
                                 :global_idx, :tcp_id, :coil_base, 0)
                        """),
                        {
                            "shelf_id": shelf_id,
                            "side": side,
                            "board": board,
                            "slot": db_slot,
                            "global_idx": global_idx,
                            "tcp_id": modbus_tcp_id,
                            "coil_base": coil_base,
                        }
                    )
                    count += 1
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
            .order_by(ShelfSlot.side, ShelfSlot.board_address, ShelfSlot.slot_on_board)
            .limit(5)
        )
        slots = slots_result.scalars().all()
        for s in slots:
            print(f"     slot_id={s.id:3d}  {s.side}{s.board_address}-{s.slot_on_board:2d}  "
                  f"global={s.global_index:3d}  tcp_id={s.modbus_tcp_id:2d}  coil={s.modbus_coil_base:5d}")

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
