"""Hardware Debug API Router — endpoints for hardware debugging and diagnostics."""

import asyncio
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.hal.hardware_debugger import HardwareDebugger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hardware-debug", tags=["hardware-debug"])

# Global debugger instance (singleton)
_debugger: Optional[HardwareDebugger] = None


def get_debugger() -> HardwareDebugger:
    """Get or create the global debugger instance."""
    global _debugger
    if _debugger is None:
        _debugger = HardwareDebugger()
    return _debugger


# ── Request/Response models ──

class ConnectRequest(BaseModel):
    ip: str = Field("192.168.1.100", description="主控板 IP 地址")
    port: int = Field(502, description="Modbus TCP 端口")


class RelayControl(BaseModel):
    relay_num: int = Field(..., ge=1, le=6, description="继电器编号 K1-K6")
    on: bool = Field(..., description="True=开启, False=关闭")


class RegisterWrite(BaseModel):
    address: int = Field(..., ge=0, description="寄存器地址")
    value: int = Field(..., ge=0, le=65535, description="写入值 (0-65535)")
    station: Optional[int] = Field(200, description="Modbus 站号")


class RegisterRead(BaseModel):
    address: int = Field(..., ge=0, description="起始寄存器地址")
    count: int = Field(..., ge=1, le=100, description="读取数量")
    func_code: int = Field(3, ge=1, le=4, description="功能码 (3=保持寄存器, 4=输入寄存器)")
    station: Optional[int] = Field(200, description="Modbus 站号")


class CoilControl(BaseModel):
    address: int = Field(..., ge=0, description="线圈地址")
    on: bool = Field(..., description="True=ON, False=OFF")
    station: Optional[int] = Field(200, description="Modbus 站号")


class CoilBatchControl(BaseModel):
    address: int = Field(..., ge=0, description="起始线圈地址")
    values: List[bool] = Field(..., description="线圈值列表")
    station: Optional[int] = Field(200, description="Modbus 站号")


class DigitalInputRead(BaseModel):
    address: int = Field(..., ge=0, description="起始地址")
    count: int = Field(..., ge=1, le=100, description="读取数量")
    station: Optional[int] = Field(200, description="Modbus 站号")


class BoardLedControl(BaseModel):
    slot_num: int = Field(..., ge=1, le=20, description="储位编号 1-20")
    color: str = Field("green", description="颜色: off/green/red/blue")


class BoardAllLedControl(BaseModel):
    colors: List[str] = Field(..., description="20个储位的颜色列表")


class BoardSetJudgment(BaseModel):
    value: int = Field(..., ge=0, le=255, description="统一判定值")


# ── Connection endpoints ──

@router.get("/status")
async def get_status(debugger: HardwareDebugger = Depends(get_debugger)):
    """Get current connection status and debugger state."""
    return debugger.get_status()


@router.post("/connect")
async def connect(req: ConnectRequest,
                 debugger: HardwareDebugger = Depends(get_debugger)):
    """Connect to the main controller board."""
    result = await debugger.connect(ip=req.ip, port=req.port)
    return result


@router.post("/disconnect")
async def disconnect(debugger: HardwareDebugger = Depends(get_debugger)):
    """Disconnect from the main controller board."""
    try:
        result = await debugger.disconnect()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Mainboard endpoints ──

@router.get("/mainboard/info")
async def read_mainboard_info(debugger: HardwareDebugger = Depends(get_debugger)):
    """Read main controller board device info."""
    try:
        info = await debugger.read_device_info()
        return {'success': True, 'data': info}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mainboard/config")
async def read_mainboard_config(debugger: HardwareDebugger = Depends(get_debugger)):
    """Read main controller configuration registers."""
    try:
        config = await debugger.read_config_registers()
        return {'success': True, 'data': config}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mainboard/relays")
async def read_relays(debugger: HardwareDebugger = Depends(get_debugger)):
    """Read relay states K1-K6."""
    try:
        relays = await debugger.read_relays()
        return {'success': True, 'data': relays}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mainboard/relay")
async def set_relay(req: RelayControl,
                    debugger: HardwareDebugger = Depends(get_debugger)):
    """Control a relay K1-K6."""
    try:
        await debugger.set_relay(req.relay_num, req.on)
        return {'success': True, 'message': f"K{req.relay_num} → {'ON' if req.on else 'OFF'}"}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mainboard/calibrate")
async def calibrate_mainboard(debugger: HardwareDebugger = Depends(get_debugger)):
    """Trigger global calibration on main controller."""
    try:
        await debugger.mainboard_calibrate()
        return {'success': True, 'message': '校准命令已发送'}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mainboard/reset")
