"""LED control service — 智能料架 HTTP API.

Polls the LedCommand table for queued commands and sends them
to the smart shelf hardware via RackApiClient (HTTP).
"""

import asyncio
import structlog
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Shelf, ShelfSlot, LedCommand as LedCommandModel
from app.utils.database import async_session_factory
from app.services.rack_api_client import RackApiClient, get_rack_api_config

logger = structlog.get_logger()


class LedService:
    """智能料架 LED 控制服务（仅支持 HTTP API 料架）。"""

    def __init__(self):
        self._db_worker: Optional[asyncio.Task] = None

    async def init(self):
        """Start DB worker."""
        self._db_worker = asyncio.create_task(self._db_command_worker())
        logger.info("LED service started (HTTP API mode)")

    async def shutdown(self):
        """Shutdown LED worker."""
        if self._db_worker:
            self._db_worker.cancel()
        logger.info("LED service stopped")

    # ------------------------------------------------------------------
    # DB-backed worker (consumes LedCommand table)
    # ------------------------------------------------------------------
    async def _db_command_worker(self):
        """Poll LedCommand table and send queued commands to hardware."""
        while True:
            try:
                await self._process_queued_commands()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("led_db_worker_error", error=str(e))
            await asyncio.sleep(2.0)

    async def _process_queued_commands(self):
        """Process all queued LED commands from the database."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(LedCommandModel)
                .where(LedCommandModel.status == "queued")
                .order_by(LedCommandModel.created_at.asc())
                .limit(20)
            )
            commands = result.scalars().all()

            for cmd in commands:
                try:
                    # 查 slot + shelf 获取控灯 API 配置
                    slot = await session.get(ShelfSlot, cmd.slot_id)
                    if not slot:
                        cmd.status = "failed"
                        logger.warning("led_slot_not_found", slot_id=cmd.slot_id)
                        continue

                    shelf = await session.get(Shelf, cmd.shelf_id)
                    if not shelf:
                        cmd.status = "failed"
                        logger.warning("led_shelf_not_found", shelf_id=cmd.shelf_id)
                        continue

                    api_config = await get_rack_api_config(session)
                    if not api_config:
                        cmd.status = "failed"
                        logger.warning("led_no_api_config",
                                       shelf_id=cmd.shelf_id, slot_id=cmd.slot_id)
                        continue

                    # 用 RackApiClient 亮灯
                    client = RackApiClient(
                        base_url=api_config["base_url"],
                        user_id=api_config["user_id"],
                        client_id=api_config["client_id"],
                    )

                    color_int = RackApiClient.LED_COLORS.get(cmd.color, 2)
                    client.light_up_cell(
                        cell_id=slot.cell_id,
                        led_color=color_int,
                        is_blink=cmd.is_blink or False,
                        turn_on_time=cmd.turn_on_time or 0,
                    )

                    cmd.status = "sent"
                    cmd.sent_at = datetime.utcnow()
                    logger.info("led_command_sent",
                                command_id=cmd.id, slot_id=cmd.slot_id,
                                cell_id=slot.cell_id, color=cmd.color)

                except Exception as e:
                    cmd.status = "failed"
                    logger.error("led_command_failed",
                                 command_id=cmd.id, slot_id=cmd.slot_id, error=str(e))

            if commands:
                await session.commit()
