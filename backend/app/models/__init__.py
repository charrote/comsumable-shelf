"""SQLAlchemy models."""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, Boolean, ForeignKey,
    UniqueConstraint, Index, Enum as SAEnum
)
from sqlalchemy.orm import relationship, declarative_base
import enum

Base = declarative_base()


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    code = Column(String, unique=True, nullable=False, index=True)
    contact_name = Column(String)
    contact_phone = Column(String)
    address = Column(String)
    active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    categories = relationship("MaterialCategory", back_populates="customer")
    materials = relationship("MaterialMaster", back_populates="customer")
    inventory = relationship("InventoryReel", back_populates="customer")
    boms = relationship("Bom", back_populates="customer")
    bom_headers = relationship("BomHeader", back_populates="customer")


class MaterialCategory(Base):
    __tablename__ = "material_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    name = Column(String, nullable=False)
    code = Column(String, nullable=False)
    parent_id = Column(Integer, ForeignKey("material_categories.id"))

    customer = relationship("Customer", back_populates="categories")
    parent = relationship("MaterialCategory", remote_side=[id], backref="children")

    __table_args__ = (
        UniqueConstraint("customer_id", "code", name="uq_cat_customer_code"),
        Index("idx_cat_customer_code", "customer_id", "code"),
    )


class MaterialMaster(Base):
    __tablename__ = "material_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("material_categories.id"))
    code = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    spec = Column(String)
    unit = Column(String, default="盘")
    qty_per_pallet = Column(Float)
    barcode_pattern = Column(String)
    active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="materials")

    __table_args__ = (
        UniqueConstraint("customer_id", "code", name="uq_mat_customer_code"),
        Index("idx_mat_customer_code", "customer_id", "code"),
    )


class MaterialAlternative(Base):
    __tablename__ = "material_alternative"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_code = Column(String, nullable=False)
    alternate_code = Column(String, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    active = Column(Integer, default=1)

    __table_args__ = (
        Index("idx_alt_original", "customer_id", "original_code"),
        Index("idx_alt_alternate", "customer_id", "alternate_code"),
    )


class Shelf(Base):
    __tablename__ = "shelves"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, unique=True, nullable=False, index=True)
    name = Column(String)
    a_sides = Column(Integer, default=0)
    b_sides = Column(Integer, default=0)
    total_slots = Column(Integer, default=0)
    controller_ip = Column(String)
    controller_port = Column(Integer, default=502)
    a_side_count = Column(Integer, default=0)
    b_side_count = Column(Integer, default=0)
    location = Column(String)
    active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class ShelfSlot(Base):
    __tablename__ = "shelf_slots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    shelf_id = Column(Integer, ForeignKey("shelves.id"), nullable=False)
    side = Column(String, nullable=False)  # 'A' or 'B'
    board_address = Column(Integer, nullable=False)
    slot_on_board = Column(Integer, nullable=False)
    global_index = Column(Integer, nullable=False)
    modbus_tcp_id = Column(Integer, nullable=False)
    modbus_coil_base = Column(Integer, nullable=False)
    max_quantity = Column(Float, nullable=True, comment="储位最大容量（null 表示不限制）")
    last_event_at = Column(DateTime, nullable=True, comment="最近一次传感器事件时间")
    last_sensor_state = Column(Integer, default=0, comment="最近一次传感器读取值（0=空, 1=有料）")

    shelf = relationship("Shelf", back_populates="slots")

    __table_args__ = (
        UniqueConstraint("shelf_id", "side", "slot_on_board", name="uq_slot_pos"),
        Index("idx_slot_pos", "shelf_id", "side", "slot_on_board"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.side == "A":
            self.modbus_tcp_id = self.board_address
        else:
            self.modbus_tcp_id = 63 + self.board_address


class ShelfSlotEvent(Base):
    """Records sensor state changes on shelf slots."""
    __tablename__ = "shelf_slot_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    shelf_slot_id = Column(Integer, ForeignKey("shelf_slots.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)  # occupied | released | error
    reel_id = Column(Integer, ForeignKey("inventory_reels.id"))
    source = Column(String, default="sensor")  # sensor | manual | api
    old_state = Column(Integer, default=0)
    new_state = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_slot_event_type", "shelf_slot_id", "event_type", "created_at"),
    )


Shelf.slots = relationship("ShelfSlot", back_populates="shelf")


