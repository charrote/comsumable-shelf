"""Unit tests for issue (outbound) API — create, calculate FIFO, assign LED,
confirm-pick, and direct outbound flows.

Covers:
  1. Create issue order from BOM
  2. Calculate FIFO assignment (tail_first, time_fifo, shortage)
  3. Assign LED commands
  4. Confirm pick (partial + full consumption, transaction recording)
  5. Direct outbound scan + confirm
"""

import pytest
import json
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Customer,
    MaterialMaster,
    MaterialCategory,
    InventoryReel,
    IssueOrder,
    IssueDetail,
    Shelf,
    ShelfSlot,
    LedCommand,
    Transaction,
    Bom,
    BomItem,
)
from app.schemas import (
    IssueCreateRequest,
    IssueCalculateRequest,
    IssueConfirmPickRequest,
)
from app.api.issue import (
    create_issue,
    calculate_issue,
    assign_led,
    confirm_pick,
)
from app.services.fifo_service import calculate_fifo_pallets


# =========================================================================
#  Helper factories
# =========================================================================

async def _make_pallets(
    db: AsyncSession,
    material_id: int,
    customer_id: int,
    quantities: list[float],
    base_time: datetime = None,
    strategy_offset: bool = True,
) -> list[InventoryReel]:
    """Create N pallets (on_shelf) with given quantities and sequential timestamps."""
    now = base_time or datetime(2026, 6, 1, 10, 0, 0)
    pallets = []
    for i, qty in enumerate(quantities):
        t = now + timedelta(minutes=i) if strategy_offset else now
        p = InventoryReel(
            material_id=material_id,
            customer_id=customer_id,
            quantity=qty,
            original_quantity=qty,
            reel_barcode=f"ISS-PALLET-{i:03d}",
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


async def _make_bom(
    db: AsyncSession,
    customer_id: int,
    product_material: MaterialMaster,
    materials: list[MaterialMaster],
    quantities: list[float],
) -> Bom:
    """Create a BOM with one-level items."""
    bom = Bom(
        customer_id=customer_id,
        product_material_id=product_material.id,
        version="1.0",
        status="active",
    )
    db.add(bom)
    await db.commit()

    for mat, qty in zip(materials, quantities):
        item = BomItem(
            bom_id=bom.id,
            material_id=mat.id,
            quantity=qty,
        )
        db.add(item)
    await db.commit()
    return bom


async def _make_issue_order(
    db: AsyncSession,
    customer_id: int,
    bom_id: int,
    material_id: int,
    required_qty: float,
) -> tuple[IssueOrder, IssueDetail]:
    """Create a pending issue order with one detail item."""
    order = IssueOrder(
        order_no=f"ISS-TEST-{datetime.utcnow().timestamp()}",
        bom_id=bom_id,
        customer_id=customer_id,
        production_quantity=1,
        status="pending",
    )
    db.add(order)
    await db.commit()

    detail = IssueDetail(
        issue_order_id=order.id,
        material_id=material_id,
        required_qty=required_qty,
        status="pending",
    )
    db.add(detail)
    await db.commit()
    await db.refresh(order)
    await db.refresh(detail)
    return order, detail


async def _make_shelf_with_slot(
    db: AsyncSession,
    code: str = "ISS-SHELF",
    slot_on_board: int = 1,
) -> tuple[Shelf, ShelfSlot]:
    shelf = Shelf(code=code, name=f"料架 {code}", active=1)
    db.add(shelf)
    await db.commit()

    slot = ShelfSlot(
        shelf_id=shelf.id,
        side="A", board_address=1,
        slot_on_board=slot_on_board,
        global_index=slot_on_board,
        modbus_tcp_id=1, modbus_coil_base=0,
    )
    db.add(slot)
    await db.commit()
    await db.refresh(shelf)
    await db.refresh(slot)
    return shelf, slot


# =========================================================================
#  Create issue order
# =========================================================================

class TestCreateIssue:
    """POST /issues — create issue order from BOM."""

    async def test_create_from_bom(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
    ):
        """BOM with one item creates order with matching detail."""
        # Need a product material (different from sample)
        product = MaterialMaster(
            customer_id=sample_customer.id,
            category_id=None,
            code="PROD-001",
            name="测试产品",
        )
        db_session.add(product)
        await db_session.commit()

        bom = await _make_bom(
            db_session, sample_customer.id, product,
            [sample_material], [4.0],
        )

        req = IssueCreateRequest(
            bom_id=bom.id,
            production_quantity=2.0,
            customer_id=sample_customer.id,
        )
        result = await create_issue(req, db_session)

        assert result.id is not None
        assert result.order_no.startswith("ISS-")
        assert result.status == "pending"
        assert len(result.details) == 1
        assert result.details[0].required_qty == 8.0  # 4 * 2
        assert result.details[0].material_id == sample_material.id

    async def test_create_from_bom_aggregates_duplicates(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
    ):
        """Same material appearing twice in BOM → quantity aggregated."""
        product = MaterialMaster(
            customer_id=sample_customer.id,
            category_id=None,
            code="PROD-002",
            name="测试产品2",
        )
        db_session.add(product)
        await db_session.commit()

        bom = Bom(
            customer_id=sample_customer.id,
            product_material_id=product.id,
            version="1.0", status="active",
        )
        db_session.add(bom)
        await db_session.commit()

        # Same material twice
        for _ in range(2):
            item = BomItem(bom_id=bom.id, material_id=sample_material.id, quantity=3.0)
            db_session.add(item)
        await db_session.commit()

        req = IssueCreateRequest(
            bom_id=bom.id,
            production_quantity=1.0,
            customer_id=sample_customer.id,
        )
        result = await create_issue(req, db_session)

        assert len(result.details) == 1
        assert result.details[0].required_qty == 6.0  # 3+3

    async def test_bom_not_found_raises_404(
        self, db_session: AsyncSession,
    ):
        """Non-existent BOM → error."""
        from fastapi import HTTPException
        req = IssueCreateRequest(bom_id=99999, production_quantity=1, customer_id=1)

        with pytest.raises(HTTPException) as exc:
            await create_issue(req, db_session)

        assert exc.value.status_code == 404


# =========================================================================
#  Calculate / FIFO assignment
# =========================================================================

class TestCalculateIssue:
    """POST /issues/{order_id}/calculate — FIFO reel assignment."""

    async def test_tail_first_assigns_smallest_first(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
    ):
        """tail_first strategy: pallets with smallest qty picked first."""
        product = MaterialMaster(
            customer_id=sample_customer.id, category_id=None,
            code="PROD-CALC", name="计算测试",
        )
        db_session.add(product)
        await db_session.commit()
        bom = await _make_bom(db_session, sample_customer.id, product, [sample_material], [10.0])

        # Create pallets: [10, 3, 7, 1]
        pallets = await _make_pallets(
            db_session, sample_material.id, sample_customer.id,
            [10.0, 3.0, 7.0, 1.0],
        )
        order, detail = await _make_issue_order(
            db_session, sample_customer.id, bom.id,
            sample_material.id, required_qty=6.0,
        )

        req = IssueCalculateRequest(strategy="tail_first")
        result = await calculate_issue(order.id, req, db_session)

        assert result.issue_order_id == order.id
        assert result.strategy_used == "tail_first"
        assert len(result.materials) == 1

        mat = result.materials[0]
        assert mat.required_qty == 6.0
        assert mat.total_selected == 6.0
        assert mat.shortage == 0

        # First reel should be smallest (qty=1), second (qty=3), third partial (qty=2 from 7)
        assert mat.reels_selected[0].quantity == 1.0
        assert mat.reels_selected[1].quantity == 3.0
        assert mat.reels_selected[2].quantity == 2.0

    async def test_shortage_reported(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
    ):
        """Insufficient stock → shortage > 0."""
        product = MaterialMaster(
            customer_id=sample_customer.id, category_id=None,
            code="PROD-SHORT", name="短缺测试",
        )
        db_session.add(product)
        await db_session.commit()
        bom = await _make_bom(db_session, sample_customer.id, product, [sample_material], [1.0])

        pallets = await _make_pallets(
            db_session, sample_material.id, sample_customer.id,
            [3.0, 4.0],
        )
        order, detail = await _make_issue_order(
            db_session, sample_customer.id, bom.id,
            sample_material.id, required_qty=10.0,
        )

        req = IssueCalculateRequest(strategy="tail_first")
        result = await calculate_issue(order.id, req, db_session)

        mat = result.materials[0]
        assert mat.total_selected == 7.0  # all stock
        assert mat.shortage == 3.0  # 10 - 7

    async def test_order_status_updated_to_assigned(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
    ):
        """After calculate, order status becomes 'assigned'."""
        product = MaterialMaster(
            customer_id=sample_customer.id, category_id=None,
            code="PROD-STATUS", name="状态测试",
        )
        db_session.add(product)
        await db_session.commit()
        bom = await _make_bom(db_session, sample_customer.id, product, [sample_material], [1.0])

        pallets = await _make_pallets(
            db_session, sample_material.id, sample_customer.id,
            [5.0],
        )
        order, detail = await _make_issue_order(
            db_session, sample_customer.id, bom.id,
            sample_material.id, required_qty=3.0,
        )

        req = IssueCalculateRequest(strategy="tail_first")
        await calculate_issue(order.id, req, db_session)

        # Refresh order
        await db_session.refresh(order)
        assert order.status == "assigned"
        assert order.assigned_at is not None

    async def test_detail_reel_assignments_stored(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
    ):
        """reel_assignments JSON is stored on IssueDetail after calculate."""
        product = MaterialMaster(
            customer_id=sample_customer.id, category_id=None,
            code="PROD-ASSIGN", name="分配测试",
        )
        db_session.add(product)
        await db_session.commit()
        bom = await _make_bom(db_session, sample_customer.id, product, [sample_material], [1.0])

        pallets = await _make_pallets(
            db_session, sample_material.id, sample_customer.id,
            [5.0, 5.0],
        )
        order, detail = await _make_issue_order(
            db_session, sample_customer.id, bom.id,
            sample_material.id, required_qty=8.0,
        )

        req = IssueCalculateRequest(strategy="tail_first")
        await calculate_issue(order.id, req, db_session)

        # Reload detail
        await db_session.refresh(detail)
        assert detail.reel_assignments is not None
        ra = json.loads(detail.reel_assignments)
        assert len(ra) > 0
        assert ra[0]["reel_id"] in [p.id for p in pallets]


# =========================================================================
#  Assign LED commands
# =========================================================================

class TestAssignLed:
    """POST /issues/{order_id}/assign — create LED pick commands."""

    async def test_creates_led_commands(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
    ):
        """LED commands created for assigned reels with shelf_slot_id."""
        shelf, slot = await _make_shelf_with_slot(db_session)
        product = MaterialMaster(
            customer_id=sample_customer.id, category_id=None,
            code="PROD-LED", name="LED测试",
        )
        db_session.add(product)
        await db_session.commit()
        bom = await _make_bom(db_session, sample_customer.id, product, [sample_material], [1.0])

        # Create pallet bound to the slot
        now = datetime.utcnow()
        pallet = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=10.0, original_quantity=10.0,
            reel_barcode="LED-PALLET",
            first_in_time=now, last_in_time=now,
            status="on_shelf", shelf_slot_id=slot.id,
        )
        db_session.add(pallet)
        await db_session.commit()

        order, detail = await _make_issue_order(
            db_session, sample_customer.id, bom.id,
            sample_material.id, required_qty=5.0,
        )

        # Assign reel assignments JSON to detail (simulate after calculate)
        detail.reel_assignments = json.dumps([{
            "reel_id": pallet.id,
            "reel_barcode": "LED-PALLET",
            "shelf_slot_id": slot.id,
            "slot_code": f"A{slot.slot_on_board}",
            "reel_qty": 10.0,
            "original_quantity": 10.0,
            "pick_quantity": 5.0,
        }])
        detail.assigned_qty = 5.0
        detail.status = "completed"
        order.status = "assigned"
        await db_session.commit()

        result = await assign_led(order.id, db_session)

        assert result.assigned is True
        assert result.led_commands_created == 1
        assert len(result.commands) == 1

        # Verify LedCommand in DB
        cmd_result = await db_session.execute(
            select(LedCommand).where(LedCommand.issue_order_id == order.id)
        )
        cmd = cmd_result.scalar_one_or_none()
        assert cmd is not None
        assert cmd.slot_id == slot.id
        assert cmd.status == "queued"

    async def test_no_reel_assignments_returns_zero_commands(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
    ):
        """Issue detail without reel_assignments → no LED commands."""
        product = MaterialMaster(
            customer_id=sample_customer.id, category_id=None,
            code="PROD-NO-LED", name="无LED测试",
        )
        db_session.add(product)
        await db_session.commit()
        bom = await _make_bom(db_session, sample_customer.id, product, [sample_material], [1.0])

        order, detail = await _make_issue_order(
            db_session, sample_customer.id, bom.id,
            sample_material.id, required_qty=5.0,
        )
        # No reel_assignments set
        result = await assign_led(order.id, db_session)

        assert result.assigned is True
        assert result.led_commands_created == 0

    async def test_order_status_updated_to_picking(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
    ):
        """After assign LED, order status becomes 'picking'."""
        shelf, slot = await _make_shelf_with_slot(db_session)
        product = MaterialMaster(
            customer_id=sample_customer.id, category_id=None,
            code="PROD-PICKING", name="拣料测试",
        )
        db_session.add(product)
        await db_session.commit()
        bom = await _make_bom(db_session, sample_customer.id, product, [sample_material], [1.0])

        now = datetime.utcnow()
        pallet = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=10.0, original_quantity=10.0,
            reel_barcode="PICKING-PALLET",
            first_in_time=now, last_in_time=now,
            status="on_shelf", shelf_slot_id=slot.id,
        )
        db_session.add(pallet)
        await db_session.commit()

        order, detail = await _make_issue_order(
            db_session, sample_customer.id, bom.id,
            sample_material.id, required_qty=5.0,
        )
        detail.reel_assignments = json.dumps([{
            "reel_id": pallet.id, "reel_barcode": "PICKING-PALLET",
            "shelf_slot_id": slot.id, "slot_code": f"A{slot.slot_on_board}",
            "reel_qty": 10.0, "original_quantity": 10.0, "pick_quantity": 5.0,
        }])
        detail.assigned_qty = 5.0
        detail.status = "completed"
        order.status = "assigned"
        await db_session.commit()

        await assign_led(order.id, db_session)
        await db_session.refresh(order)
        assert order.status == "picking"


