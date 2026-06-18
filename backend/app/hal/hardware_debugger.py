"""Hardware Debugger — wraps Amkn8702g with debug logging and connection management."""

import struct
import asyncio
import logging
import time
from collections import deque
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

from app.hal.modbus import Amkn8702g, LedColor

logger = logging.getLogger(__name__)


@dataclass
class DebugLogEntry:
    """Single debug log entry."""
    timestamp: float
    level: str  # 'info', 'warn', 'error', 'debug'
    source: str  # e.g. 'connect', 'read_registers', 'set_led', 'system'
    message: str
    data: Optional[Dict[str, Any]] = None


class HardwareDebugger:
    """Hardware debug interface — wraps Amkn8702g with comprehensive logging.

    Maintains its own Amkn8702g instance separate from the production
    LED service, so debug operations don't interfere with the running system.
    """

    MAX_LOG_ENTRIES = 1000

    def __init__(self):
        self._master: Optional[Amkn8702g] = None
        self._log: deque = deque(maxlen=self.MAX_LOG_ENTRIES)
        self._connected: bool = False
        self._ip: str = ""
        self._port: int = 502
        self._station: int = 200
        self._last_connect_attempt: float = 0
        self._connect_error: Optional[str] = None

        # Cache for board topology
        self.a_boards: int = 0
        self.b_boards: int = 0
        self.slots_per_board: int = 20

        # Event for log polling
        self._log_event = asyncio.Event()

    # ── Log management ──

    def _add_log(self, level: str, source: str, message: str, data: dict = None):
        """Add a log entry."""
        entry = DebugLogEntry(
            timestamp=time.time(),
            level=level,
            source=source,
            message=message,
            data=data,
        )
        self._log.append(entry)
        self._log_event.set()

    def get_logs(self, since: float = 0, level: str = None,
                 limit: int = 200) -> List[Dict[str, Any]]:
        """Get log entries, optionally filtered."""
        result = []
        for entry in list(self._log):
            if entry.timestamp < since:
                continue
            if level and entry.level != level:
                continue
            result.append({
                'timestamp': entry.timestamp,
                'level': entry.level,
                'source': entry.source,
                'message': entry.message,
                'data': entry.data,
            })
            if len(result) >= limit:
                break
        return result

    def clear_logs(self):
        """Clear all log entries."""
        self._log.clear()
        self._add_log('info', 'system', '日志已清除')

    # ── Connection management ──

    async def connect(self, ip: str = None, port: int = None) -> Dict[str, Any]:
        """Connect to the AMKN8702G controller."""
        if ip:
            self._ip = ip
        if port:
            self._port = port

        self._last_connect_attempt = time.time()

        # Disconnect previous if any
        if self._master:
            try:
                await self._master.disconnect()
            except Exception:
                pass

        self._master = Amkn8702g(self._ip, self._port, self._station)
        self._add_log('info', 'connect',
                      f"正在连接 {self._ip}:{self._port}...")

        try:
            ok = await self._master.connect()
            if ok:
                self._connected = True
                self._connect_error = None
                self._add_log('info', 'connect',
                              f"连接成功 {self._ip}:{self._port}")

                # Try to read device info to verify communication
                try:
                    info = await self._master.get_device_info()
                    if info:
                        self._add_log('info', 'connect',
                                      "设备信息读取成功", info)
                except Exception as e:
                    self._add_log('warn', 'connect',
                                  f"设备信息读取失败: {e}")

                return {'success': True, 'message': f'连接成功', 'ip': self._ip, 'port': self._port}
            else:
                self._connected = False
                self._connect_error = f"连接超时或拒绝"
                self._add_log('error', 'connect',
                              f"连接失败: {self._connect_error}")
                return {'success': False, 'message': self._connect_error}
        except Exception as e:
            self._connected = False
            self._connect_error = str(e)
            self._add_log('error', 'connect', f"连接异常: {e}")
            return {'success': False, 'message': str(e)}

    async def disconnect(self) -> Dict[str, Any]:
        """Disconnect from the controller."""
        if self._master:
            try:
                await self._master.disconnect()
            except Exception as e:
                self._add_log('warn', 'disconnect', f"断开时发生异常: {e}")
        self._connected = False
        self._master = None
        self._add_log('info', 'disconnect', "已断开连接")
        return {'success': True, 'message': '已断开连接'}

    async def ensure_connected(self) -> bool:
        """Ensure connection is alive, reconnect if needed."""
        if not self._master or not self._connected:
            self._add_log('warn', 'connection', "连接已断开，尝试重连...")
            result = await self.connect()
            return result.get('success', False)

        # Test connection with a quick read
        try:
            test = await self._master.execute(3, 60000, 1)
            if test is None:
                raise ConnectionError("No response from device")
            return True
        except Exception as e:
            self._connected = False
            self._add_log('error', 'connection', f"连接检测失败: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get current connection status."""
        return {
            'connected': self._connected,
            'ip': self._ip,
            'port': self._port,
            'station': self._station,
            'last_connect_attempt': self._last_connect_attempt,
            'connect_error': self._connect_error,
            'a_boards': self.a_boards,
            'b_boards': self.b_boards,
            'slots_per_board': self.slots_per_board,
        }

    # ── Helper: ensure Amkn8702g is available ──

    def _require_master(self) -> Amkn8702g:
        if not self._master or not self._connected:
            raise ConnectionError("未连接到主控板，请先连接")
        return self._master

    # ── Mainboard operations ──

    async def read_device_info(self) -> Dict[str, Any]:
        """Read all device info registers."""
        master = self._require_master()
        result = {}

        # Read status registers 60000-60021
        try:
            resp = await master.execute(3, 60000, 22)
            if resp and len(resp) > 10:
                data = resp[8:8 + 44]  # 22 registers × 2 bytes
                if len(data) >= 44:
                    result['device_mode'] = struct.unpack('>H', data[0:2])[0]
                    result['station_addr'] = struct.unpack('>H', data[2:4])[0]
                    result['hw_sw_version'] = struct.unpack('>H', data[4:6])[0]
                    result['model_name'] = data[16:32].decode('ascii', errors='replace').strip('\x00')
                    uptime_high = struct.unpack('>H', data[32:34])[0]
                    uptime_low = struct.unpack('>H', data[34:36])[0]
                    result['uptime_seconds'] = (uptime_high << 16) | uptime_low
                    comm_high = struct.unpack('>H', data[36:38])[0]
                    comm_low = struct.unpack('>H', data[38:40])[0]
                    result['total_communications'] = (comm_high << 16) | comm_low
                    result['error_count'] = struct.unpack('>H', data[40:42])[0]
                    voltage_raw = struct.unpack('>H', data[42:44])[0]
                    result['voltage'] = round(voltage_raw / 100.0, 2)

                    # Parse device mode bits
                    mode = result['device_mode']
                    result['is_tcp'] = bool(mode & (1 << 15))
                    result['config_mode'] = bool(mode & (1 << 14))
                    result['eth_enabled'] = bool(mode & (1 << 13))
                    result['wifi_enabled'] = bool(mode & (1 << 12))
                    result['com1_enabled'] = bool(mode & (1 << 10))  # A面
                    result['com2_enabled'] = bool(mode & (1 << 9))   # B面
                    result['has_error'] = bool(mode & (1 << 1))
                    result['is_busy'] = bool(mode & (1 << 0))

                    self._add_log('info', 'read_device_info',
                                  "设备信息读取成功", result)
        except Exception as e:
            self._add_log('error', 'read_device_info', f"读取失败: {e}")
            raise

        return result

    async def read_relays(self) -> Dict[str, bool]:
        """Read relay states K1-K6."""
        master = self._require_master()
        try:
            resp = await master.execute(1, 0x0000, 6)
            if resp and len(resp) > 8:
                byte_count = resp[7]
                data = resp[8:8 + byte_count] if byte_count > 0 else b''
                relays = {}
                if data:
                    byte_val = data[0]
                    for i in range(6):
                        relays[f'K{i + 1}'] = bool(byte_val & (1 << i))
                self._add_log('info', 'read_relays', "继电器状态读取成功", relays)
                return relays
            return {}
        except Exception as e:
            self._add_log('error', 'read_relays', f"读取失败: {e}")
            raise

    async def set_relay(self, relay_num: int, on: bool) -> bool:
        """Set relay K1-K6."""
        master = self._require_master()
        try:
            await master.set_relay(relay_num, on)
            self._add_log('info', 'set_relay',
                          f"继电器 K{relay_num} → {'ON' if on else 'OFF'}")
            return True
        except Exception as e:
            self._add_log('error', 'set_relay', f"设置失败: {e}")
            raise

    async def read_config_registers(self) -> Dict[str, Any]:
        """Read shelf configuration registers."""
        master = self._require_master()
        result = {}
        try:
            # Read registers 60107-60109 (shelf type, A boards, B boards)
            resp = await master.execute(3, 60107, 3)
            if resp and len(resp) > 8:
                data = resp[8:8 + 6]
                if len(data) >= 6:
                    result['shelf_type'] = struct.unpack('>H', data[0:2])[0]
                    result['a_boards'] = struct.unpack('>H', data[2:4])[0]
                    result['b_boards'] = struct.unpack('>H', data[4:6])[0]
                    self.a_boards = result['a_boards']
                    self.b_boards = result['b_boards']

            # Read network config
            resp = await master.execute(3, 60045, 12)
            if resp and len(resp) > 8:
                data = resp[8:8 + 24]
                if len(data) >= 24:
                    ip_parts = [
                        struct.unpack('>H', data[0:2])[0] >> 8,
                        struct.unpack('>H', data[0:2])[0] & 0xFF,
                        struct.unpack('>H', data[2:4])[0] >> 8,
                        struct.unpack('>H', data[2:4])[0] & 0xFF,
                    ]
                    result['ip'] = '.'.join(str(p) for p in ip_parts)
                    result['port'] = struct.unpack('>H', data[4:6])[0]

            self._add_log('info', 'read_config', "配置寄存器读取成功", result)
        except Exception as e:
            self._add_log('error', 'read_config', f"读取失败: {e}")
            raise
        return result

    async def write_register(self, addr: int, value: int,
                             station: int = None) -> bool:
        """Write a single Modbus register."""
        master = self._require_master()
        try:
            data = struct.pack('>H', value)
            await master.execute(6, addr, data=data, station=station)
            self._add_log('info', 'write_register',
                          f"写入寄存器 {addr} = 0x{value:04X} ({value})",
                          {'address': addr, 'value': value, 'station': station or 200})
            return True
        except Exception as e:
            self._add_log('error', 'write_register', f"写入失败: {e}")
            raise

    async def read_registers(self, addr: int, count: int,
                             func_code: int = 3,
                             station: int = None) -> List[int]:
        """Read Modbus registers."""
        master = self._require_master()
        try:
            resp = await master.execute(func_code, addr, count, station=station)
            if resp and len(resp) > 8:
                byte_count = resp[7]
                data = resp[8:8 + byte_count]
                values = []
                for i in range(0, len(data), 2):
                    if i + 1 < len(data):
                        values.append(struct.unpack('>H', data[i:i + 2])[0])
                self._add_log('info', 'read_registers',
                              f"读取寄存器 {addr}~{addr + count - 1} ({func_code=})",
                              {'address': addr, 'count': count, 'values': values,
                               'station': station or 200})
                return values
            return []
        except Exception as e:
            self._add_log('error', 'read_registers', f"读取失败: {e}")
            raise

    async def read_coils(self, addr: int, count: int,
                         station: int = None) -> List[bool]:
        """Read Modbus coils (FC 1)."""
        master = self._require_master()
        try:
            resp = await master.execute(1, addr, count, station=station)
            if resp and len(resp) > 8:
                byte_count = resp[7]
                data = resp[8:8 + byte_count]
                coils = []
                for i in range(count):
                    byte_idx = i // 8
                    bit_idx = i % 8
                    if byte_idx < len(data):
                        coils.append(bool(data[byte_idx] & (1 << bit_idx)))
                    else:
                        coils.append(False)
                self._add_log('info', 'read_coils',
                              f"读取线圈 {addr}~{addr + count - 1}",
                              {'address': addr, 'count': count, 'values': coils,
                               'station': station or 200})
                return coils
            return []
        except Exception as e:
            self._add_log('error', 'read_coils', f"读取失败: {e}")
            raise

    async def write_coil(self, addr: int, on: bool,
                         station: int = None) -> bool:
        """Write a single Modbus coil (FC 5)."""
        master = self._require_master()
        try:
            val = 0xFF00 if on else 0x0000
            await master.execute(5, addr, data=struct.pack('>H', val),
                                 station=station)
            self._add_log('info', 'write_coil',
                          f"写入线圈 {addr} = {'ON' if on else 'OFF'}",
                          {'address': addr, 'value': on, 'station': station or 200})
            return True
        except Exception as e:
            self._add_log('error', 'write_coil', f"写入失败: {e}")
            raise

    async def write_coils(self, addr: int, values: List[bool],
                          station: int = None) -> bool:
        """Write multiple Modbus coils (FC 15)."""
        master = self._require_master()
        try:
            count = len(values)
            byte_count = (count + 7) // 8
            bytes_arr = bytearray(byte_count)
            for i, v in enumerate(values):
                if v:
                    bytes_arr[i // 8] |= (1 << (i % 8))
            await master.execute(15, addr, count, bytes(bytes_arr),
                                 station=station)
            self._add_log('info', 'write_coils',
                          f"批量写入线圈 {addr}~{addr + count - 1}",
                          {'address': addr, 'count': count, 'station': station or 200})
            return True
        except Exception as e:
            self._add_log('error', 'write_coils', f"写入失败: {e}")
            raise

    async def read_digital_inputs(self, addr: int, count: int,
                                  station: int = None) -> List[bool]:
        """Read digital inputs (FC 2)."""
        master = self._require_master()
        try:
            resp = await master.execute(2, addr, count, station=station)
            if resp and len(resp) > 8:
                byte_count = resp[7]
                data = resp[8:8 + byte_count]
                inputs = []
                for i in range(count):
                    byte_idx = i // 8
                    bit_idx = i % 8
                    if byte_idx < len(data):
                        inputs.append(bool(data[byte_idx] & (1 << bit_idx)))
                    else:
                        inputs.append(False)
                return inputs
            return []
        except Exception as e:
            self._add_log('error', 'read_inputs', f"读取失败: {e}")
            raise

    # ── LED Board operations ──

    async def read_board_info(self, station: int) -> Dict[str, Any]:
        """Read a LED board's information registers (FC 4, addr 0x0028~0x002C)."""
        master = self._require_master()
        result = {}
        try:
            # Read 5 board info registers (addr 0x28-0x2C)
            resp = await master.execute(4, 0x0028, 5, station=station)
            if resp and len(resp) > 8:
                data = resp[8:8 + 10]
                if len(data) >= 10:
                    result['model'] = data[0:2].decode('ascii', errors='replace')
                    result['channel_count'] = data[1]  # 0x14=20, 0x0A=10, 0x06=6
                    result['hw_version_raw'] = struct.unpack('>H', data[2:4])[0]
                    result['sw_version_raw'] = struct.unpack('>H', data[4:6])[0]
                    result['hw_version'] = f"V{(data[2] >> 4)}.{data[2] & 0x0F}"
                    result['sw_version'] = f"V{(data[4] >> 4)}.{data[4] & 0x0F}"
                    result['compile_year'] = struct.unpack('>H', data[6:8])[0]
                    month = data[8] >> 4
                    day = data[8] & 0x0F
                    result['compile_date'] = f"{result['compile_year']}-{month:02d}-{day:02d}"

            # Also try reading model string from register 0x28
            # For AMKN7141, addr 0x28=model, 0x29=hw_ver, 0x2A=sw_ver, etc.
            self._add_log('info', 'read_board_info',
                          f"灯板 (站号 {station}) 信息读取成功", result)
        except Exception as e:
            self._add_log('error', 'read_board_info',
                          f"灯板 (站号 {station}) 信息读取失败: {e}")
            raise
        return result

    async def read_board_ad_values(self, station: int) -> List[int]:
        """Read AD sampling values for a board (FC 4, addr 0x0000~0x0009)."""
        master = self._require_master()
        try:
            resp = await master.execute(4, 0x0000, 10, station=station)
            if resp and len(resp) > 8:
                data = resp[8:8 + 20]
                values = []
                for i in range(0, len(data), 2):
                    if i + 1 < len(data):
                        values.append(struct.unpack('>H', data[i:i + 2])[0])
                return values
            return []
        except Exception as e:
            self._add_log('error', 'read_ad_values',
                          f"灯板 (站号 {station}) AD值读取失败: {e}")
            raise

    async def read_board_calibration(self, station: int) -> Dict[str, Any]:
        """Read calibration + judgment values for a board."""
        master = self._require_master()
        result = {}
        try:
            # Calibration values: FC 4, addr 0x000A~0x0013 (10 registers)
            resp = await master.execute(4, 0x000A, 10, station=station)
            if resp and len(resp) > 8:
                data = resp[8:8 + 20]
                cal_values = []
                for i in range(0, len(data), 2):
                    if i + 1 < len(data):
                        cal_values.append(struct.unpack('>H', data[i:i + 2])[0])
                result['calibration'] = cal_values

            # Judgment values: FC 4, addr 0x0014~0x001D (10 registers)
            resp = await master.execute(4, 0x0014, 10, station=station)
            if resp and len(resp) > 8:
                data = resp[8:8 + 20]
                judge_values = []
                for i in range(0, len(data), 2):
                    if i + 1 < len(data):
                        judge_values.append(struct.unpack('>H', data[i:i + 2])[0])
                result['judgment'] = judge_values

            # Delay values: FC 4, addr 0x001E~0x0027 (10 registers)
            resp = await master.execute(4, 0x001E, 10, station=station)
            if resp and len(resp) > 8:
                data = resp[8:8 + 20]
                delay_values = []
                for i in range(0, len(data), 2):
                    if i + 1 < len(data):
                        delay_values.append(struct.unpack('>H', data[i:i + 2])[0])
                result['delay'] = delay_values

            self._add_log('info', 'read_calibration',
                          f"灯板 (站号 {station}) 校准值读取成功")
        except Exception as e:
            self._add_log('error', 'read_calibration',
                          f"灯板 (站号 {station}) 校准值读取失败: {e}")
            raise
        return result

    async def read_board_slots(self, station: int,
                               slot_count: int = 20) -> Dict[str, Any]:
        """Read slot states for a specific LED board."""
        master = self._require_master()
        try:
            # Read digital inputs (FC 2, addr 0x0000, count=slot_count)
            resp = await master.execute(2, 0x0000, slot_count, station=station)
            slots = {}
            if resp and len(resp) > 8:
                byte_count = resp[7]
                data = resp[8:8 + byte_count]
                for i in range(slot_count):
                    byte_idx = i // 8
                    bit_idx = i % 8
                    has_material = bool(data[byte_idx] & (1 << bit_idx)) if byte_idx < len(data) else False
                    slots[f'slot_{i + 1}'] = has_material

            return {
                'station': station,
                'slot_count': slot_count,
                'slots': slots,
            }
        except Exception as e:
            self._add_log('error', 'read_board_slots',
                          f"灯板 (站号 {station}) 储位读取失败: {e}")
            raise

    async def control_board_led(self, station: int, slot_num: int,
                                color: str) -> bool:
        """Control a single LED on a board."""
        master = self._require_master()

        # Map color string to LedColor enum
        color_map = {
            'off': LedColor.OFF,
            'green': LedColor.GREEN,
            'red': LedColor.RED,
            'blue': LedColor.BLUE,
        }
        led_color = color_map.get(color.lower(), LedColor.GREEN)

        # Determine face and board_addr from station
        face = 'A' if station <= 63 else 'B'
        board_addr = station if face == 'A' else station - 63

        try:
            await master.set_led(face, board_addr, slot_num, led_color)
            self._add_log('info', 'control_led',
                          f"灯板 (站号 {station}) 储位 {slot_num} → {color.upper()}")
            return True
        except Exception as e:
            self._add_log('error', 'control_led', f"LED控制失败: {e}")
            raise

    async def control_board_all_leds(self, station: int,
                                     colors: List[str]) -> bool:
        """Control all LEDs on a board at once.

        Args:
            station: TCP station number
            colors: List of 20 color strings ('off', 'green', 'red', 'blue')
        """
        master = self._require_master()
        face = 'A' if station <= 63 else 'B'
        board_addr = station if face == 'A' else station - 63

        color_map = {
            'off': LedColor.OFF,
            'green': LedColor.GREEN,
            'red': LedColor.RED,
            'blue': LedColor.BLUE,
        }

        try:
            for i, color_str in enumerate(colors):
                if i >= 20:
                    break
                slot_num = i + 1
                led_color = color_map.get(color_str.lower(), LedColor.OFF)
                await master.set_led(face, board_addr, slot_num, led_color)
                await asyncio.sleep(0.05)  # Small delay to avoid flooding
            self._add_log('info', 'control_all_leds',
                          f"灯板 (站号 {station}) 全部LED已设置")
            return True
        except Exception as e:
            self._add_log('error', 'control_all_leds', f"批量LED控制失败: {e}")
            raise

    async def calibrate_board(self, station: int) -> bool:
        """Send calibration command to a board."""
        master = self._require_master()
        try:
            # Write command 0x5AA6 to register 0x0000
            await master.execute(6, 0x0000, data=struct.pack('>H', 0x5AA6),
                                 station=station)
            self._add_log('info', 'calibrate',
                          f"灯板 (站号 {station}) 校准命令已发送")
            return True
        except Exception as e:
            self._add_log('error', 'calibrate', f"校准失败: {e}")
            raise

    async def reset_board(self, station: int) -> bool:
        """Send reset command to a board."""
        master = self._require_master()
        try:
            await master.execute(6, 0x0000, data=struct.pack('>H', 0x5AA5),
                                 station=station)
            self._add_log('info', 'reset',
                          f"灯板 (站号 {station}) 复位命令已发送")
            return True
        except Exception as e:
            self._add_log('error', 'reset', f"复位失败: {e}")
            raise

    async def set_board_judgment(self, station: int,
                                 value: int) -> bool:
        """Set uniform judgment value for a board."""
        master = self._require_master()
        try:
            # Write multi registers: addr 0 = command 0x5AA8, addr 1 = value
            data = struct.pack('>HH', 0x5AA8, value)
            await master.execute(16, 0x0000, 2, data, station=station)
            self._add_log('info', 'set_judgment',
                          f"灯板 (站号 {station}) 判定值设为 {value}")
            return True
        except Exception as e:
            self._add_log('error', 'set_judgment', f"设置判定值失败: {e}")
            raise

    async def mainboard_calibrate(self) -> bool:
        """Trigger global calibrate from main controller."""
        master = self._require_master()
        try:
            await master.calibrate()
            self._add_log('info', 'mainboard_calibrate', "主控板校准命令已发送")
            return True
        except Exception as e:
            self._add_log('error', 'mainboard_calibrate', f"校准失败: {e}")
            raise

    async def mainboard_reset(self) -> bool:
        """Reset the main controller."""
        master = self._require_master()
        try:
            await master.reset()
            self._add_log('info', 'mainboard_reset', "主控板复位命令已发送")
            self._connected = False
            return True
        except Exception as e:
            self._add_log('error', 'mainboard_reset', f"复位失败: {e}")
            raise

    async def mainboard_save_config(self) -> bool:
        """Save configuration to main controller."""
        master = self._require_master()
        try:
            await master.execute(6, master.REG_DEVICE_COMMAND,
                                 data=struct.pack('>H', master.CMD_SAVE))
            self._add_log('info', 'mainboard_save', "配置已保存")
            return True
        except Exception as e:
            self._add_log('error', 'mainboard_save', f"保存失败: {e}")
            raise

    async def led_test_sequence(self, station: int) -> bool:
        """Run a test sequence on a board (all LEDs green → red → blue → off)."""
        for color in ['green', 'red', 'blue', 'off']:
            for slot in range(1, 21):
                try:
                    await self.control_board_led(station, slot, color)
                except Exception:
                    pass
                await asyncio.sleep(0.03)
            await asyncio.sleep(0.5)
        self._add_log('info', 'led_test', f"灯板 (站号 {station}) 测试序列完成")
        return True

    async def ping(self) -> Dict[str, Any]:
        """Quick connection test."""
        start = time.time()
        try:
            if self._master and self._connected:
                resp = await self._master.execute(3, 60000, 1)
                rtt = (time.time() - start) * 1000
                if resp:
                    return {'success': True, 'rtt_ms': round(rtt, 1)}
            return {'success': False, 'rtt_ms': None}
        except Exception as e:
            return {'success': False, 'rtt_ms': None, 'error': str(e)}
