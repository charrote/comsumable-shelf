"""Unit tests for shelving API — scan reel and bind to shelf slot.

Covers:
  1. Shelving scan (reel found, already bound, not found)
  2. Shelving bind (specific slot, auto-empty-slot, slot occupied, wrong status)
"""

import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Customer,
    MaterialMaster,
    InventoryReel,
    Shelf,
    ShelfSlot,
    ShelfSlotEvent,
)
from app.api.shelving import (
    ShelvingScanRequest,
    ShelvingScanResponse,
    ShelvingBindRequest,
    ShelvingBindResponse,
    scan_reel_for_shelving,
    bind_shelving_slot,
)
from app.utils.database import get_db
from fastapi import HTTPException


# =========================================================================
#  Helper factories
# =========================================================================

async def _make_reel(
    db: AsyncSession,
    material_id: int,
    customer_id: int,
    barcode: str = "REEL-001",
    status: str = "on_shelf",
    shelf_slot_id: int = None,
) -> InventoryReel:
    now = datetime.utcnow()
    reel = InventoryReel(
        material_id=material_id,
        customer_id=customer_id,
        quantity=25.0,
        original_quantity=25.0,
        reel_barcode=barcode,
        first_in_time=now,
        last_in_time=now,
        status=status,
        shelf_slot_id=shelf_slot_id,
    )
    db.add(reel)
    await db.commit()
    await db.refresh(reel)
    return reel


async def _make_shelf(
    db: AsyncSession,
    code: str = "SHELF-A",
    side: str = "A",
    slot_on_board: int = 1,
    global_index: int = 1,
    max_quantity: float = None,
    last_sensor_state: int = 0,
) -> tuple[Shelf, ShelfSlot]:
    shelf = Shelf(code=code, name=f"料架 {code}", active=1)
    db.add(shelf)
    await db.commit()

    slot = ShelfSlot(
        shelf_id=shelf.id,
        side=side,
        board_address=1,
        slot_on_board=slot_on_board,
        global_index=global_index,
        modbus_tcp_id=1,
        modbus_coil_base=0,
        max_quantity=max_quantity,
        last_sensor_state=last_sensor_state,
    )
    db.add(slot)
    await db.commit()
    await db.refresh(shelf)
    await db.refresh(slot)
    return shelf, slot


# =========================================================================
#  Shelving scan tests
# =========================================================================

