"""
RackSlotPoller — 替代旧 SlotReader 的 HTTP 轮询服务。

设计说明:
  每 10s 调用 GetCellList 全量查询，更新 shelf_slots 表。
  与回调结合：回调处理即时变化，轮询用于一致性校验。

双模式:
  - 回调模式（主）: 料架主动推送储位变化 → rack_callback 接口处理
  - 轮询模式（兜底）: 每 10s 查询一次，确保状态一致
"""

import asyncio
import logging
from typing import Optional

from sqlalchemy import select, update

from app.models import Shelf, ShelfSlot
from app.services.rack_api_client import RackApiClient, get_rack_api_config
from app.utils.database import async_session_factory

logger = logging.getLogger(__name__)


class RackSlotPoller:
    """料架储位 HTTP 轮询服务

    用法::

        poller = RackSlotPoller()
        await poller.start()  # 在后台运行

        # ... 应用运行 ...

        await poller.stop()
    """

    POLL_INTERVAL: int = 10  # 秒

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """启动轮询（创建后台任务）"""
        if self._running:
            logger.warning("RackSlotPoller already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("RackSlotPoller started (interval=%ds)", self.POLL_INTERVAL)

    async def stop(self):
        """停止轮询"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("RackSlotPoller stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    async def _run_loop(self):
        """主循环"""
        while self._running:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("RackSlotPoller error: %s", e, exc_info=True)
            await asyncio.sleep(self.POLL_INTERVAL)

    async def _poll_once(self):
        """单次轮询：遍历所有活跃料架（有 API 配置的）"""
        async with async_session_factory() as db:
            result = await db.execute(
                select(Shelf).where(Shelf.active == 1)
            )
            shelves = result.scalars().all()

            if not shelves:
                return

            for shelf in shelves:
                try:
                    api_config = await get_rack_api_config(db)
                    if not api_config:
                        logger.info("Rack API not configured for shelf %s, skipping", shelf.name)
                        continue

                    client = RackApiClient(
                        base_url=api_config["base_url"],
                        user_id=api_config["user_id"],
                        client_id=api_config["client_id"],
                        timeout=5.0,
                    )
                    await self._sync_shelf_cells(db, shelf.id, client)
                except Exception as e:
                    logger.warning("Poll shelf %d failed: %s", shelf.id, e)

    async def _sync_shelf_cells(self, db, shelf_id: int, client: RackApiClient):
        """同步单个料架的所有储位

        通过 GetCellList 分页查询，更新 DB 中的电量、传感器状态等信息。
        """
        page_index = 1
        page_size = 100

        while True:
            resp = client.get_cell_list(
                rack_id=None,
                page_index=page_index,
                page_size=page_size,
            )
            cells = resp.get("data", [])
            if not cells:
                break

            for cell in cells:
                cell_id = cell.get("cellId")
                if not cell_id:
                    continue

                # 更新 shelf_slots 表（传感器状态）
                await db.execute(
                    update(ShelfSlot)
                    .where(
                        ShelfSlot.shelf_id == shelf_id,
                        ShelfSlot.cell_id == cell_id,
                    )
                    .values(
                        last_sensor_state=1 if cell.get("used") else 0,
                    )
                )

            if len(cells) < page_size:
                break
            page_index += 1

        await db.commit()
