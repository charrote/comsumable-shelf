"""Pydantic schemas for API request/response validation."""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


# ---------- Auth ----------
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None


# ---------- Material ----------
class MaterialCreate(BaseModel):
    code: str
    name: str
    spec: Optional[str] = None
    category_id: Optional[int] = None
    qty_per_pallet: Optional[float] = None
    barcode_pattern: Optional[str] = None


class MaterialResponse(BaseModel):
    id: int
    code: str
    name: str
    spec: Optional[str] = None
    unit: str = "盘"
    qty_per_pallet: Optional[float] = None
    category: Optional[str] = None
    stock_balance: Optional[float] = None


# ---------- Receipt ----------
class ReceiptCreate(BaseModel):
    type: str = "normal"
    operator: str


class ReceiptScanRequest(BaseModel):
    barcode: str
    operator: str


class ReceiptScanResponse(BaseModel):
    status: str
    action: str  # first_in | restock | duplicate
    inventory_pallet_id: Optional[int] = None
    assigned_slot: Optional[int] = None
    duplicate_flag: bool = False
    warning: Optional[str] = None
    message: str


class ReceiptAssignSlotRequest(BaseModel):
    receipt_detail_id: int
    shelf_slot_id: int


class ReceiptDetailResponse(BaseModel):
    id: int
    receipt_no: str
    customer_id: int
    created_at: datetime
    operator: str
    status: str  # draft | confirmed | completed
    items: List[dict] = []


# ---------- Issue ----------
class IssueCalculateRequest(BaseModel):
    strategy: str = "config"  # config | tail_first | time_fifo


class PalletSelection(BaseModel):
    pallet_id: int
    quantity: float
    last_in_time: datetime
    shelf_slot_id: int


class MaterialCalcResult(BaseModel):
    material_id: int
    material_code: str
    material_name: str
    required_qty: float
    available_qty: float
    strategy: str
    pallets_selected: List[PalletSelection]
    total_selected: float
    shortage: float


class IssueCalculateResponse(BaseModel):
    issue_order_id: int
    calculated_at: datetime
    strategy_used: str
    materials: List[MaterialCalcResult]


class IssueAssignResponse(BaseModel):
    assigned: bool
    led_commands_created: int
    shelf_id: int
    commands: List[dict]
    message: str


class IssueConfirmPickRequest(BaseModel):
    barcode: str
    pallet_id: int
    operator: str


class IssueConfirmPickResponse(BaseModel):
    status: str  # ok | duplicate_out | completed
    picked_qty: float
    remaining_qty: float
    all_picked: bool
    cleared_leds: List[int]
    message: str


# ---------- Inventory ----------
class InventoryResponse(BaseModel):
    pallets: List[dict]
    summary: dict


class TrackingPalletResponse(BaseModel):
    pallet_id: int
    material_code: str
    quantity: float
    last_out_time: Optional[datetime] = None
    status: str = "tracking"
    xr_matched: bool = False


# ---------- XR ----------
class XrUploadRequest(BaseModel):
    reel_id: str
    qty: float


class XrUploadResponse(BaseModel):
    success: bool
    code: int
    message: str


class XrMatchRequest(BaseModel):
    xr_batch_id: int
    inventory_pallet_id: int


class XrRestockRequest(BaseModel):
    shelf_slot_id: int


# ---------- BOM ----------
class BomUploadResponse(BaseModel):
    bom_header_id: int
    bom_name: str
    parsed: bool
    total_items: int
    unique_materials: int
    alternates_found: int


class BomDetailResponse(BaseModel):
    id: int
    material_code: str
    material_name: str
    quantity: float
    unit: str = "盘"
    alternate_code: Optional[str] = None
    alternate_name: Optional[str] = None


class BomGenerateIssueRequest(BaseModel):
    customer_id: int
    required_date: Optional[str] = None


# ---------- Report ----------
class DailyReportSummary(BaseModel):
    total_materials: int
    total_in: float
    total_out: float
    total_balance: float
    total_pallets_on_shelf: int
    total_pallets_tracking: int


class DailyReportDetail(BaseModel):
    material_id: int
    material_code: str
    material_name: str
    opening_balance: float
    in_qty: float
    out_qty: float
    closing_balance: float
    pallets_on_shelf: int
    pallets_tracking: int


class DailyReportResponse(BaseModel):
    report_date: str
    customer_id: int
    customer_name: str
    summary: DailyReportSummary
    details: List[DailyReportDetail]


class CustomerSummaryResponse(BaseModel):
    customer_name: str
    period: str
    by_category: List[dict]


# ---------- Shelf ----------
class ShelfCreate(BaseModel):
    code: str
    name: Optional[str] = None
    a_sides: int = 0
    b_sides: int = 0
    controller_ip: Optional[str] = None
    controller_port: int = 502
    location: Optional[str] = None


class ShelfResponse(BaseModel):
    id: int
    code: str
    name: Optional[str] = None
    a_sides: int
    b_sides: int
    total_slots: int
    controller_ip: Optional[str] = None
    controller_port: int = 502
    a_side_count: int
    b_side_count: int
    location: Optional[str] = None
    active: int = 1


class ShelfSlotCreate(BaseModel):
    side: str
    board_address: int
    slot_on_board: int
    global_index: int
    modbus_coil_base: int


class ShelfSlotResponse(BaseModel):
    id: int
    shelf_id: int
    side: str
    board_address: int
    slot_on_board: int
    global_index: int
    modbus_tcp_id: int
    modbus_coil_base: int


# ---------- System Settings ----------
class SystemSettingUpdate(BaseModel):
    key: str
    value: str
    description: Optional[str] = None


class SystemSettingResponse(BaseModel):
    key: str
    value: str
    description: Optional[str] = None
    updated_at: Optional[datetime] = None


# ---------- General ----------
class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
