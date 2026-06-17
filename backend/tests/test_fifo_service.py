"""Unit tests for FIFO allocation service.

Covers all four strategies:
  - tail_first  : pick pallets with smallest quantity first (尾数优先)
  - time_fifo   : strict chronological order (先进先出)
  - mixed       : tail_first first, then time_fifo as tie-breaker
  - config      : resolves to the configured default strategy

Test categories:
  1. Basic FIFO selection (sufficient stock)
  2. Shortage scenarios (insufficient stock)
  3. Empty / edge cases (zero qty pallets, no pallets, etc.)
  4. Strategy-specific ordering verification
  5. Alternative material checks
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Customer,
    MaterialMaster,
    MaterialCategory,
    InventoryPallet,
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
) -> list[InventoryPallet]:
    """Create N pallets with given quantities and sequential timestamps.

    Returns the list of created pallets (ordered by creation).
    """
    now = base_time or datetime(2026, 6, 1, 10, 0, 0)
    pallets = []
    for i, qty in enumerate(quantities):
        t = now + timedelta(minutes=i)
        p = InventoryPallet(
            material_id=material_id,
            customer_id=customer_id,
            quantity=qty,
            original_quantity=qty,
            pallet_barcode=f"PALLET-{i:03d}",
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
    """Core FIFO calculation logic."""

    async def test_tail_first_selects_smallest_first(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """tail_first strategy: pallets with smallest qty picked first."""
        qties = [10.0, 3.0, 7.0, 1.0]  # expected order: 1,3,7,10
        await _make_pallets(db_session, sample_material.id, sample_customer.id, qties, base_time)

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=6.0, strategy="tail_first",
        )

        assert result["strategy_used"] == "tail_first"
        assert len(result["pallets"]) == 3  # 1+3+...7 would exceed 6, so only 1+3=4 + partial 7
        # First two should be the smallest: 1.0, 3.0
        assert result["pallets"][0]["quantity"] == 1.0
        assert result["pallets"][1]["quantity"] == 3.0
        # Third pick takes partial from 7.0 (remaining = 6 - 1 - 3 = 2)
        assert result["pallets"][2]["quantity"] == 2.0
        assert result["total_selected"] == 6.0
        assert result["shortage"] == 0

    async def test_time_fifo_strict_chronological(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """time_fifo: strictly earliest last_in_time first."""
        quantities = [5.0, 5.0, 5.0]
        pallets = await _make_pallets(
            db_session, sample_material.id, sample_customer.id, quantities, base_time
        )
        # pallets[0] has t=base, [1] has t=base+1m, [2] has t=base+2m

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=12.0, strategy="time_fifo",
        )

        assert result["strategy_used"] == "time_fifo"
        assert len(result["pallets"]) == 3
        # All 3 pallets picked: 5+5+2 (partial of third)
        assert result["pallets"][0]["pallet_id"] == pallets[0].id
        assert result["pallets"][1]["pallet_id"] == pallets[1].id
        assert result["pallets"][2]["pallet_id"] == pallets[2].id
        assert result["total_selected"] == 12.0
        assert result["shortage"] == 0

    async def test_mixed_strategy_tie_break(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """mixed: sort by (quantity, last_in_time)."""
        # Create: (qty=5, t=base+0)  (qty=3, t=base+1)  (qty=5, t=base+2)
        # mixed sort: 3 (qty asc), then 5@t0 (qty asc, time asc), then 5@t2
        t0 = base_time
        p1 = InventoryPallet(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=5.0, original_quantity=5.0,
            pallet_barcode="P-MIX-1",
            first_in_time=t0, last_in_time=t0,
            status="on_shelf",
        )
        p2 = InventoryPallet(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=3.0, original_quantity=3.0,
            pallet_barcode="P-MIX-2",
            first_in_time=t0 + timedelta(minutes=1), last_in_time=t0 + timedelta(minutes=1),
            status="on_shelf",
        )
        p3 = InventoryPallet(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=5.0, original_quantity=5.0,
            pallet_barcode="P-MIX-3",
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
        assert len(result["pallets"]) == 3
        # Expected order: p2 (qty=3), p1 (qty=5, time earlier), p3 (qty=5, time later)
        assert result["pallets"][0]["pallet_id"] == p2.id  # qty=3
        assert result["pallets"][1]["pallet_id"] == p1.id  # qty=5, earlier
        assert result["pallets"][2]["pallet_id"] == p3.id  # qty=5, later (partial: 2)
        assert result["total_selected"] == 10.0
        assert result["shortage"] == 0

    async def test_config_resolves_to_default_strategy(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """strategy='config' resolves to settings.FIFO_STRATEGY (default: tail_first)."""
        # Override config default for this test
        monkeypatch.setattr("app.config.settings.FIFO_STRATEGY", "time_fifo")

        quantities = [10.0, 5.0]
        await _make_pallets(db_session, sample_material.id, sample_customer.id, quantities, base_time)

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=3.0, strategy="config",
        )

        # Should resolve to time_fifo, not tail_first
        assert result["strategy_used"] == "time_fifo"
        # time_fifo picks pallet[0] (earliest) first → partial 3 from 10
        assert result["pallets"][0]["quantity"] == 3.0

    # ------------------------------------------------------------------
    #  Shortage scenarios
    # ------------------------------------------------------------------

    async def test_shortage_when_not_enough_stock(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """Shortage reported when total stock < required_qty."""
        await _make_pallets(db_session, sample_material.id, sample_customer.id, [3.0, 4.0], base_time)

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=10.0, strategy="tail_first",
        )

        assert result["total_selected"] == 7.0  # all stock used
        assert result["shortage"] == 3.0  # 10 - 7 = 3
        assert len(result["pallets"]) == 2

    async def test_exact_match_no_shortage(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """Required qty exactly matches total stock."""
        await _make_pallets(db_session, sample_material.id, sample_customer.id, [5.0, 3.0, 2.0], base_time)

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=10.0, strategy="tail_first",
        )

        assert result["total_selected"] == 10.0
        assert result["shortage"] == 0
        assert len(result["pallets"]) == 3

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

        assert result["pallets"] == []
        assert result["total_selected"] == 0
        assert result["shortage"] == 5.0

    async def test_zero_quantity_pallets_are_filtered(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """Pallets with quantity == 0 should be excluded."""
        p0 = InventoryPallet(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=0.0, original_quantity=5.0,
            pallet_barcode="ZERO-1",
            first_in_time=base_time, last_in_time=base_time,
            status="on_shelf",
        )
        p1 = InventoryPallet(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=3.0, original_quantity=3.0,
            pallet_barcode="OK-1",
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

        assert len(result["pallets"]) == 1
        assert result["pallets"][0]["pallet_id"] == p1.id

    async def test_exhausted_pallets_are_ignored(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """Only on_shelf pallets should be considered."""
        p_exhausted = InventoryPallet(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=10.0, original_quantity=10.0,
            pallet_barcode="EXHAUSTED",
            first_in_time=base_time, last_in_time=base_time,
            status="exhausted",  # should be excluded
        )
        db_session.add(p_exhausted)
        await db_session.commit()

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=1.0, strategy="tail_first",
        )

        assert result["pallets"] == []
        assert result["shortage"] == 1.0

    async def test_customer_scoped_isolation(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer, base_time: datetime,
    ):
        """Only pallets of the specified customer_id are selected."""
        # Create another customer
        other = Customer(name="其他客户", code="CUST002")
        db_session.add(other)
        await db_session.commit()

        # Pallet for sample_customer
        p_c1 = InventoryPallet(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=5.0, original_quantity=5.0,
            pallet_barcode="C1",
            first_in_time=base_time, last_in_time=base_time,
            status="on_shelf",
        )
        # Pallet for other customer
        p_c2 = InventoryPallet(
            material_id=sample_material.id, customer_id=other.id,
            quantity=5.0, original_quantity=5.0,
            pallet_barcode="C2",
            first_in_time=base_time, last_in_time=base_time,
            status="on_shelf",
        )
        db_session.add_all([p_c1, p_c2])
        await db_session.commit()

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=10.0, strategy="tail_first",
        )

        # Only c1's pallet should be selected
        assert len(result["pallets"]) == 1
        assert result["pallets"][0]["pallet_id"] == p_c1.id
        assert result["total_selected"] == 5.0
        assert result["shortage"] == 5.0


# =========================================================================
#  get_available_qty
# =========================================================================

class TestGetAvailableQty:
    """Total available quantity calculations."""

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
        p1 = InventoryPallet(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=10.0, original_quantity=10.0,
            pallet_barcode="TRACKING",
            first_in_time=base_time, last_in_time=base_time,
            status="tracking",
        )
        p2 = InventoryPallet(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=5.0, original_quantity=5.0,
            pallet_barcode="ON_SHELF",
            first_in_time=base_time + timedelta(minutes=1),
            last_in_time=base_time + timedelta(minutes=1),
            status="on_shelf",
        )
        db_session.add_all([p1, p2])
        await db_session.commit()

        total = await get_available_qty(db_session, sample_material.id, sample_customer.id)

        assert total == 5.0  # Only the on_shelf pallet


# =========================================================================
#  check_alternative_material
# =========================================================================

class TestCheckAlternativeMaterial:
    """Alternative material lookup."""

    async def test_returns_alternate_ids(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """Find alternative material codes registered in material_alternative."""
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
        """No alternatives registered → empty list."""
        result = await check_alternative_material(
            db_session, sample_material.id, sample_customer.id,
        )
        assert result == []

    async def test_inactive_alternatives_excluded(
        self, db_session: AsyncSession, sample_material: MaterialMaster,
        sample_customer: Customer,
    ):
        """Only active alternatives should be returned."""
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
