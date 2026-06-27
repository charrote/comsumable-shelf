"""
WebSocket 端点。

提供实时推送通道：
  - 储位变化推送（callback → WebSocket）
  - 控灯状态推送（success/fail）
  - 心跳检测（ping/pong）

用法:
    客户端连接: ws://host:port/ws
    心跳: 发送 "ping" → 接收 "pong"
"""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.websocket_service import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket 主端点

    连接生命周期:
        1. 接受连接
        2. 等待消息（ping 或其他）
        3. 断开时清理
    """
    await ws_manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
            # 可扩展其他消息类型
            # elif data == "subscribe":
            #     # 处理订阅
            #     pass
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception as e:
        logger.warning("WebSocket error: %s", e)
        ws_manager.disconnect(ws)
