import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios'
import AsyncStorage from '@react-native-async-storage/async-storage'
import * as t from '../types/api'

const BASE_URL = 'http://localhost:8080/api'

const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const token = await AsyncStorage.getItem('token')
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response?.status === 401) {
      await AsyncStorage.removeItem('token')
    }
    return Promise.reject(err)
  }
)

// ──── Auth ────
export async function loginApi(data: t.LoginRequest): Promise<t.TokenResponse> {
  const res = await api.post('/auth/login', data)
  return res.data
}

export async function getMeApi(): Promise<t.UserResponse> {
  const res = await api.get('/auth/me')
  return res.data
}

// ──── Dashboard ────
export async function getDashboardSummaryApi(): Promise<t.DashboardSummary> {
  const res = await api.get('/dashboard/summary')
  return res.data
}

// ──── BOM ────
export async function listBOMsApi(params?: {
  customer_id?: number
  status?: string
}): Promise<t.BOMResponse[]> {
  const res = await api.get('/bom', { params })
  return res.data
}

// ──── Receipts (Inbound) ────
export async function createReceiptApi(data: t.ReceiptCreate): Promise<t.ReceiptDetailResponse> {
  const res = await api.post('/receipts', data)
  return res.data
}

export async function scanPreviewApi(
  receiptId: number,
  data: t.ReceiptScanRequest
): Promise<t.BarcodePreviewResponse> {
  const res = await api.post(`/receipts/${receiptId}/scan-preview`, data)
  return res.data
}

export async function scanInboundApi(
  receiptId: number,
  data: t.ReceiptScanRequest
): Promise<t.ReceiptScanResponse> {
  const res = await api.post(`/receipts/${receiptId}/scan`, data)
  return res.data
}

export async function manualEntryApi(
  receiptId: number,
  data: t.ManualEntryRequest
): Promise<t.ReceiptScanResponse> {
  const res = await api.post(`/receipts/${receiptId}/manual-entry`, data)
  return res.data
}

// ──── Shelving ────
export async function scanShelvingReelApi(barcode: string): Promise<t.ShelvingScanResponse> {
  const res = await api.post('/shelving/scan', { barcode })
  return res.data
}

export async function bindShelvingSlotApi(
  data: t.ShelvingBindRequest
): Promise<t.ShelvingBindResponse> {
  const res = await api.post('/shelving/bind', data)
  return res.data
}

// ──── Issues (Outbound) ────
export async function listIssuesApi(params?: {
  customer_id?: number
  status?: string
}): Promise<{ data: t.IssueOrderResponse[] }> {
  const res = await api.get('/issues', { params })
  return res.data
}

export async function getIssueDetailApi(orderId: number): Promise<t.IssueOrderResponse> {
  const res = await api.get(`/issues/${orderId}`)
  return res.data
}

export async function calculateIssueApi(
  orderId: number,
  strategy: string = 'tail_first'
): Promise<t.IssueCalculateResponse> {
  const res = await api.post(`/issues/${orderId}/calculate`, { strategy })
  return res.data
}

export async function assignIssueApi(orderId: number): Promise<t.IssueAssignResponse> {
  const res = await api.post(`/issues/${orderId}/assign`)
  return res.data
}

export async function confirmPickApi(
  orderId: number,
  data: t.IssueConfirmPickRequest
): Promise<t.IssueConfirmPickResponse> {
  const res = await api.post(`/issues/${orderId}/confirm-pick`, data)
  return res.data
}

// ──── Direct Outbound ────
export async function scanReelForDirectOutApi(
  barcode: string
): Promise<{ reel_id: number; material_code: string; material_name?: string; quantity: number; shelf_code?: string; status: string }> {
  const res = await api.post('/inventory/scan-reel', { barcode })
  return res.data
}

export async function directOutboundApi(
  reelId: number,
  data: t.DirectOutRequest
): Promise<t.DirectOutResponse> {
  const res = await api.post(`/inventory/reels/${reelId}/direct-out`, data)
  return res.data
}

// ──── Inventory ────
export async function getInventoryApi(params?: {
  customer_id?: number
  material_id?: number
}): Promise<t.InventoryResponse> {
  const res = await api.get('/inventory', { params })
  return res.data
}

export async function getTrackingInventoryApi(): Promise<{ pallets: t.TrackingReelResponse[] }> {
  const res = await api.get('/inventory/tracking')
  return res.data
}

// ──── Materials ────
export async function getMaterialsApi(params?: {
  customer_id?: number
  keyword?: string
  category_id?: number
}): Promise<t.MaterialResponse[]> {
  const res = await api.get('/materials', { params })
  return res.data
}

// ──── Shelves ────
export async function getShelvesApi(): Promise<t.ShelfResponse[]> {
  const res = await api.get('/shelves')
  return res.data
}

export async function getShelfSlotsApi(shelfId: number): Promise<t.ShelfSlotResponse[]> {
  const res = await api.get(`/shelves/${shelfId}/slots`)
  return res.data
}

export async function getSlotStatesApi(shelfId: number): Promise<{ shelf_id: number; polling_active: boolean; slots: t.SlotSensorState[] }> {
  const res = await api.get(`/shelves/${shelfId}/slots/state`)
  return res.data
}

export default api
