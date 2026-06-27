"""
WebSocket 连接管理器。

管理所有 WebSocket 连接，提供广播能力。
支持储位变化推送和控灯状态推送。

用法::

    from app.services.websocket_service import ws_manager

    # 广播储位变化
    await ws_manager.broadcast("cell_changed", {
        "cell_id": "A0010001",
        "status": 1,
    })

    # 广播告警
    await ws_manager.broadcast("alert", {
        "shelf_id": 1,
        "message": "控灯 API 不可达",
    })
"""

import json
import logging
from typing import Set, Dict, Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """WebSocket 连接管理器

    支持连接/断开管理，以及向所有连接广播消息。
    断线连接自动清理。
    """

    def __init__(self):
        self._connections: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        """接受新的 WebSocket 连接"""
        await ws.accept()
        self._connections.add(ws)
        logger.info("WebSocket connected: %d total", len(self._connections))

    def disconnect(self, ws: WebSocket):
        """断开 WebSocket 连接"""
        self._connections.discard(ws)
        logger.info("WebSocket disconnected: %d remaining", len(self._connections))

    async def broadcast(self, event_type: str, data: dict):
        """向所有连接广播消息

        Args:
            event_type: 事件类型（如 "cell_changed", "alert"）
            data: 事件数据 dict
        """
        message = json.dumps(
            {"type": event_type, "data": data},
            ensure_ascii=False,
            default=str,
        )
        dead: Set[WebSocket] = set()
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)

        # 清理断线连接
        if dead:
            self._connections -= dead
            logger.info("Cleaned %d dead connections", len(dead))

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# 全局单例
ws_manager = WebSocketManager()
