"""BOM business service — material auto-creation during upload."""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import MaterialMaster

logger = logging.getLogger(__name__)


async def ensure_materials_exist(
    db: AsyncSession,
    material_codes: set[str],
    customer_id: int,
    default_unit: str = "盘",
) -> int:
    """Ensure all material codes in the set exist in MaterialMaster.

    For each code that does NOT already exist (per customer), create a new
    MaterialMaster record with unit='盘' and name=code.
    Skips empty strings.

    Returns the count of newly created materials.
    """
    created_count = 0

    for code in sorted(material_codes):
        code = code.strip()
        if not code:
            continue

        # Check if material already exists for this customer
        existing = await db.execute(
            select(MaterialMaster).where(
                MaterialMaster.customer_id == customer_id,
                MaterialMaster.code == code,
                MaterialMaster.active == 1,
            )
        )
        if existing.scalar_one_or_none():
            continue  # already exists

        # Create new material
        material = MaterialMaster(
            customer_id=customer_id,
            code=code,
            name=code,  # use code as name; user can edit later
            unit=default_unit,
            active=1,
        )
        db.add(material)
        created_count += 1
        logger.info("BOM auto-created MaterialMaster: code=%s customer_id=%d", code, customer_id)

    if created_count > 0:
        await db.commit()

    return created_count