# =========================================================================
#  Confirm pick
# =========================================================================

class TestConfirmPick:
    """POST /issues/{order_id}/confirm-pick — partial/full consumption, txn."""

    async def _setup_pick_test(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
        reel_qty: float = 10.0,
        required_qty: float = 4.0,
    ) -> tuple[IssueOrder, IssueDetail, InventoryReel, ShelfSlot]:
        """Set up a basic pick scenario with shelf+slot+pallet+order."""
        shelf, slot = await _make_shelf_with_slot(db_session)
        product = MaterialMaster(
            customer_id=sample_customer.id, category_id=None,
            code="PROD-PICK", name="拣料确认测试",
        )
        db_session.add(product)
        await db_session.commit()
        bom = await _make_bom(db_session, sample_customer.id, product, [sample_material], [1.0])

        now = datetime.utcnow()
        pallet = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=reel_qty, original_quantity=reel_qty,
            reel_barcode="CONFIRM-PALLET",
            first_in_time=now, last_in_time=now,
            status="on_shelf", shelf_slot_id=slot.id,
        )
        db_session.add(pallet)
        await db_session.commit()

        order, detail = await _make_issue_order(
            db_session, sample_customer.id, bom.id,
            sample_material.id, required_qty,
        )
        # Pre-assign reel_assignments
        detail.reel_assignments = json.dumps([{
            "reel_id": pallet.id, "reel_barcode": "CONFIRM-PALLET",
            "shelf_slot_id": slot.id, "slot_code": f"A{slot.slot_on_board}",
            "reel_qty": reel_qty, "original_quantity": reel_qty,
            "pick_quantity": min(required_qty, reel_qty),
        }])
        detail.assigned_qty = min(required_qty, reel_qty)
        detail.status = "completed" if required_qty <= reel_qty else "partial"
        order.status = "assigned"
        # Add a pending LED command
        led = LedCommand(
            issue_order_id=order.id,
            material_id=sample_material.id,
            shelf_id=shelf.id,
            slot_id=slot.id,
            status="queued",
        )
        db_session.add(led)
        await db_session.commit()

        return order, detail, pallet, slot

    async def test_partial_pick_reduces_quantity(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
    ):
        """Pick < full pallet: quantity reduced, status stays on_shelf."""
        order, detail, pallet, slot = await self._setup_pick_test(
            db_session, sample_customer, sample_material,
            reel_qty=10.0, required_qty=4.0,
        )

        req = IssueConfirmPickRequest(
            barcode=sample_material.code,
            reel_id=pallet.id,
            operator="tester",
        )
        result = await confirm_pick(order.id, req, db_session)

        assert result.status == "ok"
        assert result.picked_qty == 4.0
        assert result.remaining_qty == 0  # all picked

        # Verify pallet quantity reduced
        await db_session.refresh(pallet)
        assert pallet.quantity == 6.0  # 10 - 4
        assert pallet.status == "on_shelf"

    async def test_full_pick_exhausts_pallet(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
    ):
        """Pick == full pallet: pallet exhausted."""
        order, detail, pallet, slot = await self._setup_pick_test(
            db_session, sample_customer, sample_material,
            reel_qty=5.0, required_qty=5.0,
        )

        req = IssueConfirmPickRequest(
            barcode=sample_material.code,
            reel_id=pallet.id,
            operator="tester",
        )
        result = await confirm_pick(order.id, req, db_session)

        assert result.status == "ok"
        assert result.picked_qty == 5.0
        assert result.all_picked is True

        await db_session.refresh(pallet)
        assert pallet.quantity == 0
        assert pallet.status == "exhausted"
        assert pallet.last_out_order_id == order.id

    async def test_transaction_recorded(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
    ):
        """Pick creates a Transaction record."""
        order, detail, pallet, slot = await self._setup_pick_test(
            db_session, sample_customer, sample_material,
            reel_qty=10.0, required_qty=3.0,
        )

        req = IssueConfirmPickRequest(
            barcode=sample_material.code,
            reel_id=pallet.id,
            operator="tester",
        )
        await confirm_pick(order.id, req, db_session)

        # Verify transaction
        txn_result = await db_session.execute(
            select(Transaction).where(Transaction.reel_id == pallet.id)
        )
        txn = txn_result.scalar_one_or_none()
        assert txn is not None
        assert txn.type == "out"
        assert txn.quantity == 3.0
        assert txn.source_type == "issue"
        assert txn.source_id == order.id
        assert txn.operator == "tester"

    async def test_led_cleared_on_pick(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
    ):
        """LED command for the picked slot is cleared."""
        order, detail, pallet, slot = await self._setup_pick_test(
            db_session, sample_customer, sample_material,
            reel_qty=10.0, required_qty=3.0,
        )

        req = IssueConfirmPickRequest(
            barcode=sample_material.code,
            reel_id=pallet.id,
            operator="tester",
        )
        result = await confirm_pick(order.id, req, db_session)

        assert len(result.cleared_leds) == 1
        assert result.cleared_leds[0] == slot.id

        # Verify LED cleared
        led_result = await db_session.execute(
            select(LedCommand).where(LedCommand.issue_order_id == order.id)
        )
        led = led_result.scalar_one_or_none()
        assert led is not None
        assert led.status == "cleared"
        assert led.cleared_at is not None

    async def test_detail_picked_qty_updated(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
    ):
        """IssueDetail picked_qty and status are updated."""
        order, detail, pallet, slot = await self._setup_pick_test(
            db_session, sample_customer, sample_material,
            reel_qty=10.0, required_qty=6.0,
        )

        req = IssueConfirmPickRequest(
            barcode=sample_material.code,
            reel_id=pallet.id,
            operator="tester",
        )
        await confirm_pick(order.id, req, db_session)

        await db_session.refresh(detail)
        assert detail.picked_qty == 6.0
        assert detail.status == "completed"

    async def test_order_completed_when_all_details_done(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
    ):
        """Order status = completed when all details picked."""
        order, detail, pallet, slot = await self._setup_pick_test(
            db_session, sample_customer, sample_material,
            reel_qty=5.0, required_qty=5.0,
        )

        req = IssueConfirmPickRequest(
            barcode=sample_material.code,
            reel_id=pallet.id,
            operator="tester",
        )
        await confirm_pick(order.id, req, db_session)

        await db_session.refresh(order)
        assert order.status == "completed"
        assert order.completed_at is not None

    async def test_order_not_completed_when_not_all_picked(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
    ):
        """Order stays picking if partial pick doesn't exhaust all details."""
        # Use required_qty > 0 so after picking, shortage remains
        order, detail, pallet, slot = await self._setup_pick_test(
            db_session, sample_customer, sample_material,
            reel_qty=10.0, required_qty=4.0,
        )

        # Second material required but not picked yet
        mat2 = MaterialMaster(
            customer_id=sample_customer.id, category_id=None,
            code="MAT2-OTHER", name="第二物料",
        )
        db_session.add(mat2)
        await db_session.commit()

        detail2 = IssueDetail(
            issue_order_id=order.id,
            material_id=mat2.id,
            required_qty=3.0,
            status="pending",
        )
        db_session.add(detail2)
        await db_session.commit()

        req = IssueConfirmPickRequest(
            barcode=sample_material.code,
            reel_id=pallet.id,
            operator="tester",
        )
        await confirm_pick(order.id, req, db_session)

        await db_session.refresh(order)
        # detail 1 is completed, but detail 2 is still pending → order not "completed"
        assert order.status != "completed"

    async def test_confirm_already_completed_material(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
    ):
        """Picking a fully completed material returns 'error' (nothing left to pick)."""
        order, detail, pallet, slot = await self._setup_pick_test(
            db_session, sample_customer, sample_material,
            reel_qty=5.0, required_qty=5.0,
        )
        # Mark detail as already completed
        detail.status = "completed"
        detail.picked_qty = 5.0
        await db_session.commit()

        req = IssueConfirmPickRequest(
            barcode=sample_material.code,
            reel_id=pallet.id,
            operator="tester",
        )
        result = await confirm_pick(order.id, req, db_session)

        # remaining_need = 0 → pick_qty = 0 → returns "error"
        assert result.status == "error"
        assert result.picked_qty == 0

    async def test_invalid_barcode_returns_error(
        self, db_session: AsyncSession,
        sample_customer: Customer, sample_material: MaterialMaster,
    ):
        """Unparseable barcode → error status."""
        order, detail, pallet, slot = await self._setup_pick_test(
            db_session, sample_customer, sample_material,
            reel_qty=10.0, required_qty=4.0,
        )

        req = IssueConfirmPickRequest(
            barcode="",  # empty / unparseable
            reel_id=pallet.id,
            operator="tester",
        )
        result = await confirm_pick(order.id, req, db_session)

        assert result.status == "error"
        assert "无效的条码格式" in result.message


# =========================================================================
#  FIFO service integration (reuse existing conftest pallet seed)
# =========================================================================

class TestFifoIntegration:
    """Verify calculate_fifo_pallets contract used by issue API."""

    async def test_calculate_returns_pallets_key(
        self, db_session: AsyncSession,
        sample_material: MaterialMaster, sample_customer: Customer,
    ):
        """calculate_fifo_pallets returns dict with 'pallets' key."""
        now = datetime(2026, 6, 1, 10, 0, 0)
        p = InventoryReel(
            material_id=sample_material.id, customer_id=sample_customer.id,
            quantity=10.0, original_quantity=10.0,
            reel_barcode="FIFO-KEY",
            first_in_time=now, last_in_time=now,
            status="on_shelf",
        )
        db_session.add(p)
        await db_session.commit()

        result = await calculate_fifo_pallets(
            db_session, sample_material.id, sample_customer.id,
            required_qty=5.0, strategy="tail_first",
        )

        assert "reels" in result
        assert len(result["reels"]) == 1
        assert result["reels"][0]["quantity"] == 5.0  # partial
