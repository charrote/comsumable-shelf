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
    unit: Optional[str] = "个"
    category_id: Optional[int] = None
    qty_per_pallet: Optional[float] = None
    barcode_pattern: Optional[str] = None
    active: Optional[int] = None


class MaterialUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    spec: Optional[str] = None
    unit: Optional[str] = None
    category_id: Optional[int] = None
    qty_per_pallet: Optional[float] = None
    barcode_pattern: Optional[str] = None
    active: Optional[int] = None


class MaterialResponse(BaseModel):
    id: int
    code: str
    name: str
    spec: Optional[str] = None
    unit: str = "盘"
    qty_per_pallet: Optional[float] = None
    category: Optional[str] = None
    stock_balance: Optional[float] = None
    active: int = 1


class MaterialUploadResponse(BaseModel):
    total: int = 0
    imported: int = 0
    skipped: int = 0
    categories_created: int = 0


# ---------- Customer Material Mapping ----------
class CustomerMaterialMappingCreate(BaseModel):
    customer_id: int
    customer_material_code: str = Field(..., min_length=1)
    internal_material_id: int


class CustomerMaterialMappingUpdate(BaseModel):
    customer_material_code: Optional[str] = None
    internal_material_id: Optional[int] = None
    active: Optional[int] = None


class CustomerMaterialMappingResponse(BaseModel):
    id: int
    customer_id: int
    customer_material_code: str
    internal_material_id: int
    internal_material_code: str = ""
    internal_material_name: str = ""
    customer_name: str = ""
    active: int = 1
    created_at: Optional[datetime] = None


# ---------- Receipt ----------
class ManualEntryRequest(BaseModel):
    """手工录入请求 — 无条码标签的手工入库。"""
    operator: str = Field(..., min_length=1)
    material_code: str = Field(..., min_length=1, description="物料编码")
    material_name: str = Field("", description="物料名称（留空则用编码）")
    spec: Optional[str] = Field(None, description="规格型号")
    quantity: float = Field(1.0, gt=0, description="入库数量")
    batch_no: Optional[str] = Field(None, description="批次号")
    date_code: Optional[str] = Field(None, description="生产日期/周期")
    supplier_code: Optional[str] = Field(None, description="供应商代码")
    print_label: Optional[bool] = Field(False, description="是否打印标签")
    printer_ip: Optional[str] = Field(None, description="标签打印机 IP")
    printer_port: Optional[int] = Field(None, description="标签打印机端口")


class BarcodePreviewItem(BaseModel):
    field: str
    label: str
    value: str
    editable: bool = True


class ReceiptCreate(BaseModel):
    type: str = "normal"
    operator: str
    customer_id: int = 1


class MaterialCandidate(BaseModel):
    """Candidate material match for human review."""
    material_id: int
    code: str
    name: str
    confidence: float
    extracted_code: str = ""


class BarcodePreviewResponse(BaseModel):
    barcode: str
    status: str  # ok | pending_review | new_material
    confidence: float
    material_code: str
    material_name: str = ""
    material_id: Optional[int] = None
    quantity: Optional[float] = None
    unit: str = "盘"
    batch_no: Optional[str] = None
    date_code: Optional[str] = None
    spec: Optional[str] = None
    supplier_code: Optional[str] = None
    extracted_fields: List[BarcodePreviewItem] = []
    candidates: List[MaterialCandidate] = []
    message: str = ""


class ReceiptScanRequest(BaseModel):
    barcode: str
    operator: str
    qty: Optional[float] = None

    # ── Batch / date code (optional, from barcode or manual entry) ──
    batch_no: Optional[str] = Field(None, description="批次号（选填）")
    date_code: Optional[str] = Field(None, description="生产日期/周期代码（选填）")

    # ── Human review overrides (used in second-pass or manual selection) ──
    manual_material_id: Optional[int] = Field(
        None, description="人工选择的物料 ID（替代自动匹配）"
    )
    is_new_material: Optional[bool] = Field(
        False, description="标记为全新物料（系统自动创建 MaterialMaster）"
    )
    new_material_code: Optional[str] = Field(
        None, description="新物料编码（is_new_material 时使用）"
    )
    new_material_name: Optional[str] = Field(
        None, description="新物料名称（is_new_material 时使用）"
    )

    # ── Printer configuration ──
    printer_ip: Optional[str] = Field(None, description="标签打印机 IP（指定时使用此地址）")
    printer_port: Optional[int] = Field(None, description="标签打印机端口")
    print_label: Optional[bool] = Field(
        False, description="是否打印标签（为 true 时使用系统配置的打印机地址）"
    )


