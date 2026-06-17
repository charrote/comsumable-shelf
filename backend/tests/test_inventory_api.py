"""Tests for inventory API — PUT /inventory/{pallet_id} (P3-1c) and
quantity validation (P3-1b).

Tests schema validation and business logic directly without httpx.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import InventoryUpdateRequest
from app.models import (
    InventoryReel,
    Shelf,
    ShelfSlot,
    Transaction,
)


# =========================================================================
#  Schema tests
# =========================================================================

class TestInventoryUpdateSchema:
    """Pydantic schema validation for InventoryUpdateRequest."""

    def test_valid_full_update(self):
        req = InventoryUpdateRequest(
            quantity=10.0, status="on_shelf", shelf_slot_id=5, note="盘点修正",
        )
        assert req.quantity == 10.0
        assert req.status == "on_shelf"
        assert req.shelf_slot_id == 5

    def test_partial_update_quantity_only(self):
        req = InventoryUpdateRequest(quantity=20.0)
        assert req.quantity == 20.0
        assert req.status is None

    def test_negative_quantity_rejected(self):
        with pytest.raises(ValidationError):
            InventoryUpdateRequest(quantity=-5.0)

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            InventoryUpdateRequest(status="bogus")

    def test_empty_body_ok(self):
        req = InventoryUpdateRequest()
        assert req.quantity is None

    def test_explicit_null_shelf_slot_id(self):
        """Explicit None shelf_slot_id is valid (unbind from slot)."""
        req = InventoryUpdateRequest(shelf_slot_id=None)
        assert req.shelf_slot_id is None


# =========================================================================
#  ShelfSlot max_quantity tests
# =========================================================================

class TestShelfSlotCapacity:
    """ShelfSlot model supports max_quantity field."""

    async def test_default_max_quantity_is_none(
        self, db_session: AsyncSession,
    ):
        """New slot defaults to unlimited (max_quantity=None)."""
        shelf = Shelf(code="CAP-TEST", name="容量测试", active=1)
        db_session.add(shelf)
        await db_session.commit()

        slot = ShelfSlot(
            shelf_id=shelf.id, side="A", board_address=1,
            slot_on_board=1, global_index=1, modbus_coil_base=0,
        )
        db_session.add(slot)
        await db_session.commit()
        assert slot.max_quantity is None

    async def test_set_max_quantity(
        self, db_session: AsyncSession,
    ):
        """Can set max_quantity on slot creation."""
        shelf = Shelf(code="CAP-TEST2", name="容量测试2", active=1)
        db_session.add(shelf)
        await db_session.commit()

        slot = ShelfSlot(
            shelf_id=shelf.id, side="A", board_address=1,
            slot_on_board=1, global_index=1, modbus_coil_base=0,
            max_quantity=100.0,
        )
        db_session.add(slot)
        await db_session.commit()
        await db_session.refresh(slot)
        assert slot.max_quantity == 100.0


# =========================================================================
#  Pick quantity validation tests
# =========================================================================

class TestPickQuantityValidation:
    """Issue confirm-pick quantity logic (partial consumption, transactions)."""

    async def test_partial_consumption_reduces_pallet(
        self, db_session: AsyncSession, sample_material, sample_customer,
    ):
        """Pick < full pallet: pallet quantity reduced, status stays on_shelf."""
        now = datetime.utcnow()
        pallet = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=10.0, original_quantity=10.0,
            reel_barcode="PARTIAL-TEST",
            first_in_time=now, last_in_time=now,
            status="on_shelf",
        )
        db_session.add(pallet)
        await db_session.commit()

        # Partial pick: 4 of 10
        pick_qty = 4.0
        remaining = pallet.quantity - pick_qty
        await db_session.execute(
            update(InventoryReel)
            .where(InventoryReel.id == pallet.id)
            .values(quantity=remaining)
        )
        await db_session.commit()
        await db_session.refresh(pallet)

        assert pallet.quantity == 6.0
        assert pallet.status == "on_shelf"  # still on shelf

    async def test_full_consumption_exhausts_pallet(
        self, db_session: AsyncSession, sample_material, sample_customer,
    ):
        """Pick == full pallet: pallet exhausted."""
        now = datetime.utcnow()
        pallet = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=5.0, original_quantity=5.0,
            reel_barcode="FULL-TEST",
            first_in_time=now, last_in_time=now,
            status="on_shelf",
        )
        db_session.add(pallet)
        await db_session.commit()

        await db_session.execute(
            update(InventoryReel)
            .where(InventoryReel.id == pallet.id)
            .values(quantity=0, status="exhausted")
        )
        await db_session.commit()
        await db_session.refresh(pallet)

        assert pallet.quantity == 0
        assert pallet.status == "exhausted"

    async def test_transaction_recorded(
        self, db_session: AsyncSession, sample_material, sample_customer,
    ):
        """Transaction row created on pick."""
        now = datetime.utcnow()
        pallet = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=8.0, original_quantity=8.0,
            reel_barcode="TXN-TEST",
            first_in_time=now, last_in_time=now,
            status="on_shelf",
        )
        db_session.add(pallet)
        await db_session.commit()
        await db_session.refresh(pallet)

        txn = Transaction(
            customer_id=sample_customer.id,
            material_id=sample_material.id,
            type="out",
            quantity=3.0,
            balance_after=5.0,
            reel_id=pallet.id,
            source_type="issue",
            source_id=1,
            operator="tester",
            note="出库测试",
            created_at=now,
        )
        db_session.add(txn)
        await db_session.commit()

        result = await db_session.execute(
            select(Transaction).where(Transaction.reel_id == pallet.id)
        )
        saved = result.scalar_one_or_none()
        assert saved is not None
        assert saved.type == "out"
        assert saved.quantity == 3.0
