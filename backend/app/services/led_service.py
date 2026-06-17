"""LED control service — AMKN7141-CHXX Protocol 2."""

import asyncio
import struct
from dataclasses import dataclass
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.hal.modbus import Amkn8702g, LedColor
from app.models import Shelf, ShelfSlot
from app.config import settings


@dataclass
class LedCommand:
    """LED control command."""
    face: str  # 'A' or 'B'
    board_addr: int  # 1-based RTU address
    slot_num: int  # 1-based slot number
    color: LedColor
    duration_ms: int = 0  # 0 = permanent, >0 = flash


class LedService:
    """Smart shelf LED control service."""

    def __init__(self):
        self.master: Optional[Amkn8702g] = None
        self._active_commands: List[LedCommand] = []
        self._command_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    async def init(self, master_ip: str = None, port: int = None):
        """Initialize LED controller."""
        self.master = Amkn8702g(
            ip=master_ip or settings.MASTER_IP,
            port=port or settings.MASTER_PORT,
        )
        await self.master.connect()
        self._worker_task = asyncio.create_task(self._command_worker())

    async def shutdown(self):
        """Shutdown LED controller."""
        if self._worker_task:
            self._worker_task.cancel()
        if self.master:
            await self.master.disconnect()

    async def _command_worker(self):
        """Process LED commands from queue."""
        while True:
            try:
                cmd = await asyncio.wait_for(
                    self._command_queue.get(), timeout=1.0
                )
                if cmd.duration_ms > 0:
                    # Flash
                    await self.master.set_led(
                        cmd.face, cmd.board_addr, cmd.slot_num, cmd.color
                    )
                    await asyncio.sleep(cmd.duration_ms / 1000.0)
                    await self.master.set_led(
                        cmd.face, cmd.board_addr, cmd.slot_num, LedColor.OFF
                    )
                else:
                    # Permanent
                    await self.master.set_led(
                        cmd.face, cmd.board_addr, cmd.slot_num, cmd.color
                    )
                self._command_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Requeue failed commands
                self._command_queue.put_nowait(cmd)
                await asyncio.sleep(1.0)

    async def light_slot(self, slot_id: int, color: LedColor = LedColor.GREEN,
                         duration_ms: int = 0):
        """Light a specific slot."""
        cmd = LedCommand(
            face='A',  # default, will be resolved
            board_addr=1,
            slot_num=1,
            color=color,
            duration_ms=duration_ms,
        )
        await self._command_queue.put(cmd)

    async def light_slot_by_shelf(self, shelf_slot_id: int,
                                    color: LedColor = LedColor.GREEN):
        """Light a slot by ShelfSlot ID from database."""
        async with AsyncSession() as session:
            result = await session.execute(
                select(ShelfSlot).where(ShelfSlot.id == shelf_slot_id)
            )
            slot = result.scalar_one_or_none()
            if not slot:
                return False

            face = slot.side
            board_addr = slot.board_address
            slot_num = slot.slot_on_board

            await self.master.set_led(face, board_addr, slot_num, color)
            return True

    async def clear_all_leds(self):
        """Turn off all LEDs."""
        if not self.master:
            return
        for face_name, board_count in [('A', self.master.a_boards),
                                        ('B', self.master.b_boards)]:
            for board in range(1, board_count + 1):
                for slot in range(1, self.master.slots_per_board + 1):
                    await self.master.set_led(face_name, board, slot, LedColor.OFF)

    async def flash_led(self, face: str, board_addr: int, slot_num: int,
                        color: LedColor = LedColor.RED):
        """Flash LED briefly for verification."""
        await self.master.flash_led(face, board_addr, slot_num, color)

    async def verify_pallet(self, shelf_slot_id: int) -> bool:
        """Verify material pallet placement by flashing green."""
        await self.light_slot_by_shelf(shelf_slot_id, LedColor.GREEN, 500)
        await asyncio.sleep(0.5)
        await self.light_slot_by_shelf(shelf_slot_id, LedColor.OFF)
        return True