async def reset_mainboard(debugger: HardwareDebugger = Depends(get_debugger)):
    """Reset the main controller board."""
    try:
        await debugger.mainboard_reset()
        return {'success': True, 'message': '复位命令已发送，连接将断开'}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mainboard/save-config")
async def save_config(debugger: HardwareDebugger = Depends(get_debugger)):
    """Save configuration to main controller."""
    try:
        await debugger.mainboard_save_config()
        return {'success': True, 'message': '配置已保存'}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Raw Modbus operations (register/coil browser) ──

@router.post("/read-registers")
async def read_registers(req: RegisterRead,
                         debugger: HardwareDebugger = Depends(get_debugger)):
    """Read Modbus registers (FC 3 or 4)."""
    try:
        values = await debugger.read_registers(
            req.address, req.count, req.func_code, req.station
        )
        return {'success': True, 'data': values}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/write-register")
async def write_register(req: RegisterWrite,
                         debugger: HardwareDebugger = Depends(get_debugger)):
    """Write a single Modbus register (FC 6)."""
    try:
        await debugger.write_register(req.address, req.value, req.station)
        return {'success': True, 'message': f'寄存器 {req.address} = 0x{req.value:04X}'}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/read-coils")
async def read_coils(req: DigitalInputRead,
                     debugger: HardwareDebugger = Depends(get_debugger)):
    """Read Modbus coils (FC 1)."""
    try:
        values = await debugger.read_coils(req.address, req.count, req.station)
        return {'success': True, 'data': values}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/write-coil")
async def write_coil(req: CoilControl,
                     debugger: HardwareDebugger = Depends(get_debugger)):
    """Write a single Modbus coil (FC 5)."""
    try:
        await debugger.write_coil(req.address, req.on, req.station)
        return {'success': True, 'message': f'线圈 {req.address} → {"ON" if req.on else "OFF"}'}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/write-coils")
async def write_coils(req: CoilBatchControl,
                      debugger: HardwareDebugger = Depends(get_debugger)):
    """Write multiple Modbus coils (FC 15)."""
    try:
        await debugger.write_coils(req.address, req.values, req.station)
        return {'success': True, 'message': f'批量写入 {len(req.values)} 个线圈'}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/read-digital-inputs")
async def read_digital_inputs(req: DigitalInputRead,
                              debugger: HardwareDebugger = Depends(get_debugger)):
    """Read digital inputs (FC 2)."""
    try:
        values = await debugger.read_digital_inputs(req.address, req.count, req.station)
        return {'success': True, 'data': values}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── LED Board endpoints ──

@router.get("/boards")
async def list_boards(debugger: HardwareDebugger = Depends(get_debugger)):
    """List all LED boards (from cache/config)."""
    a_count = debugger.a_boards
    b_count = debugger.b_boards

    boards = []
    for i in range(1, a_count + 1):
        boards.append({
            'station': i,
            'side': 'A',
            'board_addr': i,
            'tcp_station': i,
            'label': f'A{i} (站号 {i})',
        })
    for i in range(1, b_count + 1):
        tcp_station = i + 63
        boards.append({
            'station': tcp_station,
            'side': 'B',
            'board_addr': i,
            'tcp_station': tcp_station,
            'label': f'B{i} (站号 {tcp_station})',
        })

    return {
        'success': True,
        'data': {
            'a_boards': a_count,
            'b_boards': b_count,
            'slots_per_board': debugger.slots_per_board,
            'boards': boards,
        }
    }


@router.get("/boards/{station}/info")
async def read_board_info(station: int,
                          debugger: HardwareDebugger = Depends(get_debugger)):
    """Read a LED board's information."""
    try:
        info = await debugger.read_board_info(station)
        return {'success': True, 'data': info}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/boards/{station}/slots")
async def read_board_slots(
    station: int,
    slot_count: int = Query(20, ge=1, le=20),
    debugger: HardwareDebugger = Depends(get_debugger),
):
    """Read slot states for a LED board."""
    try:
        slots = await debugger.read_board_slots(station, slot_count)
        return {'success': True, 'data': slots}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/boards/{station}/ad-values")
async def read_board_ad_values(station: int,
                               debugger: HardwareDebugger = Depends(get_debugger)):
    """Read AD sampling values for a LED board."""
    try:
        values = await debugger.read_board_ad_values(station)

        # Format as named slots
        slots = {}
        for i, v in enumerate(values):
            # Each register contains 2 channels (high byte = ch1, low byte = ch2)
            ch1 = (v >> 8) & 0xFF
            ch2 = v & 0xFF
            slot_idx = i * 2 + 1
            slots[f'slot_{slot_idx}'] = ch1
            if slot_idx + 1 <= 20:
                slots[f'slot_{slot_idx + 1}'] = ch2

        return {'success': True, 'data': slots}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/boards/{station}/calibration")
