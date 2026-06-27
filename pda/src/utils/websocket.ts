/**
 * 智能料架 WebSocket 连接管理。
 *
 * 连接后端 WS 端点接收实时储位变化推送：
 *   - reel_bound: 料盘自动绑定成功（智能料架回调产生）
 *   - cell_changed: 储位传感器状态变化
 *
 * 用法:
 *   const ws = useRef<WebSocketHelper | null>(null)
 *   ws.current = new WebSocketHelper(baseUrl, {
 *     onReelBound: (data) => { ... },
 *     onCellChanged: (data) => { ... },
 *   })
 *   ws.current.connect()
 *   // 清理
 *   ws.current?.disconnect()
 */

import { Platform } from 'react-native'

export interface ReelBoundEvent {
  reel_id: number
  cell_id: string
  shelf_code: string
  slot_code: string
  material_code: string
  material_name: string
  timestamp: string
}

export interface CellChangedEvent {
  cell_id: string
  status: number
  timestamp: string
}

export type WsEventType = 'reel_bound' | 'cell_changed'

export interface WsMessage {
  type: WsEventType
  data: ReelBoundEvent | CellChangedEvent
}

export interface WsCallbacks {
  onReelBound?: (data: ReelBoundEvent) => void
  onCellChanged?: (data: CellChangedEvent) => void
  onError?: (err: Event) => void
  onConnected?: () => void
  onDisconnected?: () => void
}

const RECONNECT_DELAY_MS = 3000
const MAX_RECONNECT_ATTEMPTS = 5

/**
 * 从 HTTP API 地址推导 WebSocket 地址
 * 例: http://10.0.2.2:8080/api → ws://10.0.2.2:8080/ws
 */
export function deriveWsUrl(apiBaseUrl: string): string {
  const base = apiBaseUrl.replace(/\/api$/, '').replace(/\/$/, '')
  const protocol = base.startsWith('https') ? 'wss' : 'ws'
  const host = base.replace(/^https?:\/\//, '')
  return `${protocol}://${host}/ws`
}

export class WebSocketHelper {
  private ws: WebSocket | null = null
  private apiBaseUrl: string
  private callbacks: WsCallbacks
  private reconnectAttempts = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private shouldReconnect = false
  private pingTimer: ReturnType<typeof setInterval> | null = null

  constructor(apiBaseUrl: string, callbacks: WsCallbacks) {
    this.apiBaseUrl = apiBaseUrl
    this.callbacks = callbacks
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  connect(): void {
    if (this.connected) return
    this.shouldReconnect = true
    this._doConnect()
  }

  disconnect(): void {
    this.shouldReconnect = false
    this._clearTimers()
    if (this.ws) {
      this.ws.onopen = null
      this.ws.onmessage = null
      this.ws.onerror = null
      this.ws.onclose = null
      this.ws.close()
      this.ws = null
    }
    this.callbacks.onDisconnected?.()
  }

  private _doConnect(): void {
    if (!this.shouldReconnect) return

    const url = deriveWsUrl(this.apiBaseUrl)
    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      this.reconnectAttempts = 0
      this.callbacks.onConnected?.()
      // 心跳 ping 每 30s
      this._clearPing()
      this.pingTimer = setInterval(() => {
        this._sendPing()
      }, 30000)
    }

    this.ws.onmessage = (event: WebSocketMessageEvent) => {
      try {
        const msg: WsMessage = JSON.parse(event.data)
        this._handleMessage(msg)
      } catch {
        // 非 JSON 消息忽略（如 pong 响应）
      }
    }

    this.ws.onerror = (err: Event) => {
      this.callbacks.onError?.(err)
    }

    this.ws.onclose = () => {
      this._clearPing()
      this.callbacks.onDisconnected?.()
      if (this.shouldReconnect && this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        this.reconnectAttempts++
        this.reconnectTimer = setTimeout(() => {
          this._doConnect()
        }, RECONNECT_DELAY_MS * this.reconnectAttempts)
      }
    }
  }

  private _handleMessage(msg: WsMessage): void {
    switch (msg.type) {
      case 'reel_bound':
        this.callbacks.onReelBound?.(msg.data as ReelBoundEvent)
        break
      case 'cell_changed':
        this.callbacks.onCellChanged?.(msg.data as CellChangedEvent)
        break
    }
  }

  private _sendPing(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send('ping')
    }
  }

  private _clearTimers(): void {
    this._clearPing()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  private _clearPing(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer)
      this.pingTimer = null
    }
  }
}
