"""AMKN8702G Modbus TCP protocol handler.

Protocol:
- TCP port 502, station ID 200 (fixed)
- COM1 → A-face LED boards: TCP station 1-63 → RTU station 1-63
- COM2 → B-face LED boards: TCP station 64-126 → RTU station 1-63
- Digital inputs: A-face 1000-1999, B-face 2000-2999 (slot status)
- Config registers: 60000+ (60107=type, 60108=A-count, 60109=B-count)
- Coils 0x0000-0x0005: Relay K1-K6
"""

import asyncio
import struct
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from app.config import settings


class LedColor(Enum):
    GREEN = auto()
    RED = auto()
    BLUE = auto()
    OFF = auto()
    ON = auto()  # GREEN


@dataclass
class SlotStatus:
    """Single slot status from LED board."""
    board_number: int  # 1-based within face (A or B)
    slot_number: int  # 1-based within board
    has_material: bool  # True = material detected
    led_green: bool = False
    led_red: bool = False
    led_blue: bool = False


@dataclass
class ShelfFace:
    """One face (A or B) of the smart shelf."""
    face: str  # "A" or "B"
    board_count: int
    slots_per_board: int = 20
    tcp_station_base: int = 0  # 1 for A, 64 for B


class Amkn8702g:
    """AMKN8702G master controller communication via Modbus TCP."""

    def __init__(self, ip: str = None, port: int = None):
        self.ip = ip or settings.MASTER_IP
        self.port = port or settings.MASTER_PORT
        self.station = settings.MASTER_STATION  # always 200

        # Shelf configuration
        self.a_face = ShelfFace("A", board_count=0)
        self.b_face = ShelfFace("B", board_count=0)
        self.slots_per_board = settings.SLOT_BITS_PER_BOARD

        # Cached slot states
        self.slot_cache: dict[str, SlotStatus] = {}
        self.last_scan_time: Optional[float] = None
        self.scan_interval = settings.SLOT_POLL_INTERVAL

    def configure(self, a_boards: int, b_boards: int, slots_per_board: int = None):
        """Configure shelf geometry via config registers."""
        if slots_per_board:
            self.slots_per_board = slots_per_board

        self.a_face.board_count = a_boards
        self.b_face.board_count = b_boards

    def slot_tcp_address(self, face: str, board_number: int, slot_number: int) -> int:
        """Calculate TCP digital input address for a given slot.

        Address calculation per protocol:
          A-face board i (1-based): start = 1000 + (i-1) * slots_per_board
          B-face board i (1-based): start = 2000 + (i-1) * slots_per_board
          Address = start + (slot_number - 1)
        """
        base = 1000 if face == "A" else 2000
        return base + (board_number - 1) * self.slots_per_board + (slot_number - 1)

    def tcp_station(self, face: str, rtu_board_number: int) -> int:
        """Get TCP station ID for a physical board.

        A-face: TCP station = RTU board number (1-63)
        B-face: TCP station = RTU board number + 63 (64-126)
        """
        if face == "A":
            return rtu_board_number
        else:
            return rtu_board_number + 63

    def slot_key(self, face: str, board_number: int, slot_number: int) -> str:
        return f"{face}_{board_number}_{slot_number}"

    def parse_slot_bits(self, byte_data: bytes, face: str) -> list[SlotStatus]:
        """Parse raw coil bit data into SlotStatus objects.

        Bit mapping per byte:
          Byte N (covering slots k-8..k-1):
          Bit7=slot(k), Bit6=slot(k-1), ..., Bit0=slot(k-7)
          Data bit=1 means material present, 0 means empty.
        """
        slots = []
        byte_index = 0
        board_base = 1 if face == "A" else 1  # relative to face
        total_slots = (self.a_face.board_count if face == "A" else self.b_face.board_count) * self.slots_per_board

        for byte_val in byte_data:
            for bit_pos in range(8):
                slot_index = byte_index * 8 + bit_pos
                if slot_index >= total_slots:
                    break

                has_material = bool(byte_val & (1 << bit_pos))
                board_number = slot_index // self.slots_per_board + 1
                slot_number = slot_index % self.slots_per_board + 1
                face_letter = "A" if face == "A" else "B"

                key = self.slot_key(face_letter, board_number, slot_number)
                slot = SlotStatus(
                    board_number=board_number,
                    slot_number=slot_number,
                    has_material=has_material,
                )
                slots.append(slot)
                byte_index += 1

        return slots

    async def read_slot_status(self) -> dict[str, SlotStatus]:
        """Read all slot states from the shelf.

        Uses Modbus FC 02 (read coils) to read:
          A-face: 0x03E8 (1000) to 0x07CF (1999)
          B-face: 0x07D0 (2000) to 0x0BB7 (2999)
        """
        a_bytes = self.a_face.board_count * (self.slots_per_board + 7) // 8
        b_bytes = self.b_face.board_count * (self.slots_per_board + 7) // 8

        a_slots = []
        b_slots = []

        if a_bytes > 0:
            a_slots = await self._read_coils_face("A", 1000, a_bytes)

        if b_bytes > 0:
            b_slots = await self._read_coils_face("B", 2000, b_bytes)

        for s in a_slots + b_slots:
            self.slot_cache[self.slot_key(s.board_number, s.slot_number, s.slot_number)] = s

        return self.slot_cache

    async def _read_coils_face(self, face: str, start_addr: int, count: int) -> list[SlotStatus]:
        """Read coil data for one face via Modbus TCP FC02."""
        # Build Modbus TCP request frame for FC02 (read coils)
        # Format: [tid:2][pid:2][len:2][sid:1][fc:1][start_hi:1][start_lo:1][count_hi:1][count_lo:1]
        tid = 1
        pid = 0
        sid = self.station  # 200 = 0xC8
        fc = 0x02
        start_hi = (start_addr >> 8) & 0xFF
        start_lo = start_addr & 0xFF
        count_hi = (count >> 8) & 0xFF
        count_lo = count & 0xFF

        request = struct.pack(">HHBBBHHH", tid, pid, 6, sid, fc, start_hi, start_lo, count_hi, count_lo)

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.ip, self.port), timeout=5.0
            )
            writer.write(request)
            await writer.drain()

            # Read response
            resp = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            writer.close()
            await writer.wait_closed()

            if len(resp) < 9:
                return []

            # Parse response: [tid:2][pid:2][byte_count:1][fc:1][data...]
            byte_count = resp[4]
            data = resp[6:6 + byte_count]

            face_letter = "A" if face == "A" else "B"
            return self.parse_slot_bits(data, face_letter)

        except (asyncio.TimeoutError, ConnectionError, OSError):
            return []

    async def set_led(self, face: str, board_number: int, slot_number: int, color: LedColor):
        """Control LED for a specific slot using protocol 2.

        Protocol 2 (recommended):
        - Each LED uses 4 consecutive coil addresses starting from 10000:
          LEDnG = 10000 + 4*(n-1), LEDnR = 10000 + 4*(n-1) + 1,
          LEDnB = 10000 + 4*(n-1) + 2, LEDnControl = 10000 + 4*(n-1) + 3
        - Control bit = 1 means G/R/B bits are effective
        - Byte mapping: every 2 LEDs = 1 byte:
          Odd LED (G=Bit0, R=Bit1, B=Bit2), Even LED (G=Bit4, R=Bit5, B=Bit6)
          Control bits: Odd=Bit3, Even=Bit7
        - TCP station = tcp_station(face, board_number)
        - Write multiple coils FC15 to addresses 10000+
        """
        total_slots = self.slots_per_board
        led_index = (board_number - 1) * total_slots + (slot_number - 1)  # 0-based

        tcp_station = self.tcp_station(face, board_number)

        # Calculate byte array for protocol 2 LED control
        bytes_needed = (total_slots + 1) // 2  # 2 LEDs per byte

        # Build bytes for one board's LEDs
        bytes_arr = bytearray(bytes_needed)

        # For each slot on this board, set its LED
        for slot_idx in range(total_slots):
            n = slot_idx + 1  # 1-based LED number within board
            byte_idx = (n - 1) // 2
            is_odd = (n - 1) % 2 == 0

            if is_odd:
                ctrl_bit = 3
                g_bit, r_bit, b_bit = 0, 1, 2
            else:
                ctrl_bit = 7
                g_bit, r_bit, b_bit = 4, 5, 6

            # Clear all bits for this LED
            bytes_arr[byte_idx] &= ~(0b11111111)

            if slot_idx == slot_number - 1:
                # Set this specific slot's LED
                bytes_arr[byte_idx] |= (1 << ctrl_bit)  # control bit = 1 (effective)
                if color == LedColor.GREEN or color == LedColor.ON:
                    bytes_arr[byte_idx] |= (1 << g_bit)
                elif color == LedColor.RED:
                    bytes_arr[byte_idx] |= (1 << r_bit)
                elif color == LedColor.BLUE:
                    bytes_arr[byte_idx] |= (1 << b_bit)
                # Turn off others
                other_bits = [b for b in [g_bit, r_bit, b_bit] if b != ([g_bit, r_bit, b_bit][[LedColor.GREEN, LedColor.RED, LedColor.BLUE].index(color) if color != LedColor.OFF else 0])]
            else:
                # Other slots: set control bit = 0 (no change)
                bytes_arr[byte_idx] &= ~(1 << ctrl_bit)

        # Build FC15 (write multiple coils) request
        start_addr = 10000
        count = total_slots * 3  # 3 coils per LED
        # Simplify: write 80 coils for 20-slot board
        fc = 0x0F
        byte_count = bytes_needed

        # Pack request
        tid = 2
        pid = 0
        sid = tcp_station

        # PDU: [fc:1][start_hi:1][start_lo:1][count_hi:1][count_lo:1][byte_count:1][data...]
        pdu = struct.pack(">BHHHB", fc, start_addr, count, byte_count) + bytes(bytes_arr)
        pdu_len = 1 + 2 + 2 + 1 + len(bytes_arr)

        request = struct.pack(">HHH", tid, pid, pdu_len) + sid.to_bytes() + pdu

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.ip, self.port), timeout=3.0
            )
            writer.write(request)
            await writer.drain()
            await asyncio.wait_for(reader.read(1024), timeout=3.0)
            writer.close()
            await writer.wait_closed()
        except (asyncio.TimeoutError, ConnectionError, OSError):
            pass

    async def clear_leds(self, face: str, board_number: int):
        """Turn off all LEDs on a board."""
        total_coils = self.slots_per_board * 3
        tcp_station = self.tcp_station(face, board_number)

        tid = 3
        fc = 0x0F
        start_addr = 10000
        count = total_coils
        byte_count = (total_coils + 7) // 8

        pdu = struct.pack(">BHHHB", fc, start_addr, count, byte_count) + b'\x00' * byte_count
        pdu_len = 1 + 2 + 2 + 1 + byte_count

        request = struct.pack(">HHH", tid, 0, pdu_len) + tcp_station.to_bytes() + pdu

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.ip, self.port), timeout=3.0
            )
            writer.write(request)
            await writer.drain()
            await asyncio.wait_for(reader.read(1024), timeout=3.0)
            writer.close()
            await writer.wait_closed()
        except:
            pass

    async def set_relay(self, relay_number: int, on: bool):
        """Control relay K1-K6 (address 0x0000-0x0005, station 200).

        FC05: Write single coil. Data FF00 = ON, 0000 = OFF.
        """
        tid = 4
        addr = relay_number - 1
        data = 0xFF00 if on else 0x0000

        request = struct.pack(">HHHBBH", tid, 0, 6, self.station, 0x05, addr) + data.to_bytes(2)
        # Correct packing
        request = struct.pack(">HHH", tid, 0, 6) + bytes([self.station, 0x05, addr >> 8, addr & 0xFF, data >> 8, data & 0xFF])

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.ip, self.port), timeout=3.0
            )
            writer.write(request)
            await writer.drain()
            await asyncio.wait_for(reader.read(1024), timeout=3.0)
            writer.close()
            await writer.wait_closed()
        except:
            pass

    async def execute_command(self, command: int):
        """Send command to master via register 60121.

        Commands: 0=done/idle, 1=save, 2=firmware, 3=reboot, 4=calibrate, 5=reset
        """
        tid = 5
        addr = 60121
        value = command

        request = struct.pack(">HHH", tid, 0, 6) + bytes([self.station, 0x06, addr >> 8, addr & 0xFF, value >> 8, value & 0xFF])

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.ip, self.port), timeout=5.0
            )
            writer.write(request)
            await writer.drain()
            await asyncio.wait_for(reader.read(1024), timeout=5.0)
            writer.close()
            await writer.wait_closed()
        except:
            pass
