"""ZPL label printer HAL — network TCP direct connection."""

import asyncio
import logging

logger = logging.getLogger(__name__)


def build_zpl(material_code: str, material_name: str, quantity: float) -> str:
    """Build ZPL label for SMT reel.

    Label format:
      [material_code]
      [material_name]
      QTY: [quantity]
    """
    qty_str = f"{quantity:.0f}" if quantity == int(quantity) else f"{quantity}"
    return (
        "^XA\n"
        "^CF0,40\n"
        f"^FO50,50^FD{material_code}^FS\n"
        "^CF0,30\n"
        f"^FO50,110^FD{material_name}^FS\n"
        "^CF0,50\n"
        f"^FO50,180^FDQTY: {qty_str}^FS\n"
        "^XZ\n"
    )


async def print_label(
    host: str,
    port: int,
    material_code: str,
    material_name: str,
    quantity: float,
    timeout: float = 5.0,
) -> bool:
    """Send ZPL label to network printer via TCP."""
    zpl = build_zpl(material_code, material_name, quantity)
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        writer.write(zpl.encode("ascii"))
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        logger.info("Label printed: %s QTY=%s -> %s:%s", material_code, quantity, host, port)
        return True
    except asyncio.TimeoutError:
        logger.warning("Printer timeout: %s:%s", host, port)
    except OSError as e:
        logger.warning("Printer connection failed %s:%s — %s", host, port, e)
    except Exception as e:
        logger.warning("Printer error %s:%s — %s", host, port, e)
    return False