async def read_board_calibration(station: int,
                                 debugger: HardwareDebugger = Depends(get_debugger)):
    """Read calibration + judgment values for a LED board."""
    try:
        cal = await debugger.read_board_calibration(station)
        return {'success': True, 'data': cal}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/boards/{station}/led")
async def control_board_led(station: int, req: BoardLedControl,
                            debugger: HardwareDebugger = Depends(get_debugger)):
    """Control a single LED on a board."""
    try:
        await debugger.control_board_led(station, req.slot_num, req.color)
        return {'success': True, 'message': f'储位 {req.slot_num} → {req.color.upper()}'}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/boards/{station}/led-all")
async def control_board_all_leds(station: int, req: BoardAllLedControl,
                                 debugger: HardwareDebugger = Depends(get_debugger)):
    """Control all LEDs on a board."""
    try:
        await debugger.control_board_all_leds(station, req.colors)
        return {'success': True, 'message': '全部LED已设置'}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/boards/{station}/led-test")
async def led_test_sequence(station: int,
                            debugger: HardwareDebugger = Depends(get_debugger)):
    """Run LED test sequence on a board."""
    try:
        # Run in background to avoid timeout
        asyncio.create_task(debugger.led_test_sequence(station))
        return {'success': True, 'message': 'LED测试序列已启动 (绿→红→蓝→灭)'}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/boards/{station}/calibrate")
async def calibrate_board(station: int,
                          debugger: HardwareDebugger = Depends(get_debugger)):
    """Calibrate a LED board."""
    try:
        await debugger.calibrate_board(station)
        return {'success': True, 'message': '校准命令已发送'}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/boards/{station}/reset")
async def reset_board(station: int,
                      debugger: HardwareDebugger = Depends(get_debugger)):
    """Reset a LED board."""
    try:
        await debugger.reset_board(station)
        return {'success': True, 'message': '复位命令已发送'}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/boards/{station}/set-judgment")
async def set_board_judgment(station: int, req: BoardSetJudgment,
                             debugger: HardwareDebugger = Depends(get_debugger)):
    """Set uniform judgment value for a board."""
    try:
        await debugger.set_board_judgment(station, req.value)
        return {'success': True, 'message': f'判定值设为 {req.value} (约 {req.value * 0.0196:.3f}V)'}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Log endpoints ──

@router.get("/logs")
async def get_logs(
    since: float = Query(0, description="起始时间戳"),
    level: str = Query(None, description="过滤级别: info/warn/error/debug"),
    limit: int = Query(200, ge=1, le=1000),
    debugger: HardwareDebugger = Depends(get_debugger),
):
    """Get debug log entries."""
    logs = debugger.get_logs(since=since, level=level, limit=limit)
    return {'success': True, 'data': logs}


@router.post("/logs/clear")
async def clear_logs(debugger: HardwareDebugger = Depends(get_debugger)):
    """Clear all debug log entries."""
    debugger.clear_logs()
    return {'success': True, 'message': '日志已清除'}


# ── Ping ──

@router.get("/ping")
async def ping(debugger: HardwareDebugger = Depends(get_debugger)):
    """Quick connection test (ping)."""
    try:
        result = await debugger.ping()
        return result
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── A/B面主控轮询储位 (直接从主控板读) ──

@router.get("/mainboard/slots")
async def read_mainboard_slots(
    face: str = Query('A', description="A 或 B"),
    count: int = Query(700, ge=1, le=1000),
    debugger: HardwareDebugger = Depends(get_debugger),
):
    """Read slot states from main controller's cached digital inputs."""
    try:
        master = debugger._require_master()
        base_addr = 0x03E8 if face.upper() == 'A' else 0x07D0
        resp = await master.execute(2, base_addr, count)
        if resp and len(resp) > 8:
            byte_count = resp[7]
            data = resp[8:8 + byte_count]
            slots = {}
            for i in range(count):
                byte_idx = i // 8
                bit_idx = i % 8
                has_mat = bool(data[byte_idx] & (1 << bit_idx)) if byte_idx < len(data) else False
                board = i // debugger.slots_per_board + 1
                slot = i % debugger.slots_per_board + 1
                slots[f'{face}{board}-{slot}'] = has_mat
            return {'success': True, 'data': slots}
        return {'success': True, 'data': {}}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