class InventoryReel(Base):
    __tablename__ = "inventory_reels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reel_code = Column(String, unique=True, nullable=True, comment="格式化卷盘编号，如 REEL-20260623-0001")
    material_id = Column(Integer, ForeignKey("material_master.id"), nullable=False)
    shelf_slot_id = Column(Integer, ForeignKey("shelf_slots.id"))
    quantity = Column(Float, nullable=False)
    original_quantity = Column(Float, nullable=False)
    reel_barcode = Column(String)
    customer_code = Column(String)
    customer_material_code = Column(String, comment="客户标签上的物料编码（可能与内部料号不同）")
    customer_barcode = Column(String, comment="客户标签原始条码全文")
    first_in_time = Column(DateTime, nullable=False)
    last_in_time = Column(DateTime, nullable=False)
    last_out_time = Column(DateTime)
    last_out_order_id = Column(Integer)
    inbound_type = Column(String, default="new")  # new | restock
    inbound_receipt_id = Column(Integer)
    inbound_xr_count = Column(Float)
    status = Column(String, default="pending_shelving")  # pending_shelving | on_shelf | in_use | tracking | exhausted
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    batch_no = Column(String, comment="批次号（选填）")
    date_code = Column(String, comment="生产日期/周期代码（选填）")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="inventory")

    __table_args__ = (
        Index("idx_inv_material", "customer_id", "material_id", "status"),
        Index("idx_inv_fifo", "customer_id", "material_id", "last_in_time", "quantity",
              sqlite_where=status == "on_shelf"),
        Index("idx_inv_tracking", "customer_id", "status", "last_out_time",
              sqlite_where=status == "tracking"),
    )


class Receipt(Base):
    __tablename__ = "receipt"

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_no = Column(String, unique=True, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    purchase_order_no = Column(String, comment="采购单号")
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String)
    type = Column(String, default="normal")  # normal | restock
    status = Column(String, default="draft")  # draft | confirmed | completed


class ReceiptReel(Base):
    __tablename__ = "receipt_reels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(Integer, ForeignKey("receipt.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("material_master.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    barcode = Column(String)
    customer_material_code = Column(String, comment="客户标签上的物料编码")
    ocr_confidence = Column(Float, default=0.0, comment="OCR/条码识别置信度 0.0 ~ 1.0")
    manual_intervention = Column(Integer, default=0, comment="是否经过人工介入 0=自动 1=人工选择物料 2=确认为新料")
    scanned_at = Column(DateTime, default=datetime.utcnow)
    operator = Column(String)
    shelf_slot_id = Column(Integer, ForeignKey("shelf_slots.id"))
    reel_id = Column(Integer, ForeignKey("inventory_reels.id"))
    internal_label_printed = Column(Integer, default=0, comment="内部标签是否已打印 0=未打印 1=已打印")
    label_printed_at = Column(DateTime, comment="内部标签打印时间")
    batch_no = Column(String, comment="批次号（选填）")
    date_code = Column(String, comment="生产日期/周期代码（选填）")
    is_restock = Column(Integer, default=0)
    restock_match_key = Column(String)


class IssueOrder(Base):
    __tablename__ = "issue_order"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_no = Column(String, unique=True, nullable=False, index=True)
    bom_id = Column(Integer, ForeignKey("boms.id"))
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    production_quantity = Column(Float, nullable=False, default=1)
    required_date = Column(DateTime)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    assigned_at = Column(DateTime)
    completed_at = Column(DateTime)

    bom = relationship("Bom", foreign_keys=[bom_id])


class IssueDetail(Base):
    __tablename__ = "issue_detail"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_order_id = Column(Integer, ForeignKey("issue_order.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("material_master.id"), nullable=False)
    required_qty = Column(Float, nullable=False)
    assigned_qty = Column(Float, default=0)
    picked_qty = Column(Float, default=0)
    reel_assignments = Column(Text)
    status = Column(String, default="pending")

    material = relationship("MaterialMaster", foreign_keys=[material_id])


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, nullable=False)
    material_id = Column(Integer, ForeignKey("material_master.id"), nullable=False)
    type = Column(String, nullable=False)  # in | out | restock | reverse
    quantity = Column(Float, nullable=False)
    balance_after = Column(Float, nullable=False)
    reel_id = Column(Integer, ForeignKey("inventory_reels.id"))
    source_type = Column(String)  # receipt | issue | xr_transfer
    source_id = Column(Integer)
    operator = Column(String)
    note = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_txn_customer_material", "customer_id", "material_id", "created_at"),
    )


class LedCommand(Base):
    __tablename__ = "led_commands"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_order_id = Column(Integer, ForeignKey("issue_order.id"))
    material_id = Column(Integer, nullable=False)
    shelf_id = Column(Integer, ForeignKey("shelves.id"), nullable=False)
    slot_id = Column(Integer, ForeignKey("shelf_slots.id"), nullable=False)
    color = Column(String, default="green")  # green | red | blue
    duration = Column(Integer, default=5)
    status = Column(String, default="queued")  # queued | sent | cleared | failed
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime)
    cleared_at = Column(DateTime)

    __table_args__ = (
        Index("idx_led_status", "status", "created_at"),
    )