class TestScanReelForShelving:
    """POST /shelving/scan — look up reel by barcode/ID."""

    async def test_scan_by_reel_id(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """Scan by numeric reel ID (barcode = reel ID)."""
        reel = await _make_reel(
            db_session, sample_material.id, sample_customer.id,
            barcode="REEL-SCAN-001",
        )
        req = ShelvingScanRequest(barcode=str(reel.id))

        resp = await scan_reel_for_shelving(req, db_session)

        assert resp.status == "ok"
        assert resp.reel_id == reel.id
        assert resp.material_code == sample_material.code
        assert resp.material_name == sample_material.name
        assert resp.quantity == 25.0
        assert resp.shelf_slot_id is None

    async def test_scan_by_barcode(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """Scan by reel_barcode string."""
        reel = await _make_reel(
            db_session, sample_material.id, sample_customer.id,
            barcode="REEL-BARCODE-001",
        )
        req = ShelvingScanRequest(barcode="REEL-BARCODE-001")

        resp = await scan_reel_for_shelving(req, db_session)

        assert resp.status == "ok"
        assert resp.reel_id == reel.id

    async def test_already_bound(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """Reel already has shelf_slot_id → already_bound status."""
        shelf, slot = await _make_shelf(db_session)
        reel = await _make_reel(
            db_session, sample_material.id, sample_customer.id,
            barcode="BOUND-001", shelf_slot_id=slot.id,
        )
        req = ShelvingScanRequest(barcode=str(reel.id))

        resp = await scan_reel_for_shelving(req, db_session)

        assert resp.status == "already_bound"
        assert resp.shelf_slot_id == slot.id
        assert resp.shelf_code == shelf.code
        assert resp.slot_code is not None

    async def test_not_found_raises_404(
        self, db_session: AsyncSession,
    ):
        """Non-existent barcode → 404."""
        req = ShelvingScanRequest(barcode="DOES-NOT-EXIST")

        with pytest.raises(HTTPException) as exc:
            await scan_reel_for_shelving(req, db_session)

        assert exc.value.status_code == 404

    async def test_empty_barcode_raises_400(
        self, db_session: AsyncSession,
    ):
        """Empty barcode after strip → 400."""
        req = ShelvingScanRequest(barcode="   ")

        with pytest.raises(HTTPException) as exc:
            await scan_reel_for_shelving(req, db_session)

        assert exc.value.status_code == 400
        assert "条码不能为空" in exc.value.detail


# =========================================================================
#  Shelving bind tests
# =========================================================================

class TestBindShelvingSlot:
    """POST /shelving/bind — bind reel to slot."""

    async def test_bind_to_specific_slot(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """Bind reel to a specific slot by shelf_slot_id."""
        shelf, slot = await _make_shelf(db_session)
        reel = await _make_reel(
            db_session, sample_material.id, sample_customer.id,
            barcode="BIND-SPECIFIC",
        )
        req = ShelvingBindRequest(
            reel_id=reel.id,
            shelf_id=shelf.id,
            shelf_slot_id=slot.id,
            operator="tester",
        )

        resp = await bind_shelving_slot(req, db_session)

        assert resp.status == "ok"
        assert resp.reel_id == reel.id
        assert resp.shelf_slot_id == slot.id
        assert resp.shelf_code == shelf.code
        assert "上架成功" in resp.message

        # Verify DB updated
        await db_session.refresh(reel)
        assert reel.shelf_slot_id == slot.id

        # Verify event recorded
        event_result = await db_session.execute(
            __import__("sqlalchemy").select(ShelfSlotEvent).where(
                ShelfSlotEvent.shelf_slot_id == slot.id,
                ShelfSlotEvent.event_type == "bound",
            )
        )
        event = event_result.scalar_one_or_none()
        assert event is not None
        assert event.reel_id == reel.id
        assert event.source == "pda"

    async def test_bind_to_auto_empty_slot(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """Bind with shelf_id + no shelf_slot_id → auto-find empty slot."""
        shelf, slot = await _make_shelf(
            db_session, code="AUTO-SLOT", side="A",
            slot_on_board=1, global_index=1, last_sensor_state=0,
        )
        reel = await _make_reel(
            db_session, sample_material.id, sample_customer.id,
            barcode="AUTO-BIND",
        )
        req = ShelvingBindRequest(
            reel_id=reel.id,
            shelf_id=shelf.id,
            shelf_slot_id=None,
            operator="tester",
        )

        resp = await bind_shelving_slot(req, db_session)

        assert resp.status == "ok"
        assert resp.shelf_slot_id == slot.id
        assert "上架成功" in resp.message

    async def test_bind_slot_occupied_raises_400(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """Slot already occupied by another on_shelf reel → 400."""
        shelf, slot = await _make_shelf(db_session, code="OCCUPIED")
        # First reel occupies the slot
        reel1 = await _make_reel(
            db_session, sample_material.id, sample_customer.id,
            barcode="OCC-1", shelf_slot_id=slot.id,
        )
        # Second reel tries to bind to same slot
        reel2 = await _make_reel(
            db_session, sample_material.id, sample_customer.id,
            barcode="OCC-2",
        )
        req = ShelvingBindRequest(
            reel_id=reel2.id,
            shelf_id=shelf.id,
            shelf_slot_id=slot.id,
            operator="tester",
        )

        with pytest.raises(HTTPException) as exc:
            await bind_shelving_slot(req, db_session)

        assert exc.value.status_code == 400
        assert "已被占用" in exc.value.detail

    async def test_bind_reel_not_found_raises_404(
        self, db_session: AsyncSession,
    ):
        """Non-existent reel_id → 404."""
        req = ShelvingBindRequest(
            reel_id=99999,
            shelf_id=1,
            shelf_slot_id=1,
            operator="tester",
        )

        with pytest.raises(HTTPException) as exc:
            await bind_shelving_slot(req, db_session)

        assert exc.value.status_code == 404
        assert "料盘不存在" in exc.value.detail

    async def test_bind_reel_wrong_status_raises_400(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """Reel with status != on_shelf cannot be shelved."""
        shelf, slot = await _make_shelf(db_session, code="STATUS-ERR")
        reel = await _make_reel(
            db_session, sample_material.id, sample_customer.id,
            barcode="TRACKING-REEL", status="tracking",
        )
        req = ShelvingBindRequest(
            reel_id=reel.id,
            shelf_id=shelf.id,
            shelf_slot_id=slot.id,
            operator="tester",
        )

        with pytest.raises(HTTPException) as exc:
            await bind_shelving_slot(req, db_session)

        assert exc.value.status_code == 400
        assert "无法上架" in exc.value.detail

    async def test_bind_slot_not_found_raises_404(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """Non-existent shelf_slot_id → 404."""
        shelf, _ = await _make_shelf(db_session, code="NO-SLOT")
        reel = await _make_reel(
            db_session, sample_material.id, sample_customer.id,
            barcode="NO-SLOT-REEL",
        )
        req = ShelvingBindRequest(
            reel_id=reel.id,
            shelf_id=shelf.id,
            shelf_slot_id=99999,
            operator="tester",
        )

        with pytest.raises(HTTPException) as exc:
            await bind_shelving_slot(req, db_session)

        assert exc.value.status_code == 404
        assert "储位不存在" in exc.value.detail

    async def test_auto_shelf_not_found_raises_404(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """Auto-find slot on non-existent shelf → 404."""
        reel = await _make_reel(
            db_session, sample_material.id, sample_customer.id,
            barcode="NO-SHELF",
        )
        req = ShelvingBindRequest(
            reel_id=reel.id,
            shelf_id=99999,
            shelf_slot_id=None,
            operator="tester",
        )

        with pytest.raises(HTTPException) as exc:
            await bind_shelving_slot(req, db_session)

        assert exc.value.status_code == 404
        assert "料架不存在" in exc.value.detail

    async def test_auto_no_empty_slot_raises_400(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """Shelf exists but no empty slot → 400."""
        shelf, slot = await _make_shelf(
            db_session, code="FULL", last_sensor_state=1,  # sensor says occupied
        )
        reel = await _make_reel(
            db_session, sample_material.id, sample_customer.id,
            barcode="FULL-SHELF",
        )
        req = ShelvingBindRequest(
            reel_id=reel.id,
            shelf_id=shelf.id,
            shelf_slot_id=None,
            operator="tester",
        )

        with pytest.raises(HTTPException) as exc:
            await bind_shelving_slot(req, db_session)

        assert exc.value.status_code == 400
        assert "没有可用的空储位" in exc.value.detail
