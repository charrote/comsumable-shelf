"""Tests for rack callback API — mock DB to verify callback processing logic."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient

from app.main import app
from app.models import ShelfSlot, InventoryReel, ShelfSlotEvent


@pytest.fixture
def mock_db():
    """Create a mock database session for callback testing."""
    db = AsyncMock()
    return db


@pytest.fixture
def callback_payload():
    return {
        "data": [
            {"cellId": "A0010001", "status": 1, "timestamp": "2026-06-26T10:00:00"},
            {"cellId": "A0010002", "status": 0, "timestamp": "2026-06-26T10:00:05"},
        ],
        "code": 0,
        "message": "OK",
        "sessionId": "test-session-001",
    }


@pytest.mark.asyncio
async def test_callback_unknown_cell_id():
    """测试未知 cell_id 的处理 — 忽略并记录日志"""
    payload = {
        "data": [
            {"cellId": "UNKNOWN001", "status": 1, "timestamp": "2026-06-26T10:00:00"},
        ],
        "code": 0,
        "message": "OK",
        "sessionId": "test-001",
    }

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/rack/callback/cell-changed", json=payload)

    assert response.status_code == 200
    assert response.json()["code"] == 0


@pytest.mark.asyncio
async def test_callback_empty_data():
    """测试空数据回调"""
    payload = {
        "data": [],
        "code": 0,
        "message": "OK",
        "sessionId": "test-002",
    }

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/rack/callback/cell-changed", json=payload)

    assert response.status_code == 200
    assert response.json()["code"] == 0


def test_cell_change_item_model():
    """测试回调数据模型验证"""
    from app.api.rack_callback import CellChangeItem, CellChangeCallbackRequest

    item = CellChangeItem(cellId="A0010001", status=1, timestamp="2026-06-26T10:00:00")
    assert item.cellId == "A0010001"
    assert item.status == 1

    request = CellChangeCallbackRequest(
        data=[item],
        code=0,
        message="OK",
        sessionId="test",
    )
    assert len(request.data) == 1
    assert request.code == 0


@pytest.mark.asyncio
async def test_find_unbound_reel_logic():
    """测试 _find_unbound_reel 的逻辑"""
    from app.api.rack_callback import _find_unbound_reel

    db = AsyncMock()
    db.execute = AsyncMock()

    # 模拟找到待上架料盘
    mock_reel = MagicMock(spec=InventoryReel)
    mock_reel.id = 1
    mock_reel.status = "pending_shelving"
    mock_reel.shelf_slot_id = None

    result_proxy = MagicMock()
    result_proxy.scalar_one_or_none = MagicMock(return_value=mock_reel)
    db.execute.return_value = result_proxy

    reel = await _find_unbound_reel(db)
    assert reel is not None
    assert reel.id == 1


@pytest.mark.asyncio
async def test_find_unbound_reel_none():
    """测试无待上架料盘时的处理"""
    from app.api.rack_callback import _find_unbound_reel

    db = AsyncMock()
    result_proxy = MagicMock()
    result_proxy.scalar_one_or_none = MagicMock(return_value=None)
    db.execute.return_value = result_proxy

    reel = await _find_unbound_reel(db)
    assert reel is None