class XrBatch(Base):
    __tablename__ = "xr_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String)
    material_code = Column(String, nullable=False)
    counted_qty = Column(Float, nullable=False)
    scanned_at = Column(DateTime, default=datetime.utcnow)
    operator = Column(String)
    matched_reel_id = Column(Integer, ForeignKey("inventory_reels.id"))
    status = Column(String, default="pending_match")  # pending_match | matched | failed
    match_key = Column(String)


class Bom(Base):
    __tablename__ = "boms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    product_material_id = Column(Integer, ForeignKey("material_master.id"), nullable=False)
    version = Column(String, nullable=False, default="1.0")
    status = Column(String, nullable=False, default="draft")
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="boms")
    product_material = relationship("MaterialMaster", foreign_keys=[product_material_id])
    items = relationship("BomItem", back_populates="bom", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("customer_id", "product_material_id", "version", name="uq_bom_product_version"),
        Index("idx_bom_product", "customer_id", "product_material_id"),
    )


class BomItem(Base):
    __tablename__ = "bom_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bom_id = Column(Integer, ForeignKey("boms.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("bom_items.id"))
    material_id = Column(Integer, ForeignKey("material_master.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    position = Column(Integer, default=0)
    remark = Column(String)

    bom = relationship("Bom", back_populates="items")
    parent = relationship("BomItem", remote_side=[id], backref="children")
    material = relationship("MaterialMaster", foreign_keys=[material_id])
    alternatives = relationship("BomAlternative", back_populates="bom_item", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_bom_item_bom", "bom_id"),
        Index("idx_bom_item_parent", "parent_id"),
    )


class BomAlternative(Base):
    __tablename__ = "bom_alternatives"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bom_item_id = Column(Integer, ForeignKey("bom_items.id"), nullable=False)
    alternative_material_id = Column(Integer, ForeignKey("material_master.id"), nullable=False)
    priority = Column(Integer, default=1)
    percentage = Column(Float, default=100.0)

    bom_item = relationship("BomItem", back_populates="alternatives")
    alternative_material = relationship("MaterialMaster", foreign_keys=[alternative_material_id])

    __table_args__ = (
        Index("idx_bom_alt_item", "bom_item_id"),
    )


class BomHeader(Base):
    __tablename__ = "bom_headers_legacy"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    bom_name = Column(String, nullable=False)
    product_code = Column(String)
    file_path = Column(String)
    parsed = Column(Integer, default=0)
    parsed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="bom_headers")


class BomDetail(Base):
    __tablename__ = "bom_details_legacy"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bom_header_id = Column(Integer, ForeignKey("bom_headers_legacy.id"), nullable=False)
    material_code = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String, default="盘")
    alternate_code = Column(String)
    priority = Column(Integer, default=0)
    parsed = Column(Integer, default=1)

    __table_args__ = (
        Index("idx_bom_mat", "bom_header_id", "material_code"),
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    description = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CustomerMaterialMapping(Base):
    """Maps a customer's material code to an internal material master record."""
    __tablename__ = "customer_material_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    customer_material_code = Column(String, nullable=False, comment="客户料号")
    internal_material_id = Column(Integer, ForeignKey("material_master.id"), nullable=False)
    active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("customer_id", "customer_material_code", name="uq_cust_mat_code"),
        Index("idx_cust_mat_map", "customer_id", "customer_material_code"),
    )


class BarcodeDefinition(Base):
    """条码定义 — 固定格式条码的分段解析规则。"""
    __tablename__ = "barcode_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, comment="条码定义名称")
    delimiter = Column(String, nullable=False, comment="分隔符")
    sample_barcode = Column(String, nullable=False, comment="样例条码")
    barcode_length = Column(Integer, nullable=False, comment="条码字符长度（匹配用）")
    is_active = Column(Integer, default=1, comment="是否启用")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    segments = relationship(
        "BarcodeDefinitionSegment",
        back_populates="definition",
        cascade="all, delete-orphan",
        order_by="BarcodeDefinitionSegment.segment_index",
    )


class BarcodeDefinitionSegment(Base):
    """条码定义段 — 每一段对应的字段映射。"""
    __tablename__ = "barcode_definition_segments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    definition_id = Column(Integer, ForeignKey("barcode_definitions.id"), nullable=False)
    segment_index = Column(Integer, nullable=False, comment="段索引（从0开始）")
    segment_sample = Column(String, comment="该段的样例值")
    field_mapping = Column(String, nullable=True, comment="映射字段名（为空表示忽略该段）")
    field_label = Column(String, nullable=True, comment="字段显示名称")

    definition = relationship("BarcodeDefinition", back_populates="segments")

    __table_args__ = (
        UniqueConstraint("definition_id", "segment_index", name="uq_bd_segment_index"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # admin | supervisor | operator | readonly
    customer_id = Column(Integer, ForeignKey("customers.id"))
    customer_name = Column(String)
    active = Column(Integer, default=1)
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
