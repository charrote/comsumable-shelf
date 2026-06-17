"""Duplicate scan detection with configurable behavior.

System Setting: ``duplicate_scan_behavior``

    - ``block`` (default) — Reject duplicate scans with ``status="duplicate"``
    - ``warn``  — Allow the scan through but mark ``duplicate_flag=True`` and attach a warning
    - ``force`` — Bypass duplicate check entirely; treat every scan as first-time

Usage::

    from app.services.duplicate_check import check_duplicate_scan

    result = await check_duplicate_scan(db, barcode, customer_id)
    if result.action == "block":
        return ReceiptScanResponse(status="duplicate", ...)
    # else proceed normally, optionally reading result.warning / result.duplicate_flag
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import SystemSetting, InventoryReel


# ── Setting key & valid values ──────────────────────────────────────────────

SETTING_KEY = "duplicate_scan_behavior"
VALID_VALUES = ("block", "warn", "force")
DEFAULT_VALUE = "block"


# ── Result DTO ──────────────────────────────────────────────────────────────

class DuplicateCheckResult:
    """Return value from :func:`check_duplicate_scan`."""

    __slots__ = ("duplicate", "action", "existing_reel_id", "warning", "message")

    def __init__(
        self,
        duplicate: bool,
        action: str = "allow",
        existing_reel_id: Optional[int] = None,
        warning: str = "",
        message: str = "",
    ):
        self.duplicate = duplicate
        self.action = action           # "block" | "warn" | "allow"
        self.existing_reel_id = existing_reel_id
        self.warning = warning
        self.message = message


# ── Public API ──────────────────────────────────────────────────────────────

async def check_duplicate_scan(
    db: AsyncSession,
    barcode: str,
    customer_id: int,
) -> DuplicateCheckResult:
    """Check whether *barcode* is a duplicate scan and return the configured action.

    Steps:
        1. Read ``duplicate_scan_behavior`` from system settings (cached per-call).
        2. If ``force`` → skip DB lookup; return ``allow`` immediately.
        3. Otherwise query ``InventoryReel`` for the same barcode + active statuses.
        4. If no duplicate found → return ``allow``.
        5. If duplicate found → return ``block`` or ``warn`` according to setting.
    """
    behavior = await _read_behavior(db)

    # ── force: skip duplicate check entirely ──
    if behavior == "force":
        return DuplicateCheckResult(duplicate=False, action="allow")

    # ── block / warn: perform DB lookup ──
    result = await db.execute(
        select(InventoryReel).where(
            InventoryReel.reel_barcode == barcode,
            InventoryReel.status.in_(["on_shelf", "tracking"]),
        )
    )
    dup = result.scalar_one_or_none()

    if dup is None:
        return DuplicateCheckResult(duplicate=False, action="allow")

    # ── Duplicate found ──
    if behavior == "warn":
        return DuplicateCheckResult(
            duplicate=True,
            action="warn",
            existing_reel_id=dup.id,
            warning=f"条码 {barcode} 已在库存中（盘 #{dup.id}）",
            message="该条码已存在，允许通过（警告模式）",
        )

    # behavior == "block" (default)
    return DuplicateCheckResult(
        duplicate=True,
        action="block",
        existing_reel_id=dup.id,
        warning=f"条码 {barcode} 已在库存中（盘 #{dup.id}）",
        message="该条码已存在，已拦截",
    )


# ── Helpers ─────────────────────────────────────────────────────────────────

async def _read_behavior(db: AsyncSession) -> str:
    """Read ``duplicate_scan_behavior`` from DB, falling back to DEFAULT_VALUE."""
    row = await db.execute(
        select(SystemSetting.value).where(SystemSetting.key == SETTING_KEY)
    )
    val = row.scalar_one_or_none()
    if val and val in VALID_VALUES:
        return val
    return DEFAULT_VALUE
