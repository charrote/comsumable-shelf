"""Unit tests for FIFO allocation service.

Covers all four strategies:
  - tail_first  : pick pallets with smallest quantity first (尾数优先)
  - time_fifo   : strict chronological order (先进先出)
  - mixed       : tail_first first, then time_fifo as tie-breaker
  - config      : resolves to the configured default strategy

Whole-reel mode: every pick takes an entire reel (不拆盘).
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Customer,
    MaterialMaster,
    MaterialCategory,
    InventoryReel,
    MaterialAlternative,
)
from app.services.fifo_service import (
    calculate_fifo_pallets,
    get_available_qty,
    check_alternative_material,
)


# =========================================================================
#  Helper: seed pallets with controlled quantities & timestamps
# =========================================================================

async def _make_pallets(
    db: AsyncSession,
    material_id: int,
    customer_id: int,
    quantities: list[float],
    base_time: datetime | None = None,
) -> list[InventoryReel]:
    """Create N pallets with given quantities and sequential timestamps.

    Returns the list of created pallets (ordered by creation).
    """
    now = base_time or datetime(2026, 6, 1, 10, 0, 0)
    pallets = []
    for i, qty in enumerate(quantities):
        t = now + timedelta(minutes=i)
        p = InventoryReel(
            material_id=material_id,
            customer_id=customer_id,
            quantity=qty,
            original_quantity=qty,
            reel_barcode=f"PALLET-{i:03d}",
            first_in_time=t,
            last_in_time=t,
            status="on_shelf",
        )
        db.add(p)
        pallets.append(p)
    await db.commit()
    for p in pallets:
        await db.refresh(p)
    return pallets


# =========================================================================
#  Fixtures: reusable sample data
# =========================================================================

@pytest.fixture
def base_time() -> datetime:
    """Fixed reference timestamp for FIFO ordering tests."""
    return datetime(2026, 6, 1, 8, 0, 0)


# =========================================================================
#  Basic allocation tests
# =========================================================================

class TestCalculateFifoPallets:
    """Core FIFO calculation logic (whole-reel mode)."""

    async def test_tail_first_selects_smallest_first(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """tail_first strategy: pallets with smallest qty picked first.
        Whole-reel mode: each pick takes the entire reel quantity."""
        qties = [10.0, 3.0, 7.0, 1.0]  # sorted: 1,3,7,10
        await _make_pallets(db_session, sample_material.id, sample_customer.id, qties, base_time)

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=6.0, strategy="tail_first",
        )

        assert result["strategy_used"] == "tail_first"
        # Whole-reel: picks 1, 3, 7 (all whole, not partial)
        assert len(result["reels"]) == 3
        assert result["reels"][0]["quantity"] == 1.0   # whole
        assert result["reels"][1]["quantity"] == 3.0   # whole
        assert result["reels"][2]["quantity"] == 7.0   # whole
        # total_selected = 1+3+7 = 11 (could exceed required in whole-reel mode)
        assert result["total_selected"] == 11.0
        assert result["shortage"] == 0

    async def test_time_fifo_strict_chronological(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """time_fifo: strictly earliest last_in_time first, whole-reel picks."""
        quantities = [5.0, 5.0, 5.0]
        pallets = await _make_pallets(
            db_session, sample_material.id, sample_customer.id, quantities, base_time
        )

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=12.0, strategy="time_fifo",
        )

        assert result["strategy_used"] == "time_fifo"
        assert len(result["reels"]) == 3
        assert result["reels"][0]["reel_id"] == pallets[0].id
        assert result["reels"][1]["reel_id"] == pallets[1].id
        assert result["reels"][2]["reel_id"] == pallets[2].id
        assert result["total_selected"] == 15.0  # 5+5+5 (whole reels)
        assert result["shortage"] == 0

    async def test_mixed_strategy_tie_break(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """mixed: sort by (quantity, last_in_time), whole-reel picks."""
        t0 = base_time
        p1 = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=5.0, original_quantity=5.0,
            reel_barcode="P-MIX-1",
            first_in_time=t0, last_in_time=t0,
            status="on_shelf",
        )
        p2 = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=3.0, original_quantity=3.0,
            reel_barcode="P-MIX-2",
            first_in_time=t0 + timedelta(minutes=1), last_in_time=t0 + timedelta(minutes=1),
            status="on_shelf",
        )
        p3 = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=5.0, original_quantity=5.0,
            reel_barcode="P-MIX-3",
            first_in_time=t0 + timedelta(minutes=2), last_in_time=t0 + timedelta(minutes=2),
            status="on_shelf",
        )
        db_session.add_all([p1, p2, p3])
        await db_session.commit()

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=10.0, strategy="mixed",
        )

        assert result["strategy_used"] == "mixed"
        assert len(result["reels"]) == 3
        # Expected order: p2 (qty=3), p1 (qty=5, time earlier), p3 (qty=5, time later)
        assert result["reels"][0]["reel_id"] == p2.id
        assert result["reels"][1]["reel_id"] == p1.id
        assert result["reels"][2]["reel_id"] == p3.id
        assert result["total_selected"] == 13.0  # 3+5+5 (whole reels)
        assert result["shortage"] == 0

    async def test_config_resolves_to_default_strategy(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """strategy='config' resolves to settings.FIFO_STRATEGY (default: tail_first)."""
        monkeypatch.setattr("app.config.settings.FIFO_STRATEGY", "time_fifo")

        quantities = [10.0, 5.0]
        await _make_pallets(db_session, sample_material.id, sample_customer.id, quantities, base_time)

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=3.0, strategy="config",
        )

        assert result["strategy_used"] == "time_fifo"
        # time_fifo picks pallet[0] (earliest, qty=10) first → whole reel
        assert result["reels"][0]["quantity"] == 10.0
        assert result["total_selected"] == 10.0

    async def test_config_reads_from_db_setting_when_present(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """strategy='config' reads fifo_strategy from system_settings DB table."""
        from app.models import SystemSetting

        db_setting = SystemSetting(
            key="fifo_strategy",
            value="time_fifo",
            description="FIFO 出库策略",
        )
        db_session.add(db_setting)
        await db_session.commit()

        quantities = [10.0, 5.0]
        await _make_pallets(db_session, sample_material.id, sample_customer.id, quantities, base_time)

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=3.0, strategy="config",
        )

        assert result["strategy_used"] == "time_fifo"
        # time_fifo picks earliest pallet (qty=10) first → whole reel
        assert result["reels"][0]["quantity"] == 10.0

    async def test_config_falls_back_to_env_when_db_unset(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """No DB setting → falls back to settings.FIFO_STRATEGY (env/config)."""
        monkeypatch.setattr("app.config.settings.FIFO_STRATEGY", "mixed")

        quantities = [5.0, 10.0]
        await _make_pallets(db_session, sample_material.id, sample_customer.id, quantities, base_time)

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=8.0, strategy="mixed",
        )

        assert result["strategy_used"] == "mixed"
        # mixed sort: (qty=5, t=0) first, (qty=10, t=1) second
        assert result["reels"][0]["quantity"] == 5.0   # whole
        assert result["reels"][1]["quantity"] == 10.0  # whole
        assert result["total_selected"] == 15.0

    # ------------------------------------------------------------------
    #  Shortage scenarios
    # ------------------------------------------------------------------

    async def test_shortage_when_not_enough_stock(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """Shortage reported when total stock < required_qty (whole-reel mode)."""
        await _make_pallets(db_session, sample_material.id, sample_customer.id, [3.0, 4.0], base_time)

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=10.0, strategy="tail_first",
        )

        assert result["total_selected"] == 7.0  # 3+4 (all stock, whole reels)
        assert result["shortage"] == 3.0
        assert len(result["reels"]) == 2

    async def test_exact_match_no_shortage(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """Required qty exactly matches total stock (whole-reel mode)."""
        await _make_pallets(db_session, sample_material.id, sample_customer.id, [5.0, 3.0, 2.0], base_time)

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=10.0, strategy="tail_first",
        )

        assert result["total_selected"] == 10.0  # 2+3+5 (whole reels)
        assert result["shortage"] == 0
        assert len(result["reels"]) == 3

    # ------------------------------------------------------------------
    #  Empty / edge cases
    # ------------------------------------------------------------------

    async def test_no_pallets_returns_empty(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """No on_shelf pallets → empty result with full shortage."""
        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=5.0, strategy="tail_first",
        )

        assert result["reels"] == []
        assert result["total_selected"] == 0
        assert result["shortage"] == 5.0

    async def test_zero_quantity_pallets_are_filtered(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """Pallets with quantity == 0 should be excluded."""
        p0 = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=0.0, original_quantity=5.0,
            reel_barcode="ZERO-1",
            first_in_time=base_time, last_in_time=base_time,
            status="on_shelf",
        )
        p1 = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=3.0, original_quantity=3.0,
            reel_barcode="OK-1",
            first_in_time=base_time + timedelta(minutes=1),
            last_in_time=base_time + timedelta(minutes=1),
            status="on_shelf",
        )
        db_session.add_all([p0, p1])
        await db_session.commit()

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=2.0, strategy="tail_first",
        )

        assert len(result["reels"]) == 1
        assert result["reels"][0]["reel_id"] == p1.id
        assert result["reels"][0]["quantity"] == 3.0  # whole reel

    async def test_exhausted_pallets_are_ignored(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """Only on_shelf pallets should be considered."""
        p_exhausted = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=10.0, original_quantity=10.0,
            reel_barcode="EXHAUSTED",
            first_in_time=base_time, last_in_time=base_time,
            status="exhausted",
        )
        db_session.add(p_exhausted)
        await db_session.commit()

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=1.0, strategy="tail_first",
        )

        assert result["reels"] == []
        assert result["shortage"] == 1.0

    async def test_customer_scoped_isolation(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """Only pallets of the specified customer_id are selected."""
        other = Customer(name="其他客户", code="CUST002")
        db_session.add(other)
        await db_session.commit()

        p_c1 = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=5.0, original_quantity=5.0,
            reel_barcode="C1",
            first_in_time=base_time, last_in_time=base_time,
            status="on_shelf",
        )
        p_c2 = InventoryReel(
            material_id=sample_material.id, customer_id=other.id,
            quantity=5.0, original_quantity=5.0,
            reel_barcode="C2",
            first_in_time=base_time, last_in_time=base_time,
            status="on_shelf",
        )
        db_session.add_all([p_c1, p_c2])
        await db_session.commit()

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=10.0, strategy="tail_first",
        )

        assert len(result["reels"]) == 1
        assert result["reels"][0]["reel_id"] == p_c1.id
        assert result["total_selected"] == 5.0
        assert result["shortage"] == 5.0


# =========================================================================
#  get_available_qty
# =========================================================================

class TestGetAvailableQty:
    """Total available quantity calculations (excludes reserved reels)."""

    async def test_returns_sum_of_all_on_shelf(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """Sum quantities of all on_shelf pallets for the material."""
        await _make_pallets(db_session, sample_material.id, sample_customer.id, [2.5, 3.5, 4.0], base_time)

        total = await get_available_qty(db_session, sample_material.id, sample_customer.id)

        assert total == 10.0

    async def test_returns_zero_when_none(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """No pallets → returns 0."""
        total = await get_available_qty(db_session, sample_material.id, sample_customer.id)
        assert total == 0.0

    async def test_excludes_non_on_shelf_status(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """Pallets with status != on_shelf are excluded."""
        p1 = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=10.0, original_quantity=10.0,
            reel_barcode="TRACKING",
            first_in_time=base_time, last_in_time=base_time,
            status="tracking",
        )
        p2 = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=5.0, original_quantity=5.0,
            reel_barcode="ON_SHELF",
            first_in_time=base_time + timedelta(minutes=1),
            last_in_time=base_time + timedelta(minutes=1),
            status="on_shelf",
        )
        db_session.add_all([p1, p2])
        await db_session.commit()

        total = await get_available_qty(db_session, sample_material.id, sample_customer.id)

        assert total == 5.0  # Only the on_shelf pallet


# =========================================================================
#  Reservation isolation tests
# =========================================================================

class TestReservationIsolation:
    """Verify reserved reels are excluded from FIFO calculation."""

    async def test_reserved_reel_excluded_from_fifo(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """A reel with an active reservation should not appear in FIFO results."""
        from app.models import ReelReservation, IssueOrder, IssueDetail

        # Create two pallets
        p1 = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=10.0, original_quantity=10.0,
            reel_barcode="RESERVED-1",
            first_in_time=base_time, last_in_time=base_time,
            status="on_shelf",
        )
        p2 = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=5.0, original_quantity=5.0,
            reel_barcode="FREE-1",
            first_in_time=base_time + timedelta(minutes=1),
            last_in_time=base_time + timedelta(minutes=1),
            status="on_shelf",
        )
        db_session.add_all([p1, p2])
        await db_session.commit()

        # Create a dummy issue order + detail + reservation for p1
        dummy_order = IssueOrder(
            order_no="DUM-RES", customer_id=sample_customer.id,
            production_quantity=1, status="assigned",
        )
        db_session.add(dummy_order)
        await db_session.flush()

        dummy_detail = IssueDetail(
            issue_order_id=dummy_order.id,
            material_id=sample_material.id,
            required_qty=1.0, status="completed",
        )
        db_session.add(dummy_detail)
        await db_session.flush()

        reservation = ReelReservation(
            reel_id=p1.id,
            issue_order_id=dummy_order.id,
            issue_detail_id=dummy_detail.id,
            reserved_qty=10.0,
            status="active",
        )
        db_session.add(reservation)
        await db_session.commit()

        # Now calculate FIFO — p1 should be excluded
        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=8.0, strategy="tail_first",
        )

        # Only p2 (qty=5) should be available
        assert len(result["reels"]) == 1
        assert result["reels"][0]["reel_id"] == p2.id
        assert result["total_selected"] == 5.0
        assert result["shortage"] == 3.0  # 8 - 5 = 3

    async def test_released_reservation_is_available(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """A released reservation should make the reel available again."""
        from app.models import ReelReservation, IssueOrder, IssueDetail

        p1 = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=10.0, original_quantity=10.0,
            reel_barcode="REL-1",
            first_in_time=base_time, last_in_time=base_time,
            status="on_shelf",
        )
        db_session.add(p1)
        await db_session.commit()

        dummy_order = IssueOrder(
            order_no="DUM-REL", customer_id=sample_customer.id,
            production_quantity=1, status="released",
        )
        db_session.add(dummy_order)
        await db_session.flush()

        dummy_detail = IssueDetail(
            issue_order_id=dummy_order.id,
            material_id=sample_material.id,
            required_qty=1.0, status="pending",
        )
        db_session.add(dummy_detail)
        await db_session.flush()

        # Reservation already consumed/released
        reservation = ReelReservation(
            reel_id=p1.id,
            issue_order_id=dummy_order.id,
            issue_detail_id=dummy_detail.id,
            reserved_qty=10.0,
            status="released",
            released_at=base_time,
        )
        db_session.add(reservation)
        await db_session.commit()

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=5.0, strategy="tail_first",
        )

        # p1 should be available (reservation is released)
        assert len(result["reels"]) == 1
        assert result["reels"][0]["reel_id"] == p1.id
        assert result["total_selected"] == 10.0
        assert result["shortage"] == 0

    async def test_consumed_reservation_is_available(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """A consumed reservation (after pickup) should also not block."""
        from app.models import ReelReservation, IssueOrder, IssueDetail

        p1 = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=10.0, original_quantity=10.0,
            reel_barcode="CONS-1",
            first_in_time=base_time, last_in_time=base_time,
            status="on_shelf",
        )
        db_session.add(p1)
        await db_session.commit()

        dummy_order = IssueOrder(
            order_no="DUM-CON", customer_id=sample_customer.id,
            production_quantity=1, status="completed",
        )
        db_session.add(dummy_order)
        await db_session.flush()

        dummy_detail = IssueDetail(
            issue_order_id=dummy_order.id,
            material_id=sample_material.id,
            required_qty=1.0, status="completed",
        )
        db_session.add(dummy_detail)
        await db_session.flush()

        reservation = ReelReservation(
            reel_id=p1.id,
            issue_order_id=dummy_order.id,
            issue_detail_id=dummy_detail.id,
            reserved_qty=10.0,
            status="consumed",
            released_at=base_time,
        )
        db_session.add(reservation)
        await db_session.commit()

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=5.0, strategy="tail_first",
        )

        assert len(result["reels"]) == 1
        assert result["reels"][0]["reel_id"] == p1.id


# =========================================================================
#  check_alternative_material (unchanged)
# =========================================================================

class TestCheckAlternativeMaterial:
    """Alternative material lookup."""

    async def test_returns_alternate_ids(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        alt_code = "RES-100K-ALT"
        alt = MaterialAlternative(
            original_code=sample_material.code,
            alternate_code=alt_code,
            customer_id=sample_customer.id,
            active=1,
        )
        db_session.add(alt)
        await db_session.commit()

        result = await check_alternative_material(
            db_session, sample_material.id, sample_customer.id,
        )

        assert alt_code in result

    async def test_returns_empty_when_none(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        result = await check_alternative_material(
            db_session, sample_material.id, sample_customer.id,
        )
        assert result == []

    async def test_inactive_alternatives_excluded(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        alt_active = MaterialAlternative(
            original_code=sample_material.code,
            alternate_code="RES-100K-ALT1",
            customer_id=sample_customer.id,
            active=1,
        )
        alt_inactive = MaterialAlternative(
            original_code=sample_material.code,
            alternate_code="RES-100K-ALT2",
            customer_id=sample_customer.id,
            active=0,
        )
        db_session.add_all([alt_active, alt_inactive])
        await db_session.commit()

        result = await check_alternative_material(
            db_session, sample_material.id, sample_customer.id,
        )

        assert "RES-100K-ALT1" in result
        assert "RES-100K-ALT2" not in result