class ReceiptScanResponse(BaseModel):
    status: str  # ok | duplicate | pending_review | error
    action: str  # first_in | restock | duplicate | pending_review | new_material

    # ── Auto-proceed result ──
    reel_id: Optional[int] = None
    reel_code: str = ""
    assigned_slot: Optional[int] = None
    quantity: float = 0

    duplicate_flag: bool = False
    warning: Optional[str] = None

    # ── Label printing ──
    label_printed: bool = Field(
        False, description="内部标签是否已打印"
    )

    # ── Pending review result ──
    candidates: List[MaterialCandidate] = Field(
        default_factory=list,
        description="匹配置信度低于阈值时的候选物料列表",
    )
    customer_material_code: str = Field(
        "", description="从客户标签识别的物料编码"
    )

    # ── Material info (when matched / newly created) ──
    material_id: Optional[int] = None
    material_code: str = ""
    material_name: str = ""
    confidence: float = 0.0

    message: str


class ReceiptAssignSlotRequest(BaseModel):
    receipt_detail_id: int
    shelf_slot_id: int


class ReprintLabelRequest(BaseModel):
    receipt_reel_id: int
    printer_ip: Optional[str] = Field(None, description="标签打印机 IP（不传则使用系统默认）")
    printer_port: Optional[int] = Field(None, description="标签打印机端口（不传则使用系统默认）")


class ReprintLabelResponse(BaseModel):
    status: str
    printed: bool
    message: str
    receipt_reel_id: int


class ReceiptDetailResponse(BaseModel):
    id: int
    receipt_no: str
    customer_id: int
    created_at: datetime
    operator: str
    status: str  # draft | confirmed | completed
    items: List[dict] = []


# ---------- Issue ----------
class ReelAssignment(BaseModel):
    reel_id: int
    reel_barcode: Optional[str] = None
    shelf_slot_id: Optional[int] = None
    slot_code: Optional[str] = None
    reel_qty: float
    original_quantity: float
    pick_quantity: float


class IssueDetailItem(BaseModel):
    id: Optional[int] = None
    material_id: int
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    material_unit: Optional[str] = None
    required_qty: float
    assigned_qty: float = 0
    picked_qty: float = 0
    reel_assignments: List[ReelAssignment] = []
    shortage: float = 0
    status: str = "pending"


class IssueCreateRequest(BaseModel):
    bom_id: int
    production_quantity: float
    customer_id: int
    required_date: Optional[str] = None


class IssueOrderListItem(BaseModel):
    id: int
    order_no: str
    bom_id: Optional[int] = None
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    production_quantity: float
    customer_id: int
    customer_name: Optional[str] = None
    status: str
    required_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    detail_count: int = 0


class IssueOrderDetail(BaseModel):
    id: int
    order_no: str
    bom_id: Optional[int] = None
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    production_quantity: float
    customer_id: int
    customer_name: Optional[str] = None
    status: str
    required_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    details: List[IssueDetailItem] = []


class IssueCalculateRequest(BaseModel):
    strategy: str = "config"


class ReelSelection(BaseModel):
    reel_id: int
    quantity: float
    last_in_time: datetime
    shelf_slot_id: Optional[int] = None


class MaterialCalcResult(BaseModel):
    material_id: int
    material_code: str
    material_name: str
    required_qty: float
    available_qty: float
    strategy: str
    reels_selected: List[ReelSelection]
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
    reel_id: int
    operator: str


class IssueConfirmPickResponse(BaseModel):
    status: str
    picked_qty: float
    remaining_qty: float
    all_picked: bool
    cleared_leds: List[int]
    message: str


