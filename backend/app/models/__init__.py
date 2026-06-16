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
    inventory = relationship("InventoryPallet", back_populates="customer")
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


Shelf.slots = relationship("ShelfSlot", back_populates="shelf")


class InventoryPallet(Base):
    __tablename__ = "inventory_pallets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(Integer, ForeignKey("material_master.id"), nullable=False)
    shelf_slot_id = Column(Integer, ForeignKey("shelf_slots.id"))
    quantity = Column(Float, nullable=False)
    original_quantity = Column(Float, nullable=False)
    pallet_barcode = Column(String)
    customer_code = Column(String)
    first_in_time = Column(DateTime, nullable=False)
    last_in_time = Column(DateTime, nullable=False)
    last_out_time = Column(DateTime)
    last_out_order_id = Column(Integer)
    inbound_type = Column(String, default="new")  # new | restock
    inbound_receipt_id = Column(Integer)
    inbound_xr_count = Column(Float)
    status = Column(String, default="on_shelf")  # on_shelf | in_use | tracking | exhausted
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
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
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String)
    type = Column(String, default="normal")  # normal | restock
    status = Column(String, default="draft")  # draft | confirmed | completed


class ReceiptPallet(Base):
    __tablename__ = "receipt_pallets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(Integer, ForeignKey("receipt.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("material_master.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    barcode = Column(String)
    scanned_at = Column(DateTime, default=datetime.utcnow)
    operator = Column(String)
    shelf_slot_id = Column(Integer, ForeignKey("shelf_slots.id"))
    inventory_pallet_id = Column(Integer, ForeignKey("inventory_pallets.id"))
    is_restock = Column(Integer, default=0)
    restock_match_key = Column(String)


class IssueOrder(Base):
    __tablename__ = "issue_order"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_no = Column(String, unique=True, nullable=False, index=True)
    bom_header_id = Column(Integer, ForeignKey("bom_headers.id"))
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    required_date = Column(DateTime)
    status = Column(String, default="pending")  # pending | calculating | assigned | picking | completed
    created_at = Column(DateTime, default=datetime.utcnow)
    assigned_at = Column(DateTime)
    completed_at = Column(DateTime)


class IssueDetail(Base):
    __tablename__ = "issue_detail"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_order_id = Column(Integer, ForeignKey("issue_order.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("material_master.id"), nullable=False)
    required_qty = Column(Float, nullable=False)
    picked_qty = Column(Float, default=0)
    pallet_ids = Column(String)  # JSON
    pick_strategy = Column(String, default="tail_first")
    status = Column(String, default="pending")  # pending | picking | completed


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, nullable=False)
    material_id = Column(Integer, ForeignKey("material_master.id"), nullable=False)
    type = Column(String, nullable=False)  # in | out | restock | reverse
    quantity = Column(Float, nullable=False)
    balance_after = Column(Float, nullable=False)
    inventory_pallet_id = Column(Integer, ForeignKey("inventory_pallets.id"))
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
    matched_pallet_id = Column(Integer, ForeignKey("inventory_pallets.id"))
    status = Column(String, default="pending_match")  # pending_match | matched | failed
    match_key = Column(String)


class BomHeader(Base):
    __tablename__ = "bom_headers"

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
    __tablename__ = "bom_details"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bom_header_id = Column(Integer, ForeignKey("bom_headers.id"), nullable=False)
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
