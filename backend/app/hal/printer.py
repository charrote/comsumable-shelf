"""ZPL label printer HAL — network TCP direct connection.

Label format (SMT Reel):

    ┌─────────────────────────────────┐
    │  内部料号: RES-0402-1001         │
    │  客户料号: CUST-ABC-12345        │
    │  Reel: #1024                    │
    │  QTY: 3000                      │
    │  ═════════════════════════════  │
    │  [Barcode: material_code]       │
    └─────────────────────────────────┘
"""

import asyncio
import logging

from app.config import settings

logger = logging.getLogger(__name__)


def build_zpl(
    material_code: str,
    material_name: str,
    quantity: float,
    customer_material_code: str = "",
    reel_barcode: str = "",
) -> str:
    """Build ZPL label for SMT reel with internal + customer info.

    Args:
        material_code: Internal material code (系统内部料号)
        material_name: Material description (物料名称)
        quantity: Remaining quantity on reel (盘数量)
        customer_material_code: Customer's material code (客户料号, optional)
        reel_barcode: System reel ID / barcode (Reel编码, optional)

    Returns:
        ZPL string ready to send to printer.
    """
    qty_str = f"{quantity:.0f}" if quantity == int(quantity) else f"{quantity}"

    # Build label lines (font size 35 for info, 50 for main code)
    lines = [
        "^XA",
        "^CF0,35",
        f"^FO50,30^FD\u5185\u90E8\u6599\u53F7: {material_code}^FS",       # 内部料号
    ]

    if customer_material_code:
        lines.append(
            f"^FO50,70^FD\u5BA2\u6237\u6599\u53F7: {customer_material_code}^FS"  # 客户料号
        )

    if reel_barcode:
        lines.append(f"^FO50,110^FDReel: {reel_barcode}^FS")

    lines.extend([
        "^CF0,50",
        f"^FO50,170^FDQTY: {qty_str}^FS",
        # Separator line
        "^FO50,230^GB500,2,2^FS",
        # Material code in large font for barcode scanner
        "^CF0,60",
        f"^FO50,250^FD{material_code}^FS",
        "^XZ",
    ])

    return "\n".join(lines)


async def print_label(
    host: str,
    port: int,
    material_code: str,
    material_name: str,
    quantity: float,
    customer_material_code: str = "",
    reel_barcode: str = "",
    timeout: float = 5.0,
) -> bool:
    """Send ZPL label to network printer via TCP.

    Returns True if the label was sent successfully, False otherwise.
    """
    zpl = build_zpl(
        material_code=material_code,
        material_name=material_name,
        quantity=quantity,
        customer_material_code=customer_material_code,
        reel_barcode=reel_barcode,
    )

    # ── Simulation mode: skip real TCP connection ──
    if settings.HARDWARE_SIMULATION:
        logger.info(
            "SIM: label printed %s QTY=%s reel=%s (no hardware)",
            material_code, quantity, reel_barcode,
        )
        return True

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        writer.write(zpl.encode("ascii"))
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        logger.info(
            "Label printed: %s QTY=%s customer=%s reel=%s -> %s:%s",
            material_code, quantity, customer_material_code, reel_barcode, host, port,
        )
        return True
    except asyncio.TimeoutError:
        logger.warning("Printer timeout: %s:%s", host, port)
    except OSError as e:
        logger.warning("Printer connection failed %s:%s — %s", host, port, e)
    except Exception as e:
        logger.warning("Printer error %s:%s — %s", host, port, e)
    return False