# ---------- Inventory ----------
class InventoryUpdateRequest(BaseModel):
    """Update inventory pallet fields (partial update)."""
    quantity: Optional[float] = Field(None, ge=0, description="盘数量（>=0）")
    status: Optional[str] = Field(None, pattern=r"^(pending_shelving|on_shelf|in_use|tracking|exhausted)$")
    shelf_slot_id: Optional[int] = Field(None, description="储位 ID（null 表示解除绑定）")
    note: Optional[str] = Field(None, max_length=500, description="变更备注")

    model_config = {
        "json_schema_extra": {
            "example": {
                "quantity": 5.0,
                "status": "on_shelf",
                "shelf_slot_id": 12,
                "note": "盘点调整",
            }
        }
    }


class InventoryUpdateResponse(BaseModel):
    status: str = "ok"
    reel_id: int
    updated_fields: List[str]
    message: str


class InventoryResponse(BaseModel):
    pallets: List[dict]
    summary: dict


class TrackingReelResponse(BaseModel):
    reel_id: int
    material_code: str
    quantity: float
    last_out_time: Optional[datetime] = None
    status: str = "tracking"
    xr_matched: bool = False


# ---------- XR ----------
class XrUploadRequest(BaseModel):
    reel_id: str
    qty: float
    printer_ip: Optional[str] = None
    printer_port: Optional[int] = None


class XrUploadResponse(BaseModel):
    success: bool
    code: int
    message: str


class XrMatchRequest(BaseModel):
    xr_batch_id: int
    reel_id: int


class XrRestockRequest(BaseModel):
    shelf_slot_id: int


# ---------- BOM ----------
class BomAlternativeSchema(BaseModel):
    id: Optional[int] = None
    alternative_material_id: int
    alternative_material_code: Optional[str] = None
    alternative_material_name: Optional[str] = None
    priority: int = 1
    percentage: float = 100.0


class BomItemSchema(BaseModel):
    id: Optional[int] = None
    parent_id: Optional[int] = None
    material_id: int
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    material_unit: Optional[str] = None
    quantity: float
    position: int = 0
    remark: Optional[str] = None
    alternatives: List[BomAlternativeSchema] = []
    children: List["BomItemSchema"] = []


BomItemSchema.model_rebuild()


class BomCreateRequest(BaseModel):
    customer_id: int
    product_material_id: int
    version: str = "1.0"
    description: Optional[str] = None


class BomUpdateRequest(BaseModel):
    version: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None


class BomListItem(BaseModel):
    id: int
    customer_id: int
    customer_name: Optional[str] = None
    product_material_id: int
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    version: str
    status: str
    description: Optional[str] = None
    item_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BomDetailResponse(BaseModel):
    id: int
    customer_id: int
    customer_name: Optional[str] = None
    product_material_id: int
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    version: str
    status: str
    description: Optional[str] = None
    items: List[BomItemSchema] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BomUploadResponse(BaseModel):
    bom_id: int
    product_code: str
    version: str
    parsed: bool
    total_items: int
    unique_materials: int
    alternates_found: int
    auto_created_count: int = 0


class BomGenerateIssueRequest(BaseModel):
    customer_id: int
    required_date: Optional[str] = None


# ---------- Report ----------
class DailyReportSummary(BaseModel):
    total_materials: int
    total_in: float
    total_out: float
    total_balance: float
    total_reels_on_shelf: int
    total_reels_tracking: int


class DailyReportDetail(BaseModel):
    material_id: int
    material_code: str
    material_name: str
    opening_balance: float
    in_qty: float
    out_qty: float
    closing_balance: float
    reels_on_shelf: int
    reels_tracking: int


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
    a_sides: Optional[int] = 0
    b_sides: Optional[int] = 0
    total_slots: Optional[int] = 0
    controller_ip: Optional[str] = None
    controller_port: Optional[int] = 502
    a_side_count: Optional[int] = 0
    b_side_count: Optional[int] = 0
    location: Optional[str] = None
    active: Optional[int] = 1


class ShelfSlotCreate(BaseModel):
    side: str
    board_address: int
    slot_on_board: int
    global_index: int
    modbus_coil_base: int
    max_quantity: Optional[float] = Field(None, ge=0, description="储位最大容量（null=不限制）")


class ShelfSlotResponse(BaseModel):
    id: int
    shelf_id: int
    side: str
    board_address: int
    slot_on_board: int
    global_index: int
    modbus_tcp_id: int
    modbus_coil_base: int
    max_quantity: Optional[float] = None
    last_event_at: Optional[datetime] = None
    last_sensor_state: int = 0


