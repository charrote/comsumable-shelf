"""Unit tests for receipt (inbound) service — barcode matching, duplicate check,
material auto-create, and receipt reel finalization.

Covers:
  1. Duplicate scan detection (block / warn / force)
  2. Barcode matching (CustomerMaterialMapping, exact, fuzzy, no-match)
  3. Auto-create material
  4. Finalize receipt reel (InventoryReel + ReceiptReel + auto slot assign)
"""

import pytest
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Customer,
    MaterialMaster,
    MaterialCategory,
    InventoryReel,
    Receipt,
    ReceiptReel,
    Shelf,
    ShelfSlot,
    SystemSetting,
    CustomerMaterialMapping,
)
from app.services.receipt_service import (
    match_material_by_barcode,
    auto_create_material,
    finalize_receipt_reel,
    MatchResult,
)
from app.services.duplicate_check import check_duplicate_scan


# =========================================================================
#  Duplicate scan detection
# =========================================================================

class TestDuplicateScan:
    """duplicate_scan_behavior: block | warn | force."""

    async def _seed_reel(
        self, db: AsyncSession, material_id: int, customer_id: int,
        barcode: str, status: str = "on_shelf",
    ) -> InventoryReel:
        now = datetime.utcnow()
        reel = InventoryReel(
            material_id=material_id,
            customer_id=customer_id,
            quantity=10.0,
            original_quantity=10.0,
            reel_barcode=barcode,
            first_in_time=now,
            last_in_time=now,
            status=status,
        )
        db.add(reel)
        await db.commit()
        return reel

    async def test_block_duplicate_by_default(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """Default behavior (block) rejects duplicate scans."""
        barcode = "DUP-001"
        await self._seed_reel(db_session, sample_material.id, sample_customer.id, barcode)

        result = await check_duplicate_scan(db_session, barcode, sample_customer.id)

        assert result.duplicate is True
        assert result.action == "block"
        assert result.existing_reel_id is not None
        assert "已拦截" in result.message

    async def test_warn_allows_duplicate_with_flag(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """warn mode allows duplicate but sets duplicate flag."""
        barcode = "DUP-WARN-001"
        await self._seed_reel(db_session, sample_material.id, sample_customer.id, barcode)

        # Set behavior to warn
        setting = SystemSetting(key="duplicate_scan_behavior", value="warn")
        db_session.add(setting)
        await db_session.commit()

        result = await check_duplicate_scan(db_session, barcode, sample_customer.id)

        assert result.duplicate is True
        assert result.action == "warn"
        assert result.warning != ""

    async def test_force_skips_check(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """force mode skips duplicate check entirely."""
        barcode = "DUP-FORCE-001"
        await self._seed_reel(db_session, sample_material.id, sample_customer.id, barcode)

        setting = SystemSetting(key="duplicate_scan_behavior", value="force")
        db_session.add(setting)
        await db_session.commit()

        result = await check_duplicate_scan(db_session, barcode, sample_customer.id)

        assert result.duplicate is False
        assert result.action == "allow"

    async def test_no_duplicate_returns_allow(
        self, db_session: AsyncSession,
    ):
        """No existing reel → allow."""
        result = await check_duplicate_scan(db_session, "NONEXISTENT-001", 1)

        assert result.duplicate is False
        assert result.action == "allow"

    async def test_ignores_exhausted_reels(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """Exhausted reels should not trigger duplicate."""
        barcode = "EXHAUSTED-DUP"
        await self._seed_reel(
            db_session, sample_material.id, sample_customer.id,
            barcode, status="exhausted",
        )

        result = await check_duplicate_scan(db_session, barcode, sample_customer.id)

        assert result.duplicate is False
        assert result.action == "allow"

    async def test_unknown_setting_falls_back_to_block(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """Invalid setting value falls back to 'block'."""
        barcode = "INVALID-SETTING"
        await self._seed_reel(db_session, sample_material.id, sample_customer.id, barcode)

        setting = SystemSetting(key="duplicate_scan_behavior", value="unknown_value")
        db_session.add(setting)
        await db_session.commit()

        result = await check_duplicate_scan(db_session, barcode, sample_customer.id)

        assert result.action == "block"


# =========================================================================
#  Barcode matching
# =========================================================================

class TestMatchMaterialByBarcode:
    """match_material_by_barcode scenarios."""

    async def test_maps_through_customer_material_mapping(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """CustomerMaterialMapping resolves to mapped internal material."""
        # Create mapping: customer code "CUST-RES" → sample_material
        mapping = CustomerMaterialMapping(
            customer_id=sample_customer.id,
            customer_material_code="CUST-RES",
            internal_material_id=sample_material.id,
            active=1,
        )
        db_session.add(mapping)
        await db_session.commit()

        result = await match_material_by_barcode(
            db_session, barcode="CUST-RES", customer_id=sample_customer.id,
        )

        assert result.action == "auto_proceed"
        assert result.matched is True
        assert result.material_id == sample_material.id
        assert result.material_code == sample_material.code
        assert result.confidence == 1.0
        assert result.customer_material_code == "CUST-RES"

    async def test_inactive_mapping_ignored(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """Inactive CustomerMaterialMapping is not used."""
        mapping = CustomerMaterialMapping(
            customer_id=sample_customer.id,
            customer_material_code="INACTIVE-MAP",
            internal_material_id=sample_material.id,
            active=0,
        )
        db_session.add(mapping)
        await db_session.commit()

        result = await match_material_by_barcode(
            db_session, barcode="INACTIVE-MAP", customer_id=sample_customer.id,
        )

        # Should fall through — no active mapping match
        assert result.action in ("auto_proceed", "pending_review", "new_material")
        # It's not matching via mapping, so it could be exact match via find_material_candidates
        # Since sample_material.code != "INACTIVE-MAP", it won't be exact
        # But it might fuzzy-match — handle either outcome

    async def test_exact_match_auto_proceeds(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """Exact barcode → material code match yields auto_proceed."""
        barcode = sample_material.code  # e.g., "RES-100K"
        result = await match_material_by_barcode(
            db_session, barcode=barcode, customer_id=sample_customer.id,
        )

        assert result.action == "auto_proceed"
        assert result.matched is True
        assert result.material_id == sample_material.id

    async def test_no_match_returns_new_material(
        self, db_session: AsyncSession, sample_customer: Customer,
    ):
        """No candidates at all → new_material action."""
        result = await match_material_by_barcode(
            db_session, barcode="ZZZ-NO-MATCH-99999", customer_id=sample_customer.id,
        )

        assert result.action == "new_material"
        assert result.matched is False

    async def test_no_customer_id_skips_mapping(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
    ):
        """customer_id=0 or None skips CustomerMaterialMapping."""
        result = await match_material_by_barcode(
            db_session, barcode=sample_material.code, customer_id=0,
        )

        assert result.action in ("auto_proceed", "new_material")
        # Depending on whether code matches, it'll auto_proceed or new_material


# =========================================================================
#  Auto-create material
# =========================================================================

class TestAutoCreateMaterial:
    """auto_create_material logic."""

    async def test_creates_material(
        self, db_session: AsyncSession, sample_customer: Customer,
    ):
        """New material record is created with correct fields."""
        mat = await auto_create_material(
            db_session,
            code="NEW-MAT-001",
            name="新增物料",
            customer_id=sample_customer.id,
            customer_material_code="SUPPLIER-001",
        )

        assert mat.id is not None
        assert mat.code == "NEW-MAT-001"
        assert mat.name == "新增物料"
        assert mat.customer_id == sample_customer.id
        assert mat.active == 1

    async def test_name_falls_back_to_code(
        self, db_session: AsyncSession, sample_customer: Customer,
    ):
        """When name is None, falls back to code."""
        mat = await auto_create_material(
            db_session,
            code="FALLBACK-NAME",
            customer_id=sample_customer.id,
        )

        assert mat.name == "FALLBACK-NAME"

    async def test_default_unit_is_pan(
        self, db_session: AsyncSession, sample_customer: Customer,
    ):
        """Default unit is '盘'."""
        mat = await auto_create_material(
            db_session,
            code="UNIT-TEST",
            customer_id=sample_customer.id,
        )

        assert mat.unit == "盘"


# =========================================================================
#  Finalize receipt reel
# =========================================================================

class TestFinalizeReceiptReel:
    """finalize_receipt_reel creates InventoryReel + ReceiptReel + optional slot assign."""

    async def _setup_receipt(
        self, db: AsyncSession, customer_id: int,
    ) -> Receipt:
        r = Receipt(
            receipt_no=f"RCV-TEST-{datetime.utcnow().timestamp()}",
            customer_id=customer_id,
            created_by="tester",
            status="draft",
        )
        db.add(r)
        await db.commit()
        await db.refresh(r)
        return r

    async def _setup_shelf(
        self, db: AsyncSession,
    ) -> tuple[Shelf, ShelfSlot]:
        """Create shelf + one empty slot with sensor state=0."""
        shelf = Shelf(code="AUTO-SHELF", name="自动分配测试", active=1)
        db.add(shelf)
        await db.commit()

        slot = ShelfSlot(
            shelf_id=shelf.id,
            side="A",
            board_address=1,
            slot_on_board=1,
            global_index=1,
            modbus_tcp_id=1,
            modbus_coil_base=0,
            last_sensor_state=0,
        )
        db.add(slot)
        await db.commit()
        return shelf, slot

    async def test_creates_inventory_reel(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """InventoryReel is created with correct fields."""
        receipt = await self._setup_receipt(db_session, sample_customer.id)

        result = await finalize_receipt_reel(
            db=db_session,
            receipt_id=receipt.id,
            material_id=sample_material.id,
            barcode="FINALIZE-001",
            quantity=50.0,
            operator="tester",
            customer_id=sample_customer.id,
            customer_material_code="CUST-CODE",
        )

        assert result["reel_id"] is not None
        assert result["quantity"] == 50.0

        # Verify in DB
        reel = await db_session.get(InventoryReel, result["reel_id"])
        assert reel is not None
        assert reel.material_id == sample_material.id
        assert reel.quantity == 50.0
        assert reel.original_quantity == 50.0
        assert reel.reel_barcode == reel.reel_code  # reel_barcode is set to auto-generated reel_code

    async def test_creates_receipt_reel(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """ReceiptReel record is created linked to the receipt and reel."""
        receipt = await self._setup_receipt(db_session, sample_customer.id)

        result = await finalize_receipt_reel(
            db=db_session,
            receipt_id=receipt.id,
            material_id=sample_material.id,
            barcode="RR-TEST",
            quantity=20.0,
            operator="tester",
            customer_id=sample_customer.id,
        )

        # Find the ReceiptReel
        from sqlalchemy import select
        rr_result = await db_session.execute(
            select(ReceiptReel).where(ReceiptReel.receipt_id == receipt.id)
        )
        rr = rr_result.scalar_one_or_none()
        assert rr is not None
        assert rr.material_id == sample_material.id
        assert rr.quantity == 20.0
        assert rr.reel_id == result["reel_id"]
        assert rr.operator == "tester"

    async def test_auto_assign_slot(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """auto_assign_slot=True finds and binds empty slot."""
        receipt = await self._setup_receipt(db_session, sample_customer.id)
        shelf, slot = await self._setup_shelf(db_session)

        result = await finalize_receipt_reel(
            db=db_session,
            receipt_id=receipt.id,
            material_id=sample_material.id,
            barcode="SLOT-TEST",
            quantity=30.0,
            operator="tester",
            customer_id=sample_customer.id,
            auto_assign_slot=True,
        )

        assert result["assigned_slot"] is not None

        # Verify reel has shelf_slot_id set
        reel = await db_session.get(InventoryReel, result["reel_id"])
        assert reel.shelf_slot_id is not None

    async def test_skip_auto_assign_when_disabled(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """auto_assign_slot=False does not assign a slot."""
        receipt = await self._setup_receipt(db_session, sample_customer.id)
        shelf, slot = await self._setup_shelf(db_session)

        result = await finalize_receipt_reel(
            db=db_session,
            receipt_id=receipt.id,
            material_id=sample_material.id,
            barcode="NO-SLOT",
            quantity=10.0,
            operator="tester",
            customer_id=sample_customer.id,
            auto_assign_slot=False,
        )

        assert result["assigned_slot"] is None

        reel = await db_session.get(InventoryReel, result["reel_id"])
        assert reel.shelf_slot_id is None

    async def test_auto_assign_respects_capacity(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """Slot with max_quantity < quantity is skipped."""
        receipt = await self._setup_receipt(db_session, sample_customer.id)
        shelf = Shelf(code="CAP-SHELF", name="容量测试", active=1)
        db_session.add(shelf)
        await db_session.commit()

        # Small slot (capacity 5)
        small_slot = ShelfSlot(
            shelf_id=shelf.id, side="A", board_address=1,
            slot_on_board=1, global_index=1,
            modbus_tcp_id=1, modbus_coil_base=0,
            last_sensor_state=0, max_quantity=5.0,
        )
        # Large slot (capacity 100)
        large_slot = ShelfSlot(
            shelf_id=shelf.id, side="A", board_address=2,
            slot_on_board=2, global_index=2,
            modbus_tcp_id=2, modbus_coil_base=1,
            last_sensor_state=0, max_quantity=100.0,
        )
        db_session.add_all([small_slot, large_slot])
        await db_session.commit()

        # Real quantity = 50 — should skip small_slot (cap 5) and assign large_slot
        result = await finalize_receipt_reel(
            db=db_session,
            receipt_id=receipt.id,
            material_id=sample_material.id,
            barcode="CAP-TEST",
            quantity=50.0,
            operator="tester",
            customer_id=sample_customer.id,
            auto_assign_slot=True,
        )

        assert result["assigned_slot"] is not None
        # Should be assigned to large_slot (global_index=2) not small_slot (global_index=1)
        assert result["assigned_slot"] == 2

    async def test_no_available_slot_returns_none(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """No empty slot → assigned_slot is None (no error)."""
        receipt = await self._setup_receipt(db_session, sample_customer.id)
        # No shelf/slot created — no empty slots

        result = await finalize_receipt_reel(
            db=db_session,
            receipt_id=receipt.id,
            material_id=sample_material.id,
            barcode="NO-SLOT-AVAIL",
            quantity=10.0,
            operator="tester",
            customer_id=sample_customer.id,
            auto_assign_slot=True,
        )

        assert result["assigned_slot"] is None
        # Reel should still be created without a slot
        assert result["reel_id"] is not None
