"""AMKN8702G Modbus TCP protocol handler and AMKN7141-CHXX LED protocol 2 implementation."""

import struct
import asyncio
import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)


class LedColor(Enum):
    OFF = auto()
    GREEN = auto()  # On (default)
    RED = auto()
    BLUE = auto()


@dataclass
class SlotState:
    face: str  # 'A' or 'B'
    board_addr: int  # 1-based RTU board address
    slot_num: int  # 1-based slot number
    has_material: bool
    led_color: LedColor = LedColor.OFF


class Amkn8702g:
    """AMKN8702G industrial communication board — Modbus TCP master."""

    # Register mapping (from protocol spec)
    RELAY_START = 0x0000
    RELAY_COUNT = 6  # K1-K6
    A_FACE_SLOT_START = 0x03E8  # 1000
    B_FACE_SLOT_START = 0x07D0  # 2000
    MAX_SLOT_REGS = 1000  # per face

    # Config registers (base 60000)
    REG_CONFIG_BASE = 60000
    REG_DEVICE_MODE = REG_CONFIG_BASE + 0  # 60000
    REG_DEVICE_STATION = REG_CONFIG_BASE + 1  # 60001
    REG_DEVICE_VERSION = REG_CONFIG_BASE + 2  # 60002
    REG_SHELF_TYPE = REG_CONFIG_BASE + 107  # 60107
    REG_A_BOARDS = REG_CONFIG_BASE + 108  # 60108
    REG_B_BOARDS = REG_CONFIG_BASE + 109  # 60109
    REG_DEVICE_COMMAND = REG_CONFIG_BASE + 121  # 60121

    # Commands
    CMD_IDLE = 0x0000
    CMD_SAVE = 0x0001
    CMD_FIRMWARE = 0x0002
    CMD_REBOOT = 0x0003
    CMD_CALIBRATE = 0x0004
    CMD_RESET = 0x0005
    CMD_VOICE_PLAY = 0x0006
    CMD_VOICE_STOP = 0x0007

    # LED Protocol 2 base address
    LED_PROTOCOL2_BASE = 10000  # 0x2710
    LED_COILS_PER_LED = 4  # G, R, B, Control

    def __init__(self, ip: str, port: int = 502, station: int = 200):
        self.ip = ip
        self.port = port
        self.station = station  # always 200

        # Shelf topology
        self.a_boards: int = 0
        self.b_boards: int = 0
        self.slots_per_board: int = 20  # configurable per board type

        # Connection
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected: bool = False

    @property
    def slot_base_address(self) -> int:
        """Calculate A-face slot base based on configured board count."""
        return self.A_FACE_SLOT_START

    def get_tcp_station(self, face: str, rtu_addr: int) -> int:
        """Map RTU board address to TCP station ID.
        A-face: 1-63 → 1-63
        B-face: 1-63 → 64-126
        """
        if face == 'A':
            return rtu_addr
        else:
            return rtu_addr + 63

    def get_slot_address(self, face: str, board_addr: int, slot_num: int) -> int:
        """Calculate Modbus address for a specific slot."""
        base = self.A_FACE_SLOT_START if face == 'A' else self.B_FACE_SLOT_START
        return base + (board_addr - 1) * self.slots_per_board + (slot_num - 1)

    def _build_modbus_frame(self, func_code: int, addr: int, count: int,
                            data: bytes = b'', station: int = None) -> bytes:
        """Build Modbus TCP frame."""
        station = station or self.station
        tid = 0x0001  # Simple transaction ID
        length = 6 + len(data) if func_code in (1, 2, 3, 4) else 6
        if func_code == 5 or func_code == 6:
            length = 6
        elif func_code == 15:
            byte_count = (count + 7) // 8
            length = 5 + 1 + byte_count
        elif func_code == 16:
            byte_count = len(data)
            length = 5 + 1 + byte_count

        if func_code in (1, 2, 3, 4):
            frame = struct.pack('>HHHBBHH', tid, 0, 6, station, func_code, addr, count)
        elif func_code == 5:
            val = 0xFF00 if data else 0x0000
            frame = struct.pack('>HHHBBH', tid, 0, 6, station, func_code, addr, val)
        elif func_code == 6:
            frame = struct.pack('>HHHBBH', tid, 0, 6, station, func_code, addr,
                               struct.unpack('>H', data)[0])
        elif func_code == 15:
            byte_count = (count + 7) // 8
            frame = struct.pack('>HHHBBHHB', tid, 0, 5 + 1 + byte_count, station,
                               func_code, addr, count, byte_count) + data
        elif func_code == 16:
            byte_count = len(data)
            frame = struct.pack('>HHHBBHHB', tid, 0, 5 + 1 + byte_count, station,
                               func_code, addr, count, byte_count) + data
        else:
            frame = struct.pack('>HHHBBHH', tid, 0, 6, station, func_code, addr, count)

        # Rebuild with correct length
        if func_code in (1, 2, 3, 4, 5, 6):
            frame = struct.pack('>HH', tid, 0) + struct.pack('>H', 6) + frame[6:]
        elif func_code in (15, 16):
            byte_count = (count + 7) // 8 if func_code == 15 else len(data)
            frame = struct.pack('>HH', tid, 0) + struct.pack('>H', 5 + 1 + byte_count) + frame[6:]

        return frame

    async def connect(self) -> bool:
        """Establish TCP connection to the AMKN8702G."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.ip, self.port), timeout=5.0
            )
            self._connected = True
            logger.info(f"Connected to AMKN8702G at {self.ip}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to AMKN8702G: {e}")
            return False

    async def disconnect(self):
        """Close TCP connection."""
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self._connected = False

    async def execute(self, func_code: int, addr: int, count: int = 1,
                      data: bytes = b'', station: int = None) -> Optional[bytes]:
        """Execute a Modbus TCP command."""
        if not self._connected:
            await self.connect()

        frame = self._build_modbus_frame(func_code, addr, count, data, station)

        try:
            self._writer.write(frame)
            await self._writer.drain()
            # Read response
            header = await asyncio.wait_for(self._reader.read(9), timeout=3.0)
            if len(header) < 9:
                return None
            byte_count = header[7]
            resp_data = await asyncio.wait_for(
                self._reader.read(byte_count + 2), timeout=3.0
            )  # +2 for CRC in RTU, or just data
            return header + resp_data
        except Exception as e:
            logger.error(f"Modbus execute failed: {e}")
            self._connected = False
            return None

    # --- High-level API ---

    async def configure_shelf(self, a_boards: int, b_boards: int,
                              slots_per_board: int = 20) -> bool:
        """Configure shelf geometry via config registers."""
        self.a_boards = a_boards
        self.b_boards = b_boards
        self.slots_per_board = slots_per_board

        # Write shelf type (1=sensed)
        await self.execute(16, self.REG_SHELF_TYPE, 1, struct.pack('>H', 1))
        # Write A-board count
        await self.execute(16, self.REG_A_BOARDS, 1, struct.pack('>H', a_boards))
        # Write B-board count
        await self.execute(16, self.REG_B_BOARDS, 1, struct.pack('>H', b_boards))
        # Save configuration
        await self.execute(6, self.REG_DEVICE_COMMAND, data=struct.pack('>H', self.CMD_SAVE))
        # Reset to apply
        await self.execute(6, self.REG_DEVICE_COMMAND, data=struct.pack('>H', self.CMD_RESET))
        return True

    async def read_all_slots(self) -> Dict[str, SlotState]:
        """Read all slot states from both faces."""
        slots = {}

        # Read A-face slots
        a_count = self.a_boards * self.slots_per_board
        if a_count > 0:
            result = await self.execute(2, self.A_FACE_SLOT_START, a_count)
            if result:
                byte_count = result[7]
                data = result[8:8 + byte_count]
                for i in range(min(a_count, len(data) * 8)):
                    byte_idx = i // 8
                    bit_idx = i % 8
                    has_mat = bool(data[byte_idx] & (1 << bit_idx))
                    board = i // self.slots_per_board + 1
                    slot = i % self.slots_per_board + 1
                    key = f"A{board}-{slot}"
                    slots[key] = SlotState(
                        face='A', board_addr=board, slot_num=slot,
                        has_material=has_mat
                    )

        # Read B-face slots
        b_count = self.b_boards * self.slots_per_board
        if b_count > 0:
            result = await self.execute(2, self.B_FACE_SLOT_START, b_count)
            if result:
                byte_count = result[7]
                data = result[8:8 + byte_count]
                for i in range(min(b_count, len(data) * 8)):
                    byte_idx = i // 8
                    bit_idx = i % 8
                    has_mat = bool(data[byte_idx] & (1 << bit_idx))
                    board = i // self.slots_per_board + 1
                    slot = i % self.slots_per_board + 1
                    key = f"B{board}-{slot}"
                    slots[key] = SlotState(
                        face='B', board_addr=board, slot_num=slot,
                        has_material=has_mat
                    )

        return slots

    async def set_led(self, face: str, board_addr: int, slot_num: int,
                      color: LedColor = LedColor.GREEN) -> bool:
        """Control LED using Protocol 2 (4 coils per LED, partial update).

        Protocol 2 addressing:
        - LEDnG = 10000 + 4*(n-1)
        - LEDnR = 10000 + 4*(n-1) + 1
        - LEDnB = 10000 + 4*(n-1) + 2
        - LEDnControl = 10000 + 4*(n-1) + 3
        - Control bit = 1 → G/R/B bits take effect
        - Control bit = 0 → G/R/B bits ignored (keep current state)

        Byte mapping (every 2 LEDs = 1 byte):
        - Odd LED n: G=Bit0, R=Bit1, B=Bit2, Control=Bit3
        - Even LED n: G=Bit4, R=Bit5, B=Bit6, Control=Bit7
        """
        # Global LED index (across all boards on this face)
        global_idx = (board_addr - 1) * self.slots_per_board + (slot_num - 1)

        # LED Protocol 2: 4 coils per LED
        coils_needed = global_idx * self.LED_COILS_PER_LED + 4
        bytes_needed = (coils_needed + 7) // 8

        # Build byte array
        bytes_arr = bytearray(bytes_needed)

        # Calculate which LED and which byte
        led_idx = global_idx
        byte_idx = led_idx // 2
        is_odd = led_idx % 2 == 0

        if is_odd:
            ctrl_bit, g_bit, r_bit, b_bit = 3, 0, 1, 2
        else:
            ctrl_bit, g_bit, r_bit, b_bit = 7, 4, 5, 6

        # Set control bit for this LED
        bytes_arr[byte_idx] |= (1 << ctrl_bit)

        # Set color bits
        if color == LedColor.GREEN:
            bytes_arr[byte_idx] |= (1 << g_bit)
        elif color == LedColor.RED:
            bytes_arr[byte_idx] |= (1 << r_bit)
        elif color == LedColor.BLUE:
            bytes_arr[byte_idx] |= (1 << b_bit)
        # OFF: control=1 but G=R=B=0

        # For all other LEDs on this board, set control=0 (no change)
        board_start = (board_addr - 1) * self.slots_per_board
        board_end = board_start + self.slots_per_board
        for i in range(board_start, board_end):
            if i == led_idx:
                continue
            other_byte = i // 2
            other_is_odd = i % 2 == 0
            other_ctrl = 3 if other_is_odd else 7
            bytes_arr[other_byte] &= ~(1 << other_ctrl)  # control=0

        tcp_station = self.get_tcp_station(face, board_addr)
        await self.execute(15, self.LED_PROTOCOL2_BASE, coils_needed,
                           bytes(bytes_arr), tcp_station)
        return True

    async def set_led_simple(self, face: str, board_addr: int, slot_num: int,
                             color: LedColor) -> bool:
        """Simple LED control: turn on one LED, turn off all others on board."""
        board_start = (board_addr - 1) * self.slots_per_board
        board_end = board_start + self.slots_per_board

        tcp_station = self.get_tcp_station(face, board_addr)

        for i in range(board_start, board_end):
            b = i // self.slots_per_board + 1
            s = i % self.slots_per_board + 1
            c = color if (b == board_addr and s == slot_num) else LedColor.OFF
            await self.set_led(face, b, s, c)

        return True

    async def flash_led(self, face: str, board_addr: int, slot_num: int,
                        color: LedColor = LedColor.RED) -> bool:
        """Flash LED green for quick verification."""
        await self.set_led(face, board_addr, slot_num, LedColor.GREEN)
        await asyncio.sleep(0.5)
        await self.set_led(face, board_addr, slot_num, LedColor.OFF)
        return True

    async def set_relay(self, relay_num: int, on: bool) -> bool:
        """Control relay K1-K6 (coils 0x0000-0x0005)."""
        addr = self.RELAY_START + (relay_num - 1)
        val = 0xFF00 if on else 0x0000
        await self.execute(5, addr, data=struct.pack('>H', val))
        return True

    async def get_device_info(self) -> Dict:
        """Read device status and info from config registers."""
        info = {}

        # Read device mode/status
        result = await self.execute(3, self.REG_DEVICE_MODE, 3)
        if result:
            data = result[8:]
            if len(data) >= 6:
                info['device_mode'] = struct.unpack('>H', data[0:2])[0]
                info['station_addr'] = struct.unpack('>H', data[2:4])[0]
                info['hw_sw_version'] = struct.unpack('>H', data[4:6])[0]

        # Read voltage
        result = await self.execute(3, self.REG_CONFIG_BASE + 21, 1)
        if result and len(result) > 8:
            voltage = struct.unpack('>H', result[8:10])[0]
            info['voltage'] = voltage / 100.0  # unit: 0.01V

        return info

    async def calibrate(self) -> bool:
        """Trigger shelf calibration."""
        await self.execute(6, self.REG_DEVICE_COMMAND,
                           data=struct.pack('>H', self.CMD_CALIBRATE))
        return True

    async def reset(self) -> bool:
        """Reset the master controller."""
        await self.execute(6, self.REG_DEVICE_COMMAND,
                           data=struct.pack('>H', self.CMD_RESET))
        return True


class SlotPoller:
    """Background slot state polling service."""

    def __init__(self, master: Amkn8702g, callback=None):
        self.master = master
        self.callback = callback  # callable with slot_states dict
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self, interval: int = None):
        """Start polling in background."""
        self._running = True
        interval = interval or self.master.slots_per_board  # fallback
        self._task = asyncio.create_task(self._poll_loop(interval))

    async def stop(self):
        """Stop polling."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self, interval: int):
        """Main polling loop."""
        while self._running:
            try:
                slots = await self.master.read_all_slots()
                if self.callback:
                    self.callback(slots)
            except Exception as e:
                logger.error(f"Slot poll error: {e}")
            await asyncio.sleep(interval)