class ShelfSlotEventResponse(BaseModel):
    id: int
    shelf_slot_id: int
    event_type: str  # occupied | released | error
    reel_id: Optional[int] = None
    source: str = "sensor"
    old_state: int = 0
    new_state: int = 0
    created_at: Optional[datetime] = None


class SlotSensorState(BaseModel):
    """Live sensor state for a single slot."""
    slot_id: int
    side: str
    board_address: int
    slot_on_board: int
    has_material: bool
    last_event_at: Optional[datetime] = None
    bound_reel_id: Optional[int] = None


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


# ---------- Direct Outbound ----------
class DirectOutRequest(BaseModel):
    quantity: float = Field(..., gt=0, description="出库数量")
    operator: str = Field(..., min_length=1)
    note: Optional[str] = Field(None, max_length=500)
    release_slot: bool = Field(True, description="数量归零时是否释放储位")


class DirectOutResponse(BaseModel):
    status: str  # ok | exhausted | error
    reel_id: int
    quantity_before: float
    quantity_after: float
    reel_status: str
    slot_released: bool = False
    message: str


# ---------- Barcode Definition ----------
class BarcodeDefinitionSegmentSchema(BaseModel):
    """条码定义段 — 单个段的字段映射。"""
    segment_index: int = Field(..., ge=0, description="段索引（从0开始）")
    segment_sample: Optional[str] = Field(None, description="该段的样例值")
    field_mapping: Optional[str] = Field("", description="映射字段名（如 material_code, batch_no，为空表示忽略该段）")
    field_label: Optional[str] = Field("", description="字段显示名称，空表示不映射")


class BarcodeDefinitionCreate(BaseModel):
    """创建条码定义请求。"""
    name: str = Field(..., min_length=1, max_length=100, description="条码定义名称")
    delimiter: str = Field(..., min_length=1, max_length=10, description="分隔符")
    sample_barcode: str = Field(..., min_length=1, description="样例条码")
    barcode_length: Optional[int] = Field(None, ge=1, description="条码字符长度（不传则自动取样例长度）")
    segments: List[BarcodeDefinitionSegmentSchema] = Field(..., min_length=1, description="段定义列表")


class BarcodeDefinitionUpdate(BaseModel):
    """更新条码定义请求。"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    delimiter: Optional[str] = Field(None, min_length=1, max_length=10)
    sample_barcode: Optional[str] = Field(None, min_length=1)
    barcode_length: Optional[int] = Field(None, ge=1, description="条码字符长度（不传则自动取样例长度）")
    is_active: Optional[int] = Field(None, ge=0, le=1)
    segments: Optional[List[BarcodeDefinitionSegmentSchema]] = Field(None, min_length=1)


class BarcodeDefinitionResponse(BaseModel):
    """条码定义响应。"""
    id: int
    name: str
    delimiter: str
    sample_barcode: str
    barcode_length: int = 0
    is_active: int = 1
    segments: List[BarcodeDefinitionSegmentSchema] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BarcodePreviewRequest(BaseModel):
    """条码预览请求 — 输入条码和分隔符预览拆分结果。"""
    sample_barcode: str = Field(..., min_length=1, description="样例条码")
    delimiter: str = Field(..., min_length=1, max_length=10, description="分隔符")


class BarcodePreviewSegment(BaseModel):
    """条码预览 — 单个段的拆分结果。"""
    segment_index: int
    value: str


class BarcodeDefPreviewResponse(BaseModel):
    """条码定义预览响应（分割预览）。"""
    segments: List[BarcodePreviewSegment] = []
    segment_count: int = 0


class BarcodeTestRequest(BaseModel):
    """条码测试请求 — 用条码定义解析实际条码。"""
    definition_id: int = Field(..., description="条码定义ID")
    barcode: str = Field(..., min_length=1, description="待解析的条码")


class BarcodeTestSegmentResult(BaseModel):
    """条码测试 — 单个段的解析结果。"""
    segment_index: int
    value: str
    field_mapping: Optional[str] = ""
    field_label: Optional[str] = ""


class BarcodeTestResponse(BaseModel):
    """条码测试响应。"""
    definition_id: int
    definition_name: str
    delimiter: str
    barcode: str
    matched: bool
    segments: List[BarcodeTestSegmentResult] = []
    message: str = ""


# ---------- General ----------
class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
