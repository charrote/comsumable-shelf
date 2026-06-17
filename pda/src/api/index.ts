import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios'
import * as t from '../types/api'

const BASE_URL = 'http://localhost:8080/api'

const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('token')
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
    }
    return Promise.reject(err)
  }
)

// ---- Auth ----
export async function loginApi(data: t.LoginRequest): Promise<t.TokenResponse> {
  const res = await api.post('/auth/login', data)
  return res.data
}

export async function getMeApi(): Promise<t.UserResponse> {
  const res = await api.get('/auth/me')
  return res.data
}

// ---- Receipts (Inbound) ----
export async function createReceiptApi(data: t.ReceiptCreate): Promise<t.ReceiptDetailResponse> {
  const res = await api.post('/receipts', data)
  return res.data
}

export async function scanInboundApi(
  receiptId: number,
  data: t.ReceiptScanRequest
): Promise<t.ReceiptScanResponse> {
  const res = await api.post(`/receipts/${receiptId}/scan`, data)
  return res.data
}

// ---- Issues (Outbound) ----
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

// ---- Inventory ----
export async function getInventoryApi(params?: {
  customer_id?: number
  material_id?: number
}): Promise<t.InventoryResponse> {
  const res = await api.get('/inventory', { params })
  return res.data
}

export async function getTrackingInventoryApi(): Promise<{ pallets: t.TrackingPalletResponse[] }> {
  const res = await api.get('/inventory/tracking')
  return res.data
}

// ---- Materials ----
export async function getMaterialsApi(params?: {
  customer_id?: number
  keyword?: string
  category_id?: number
}): Promise<t.MaterialResponse[]> {
  const res = await api.get('/materials', { params })
  return res.data
}

// ---- Shelves ----
export async function getShelvesApi(): Promise<t.ShelfResponse[]> {
  const res = await api.get('/shelves')
  return res.data
}

export async function getShelfSlotsApi(shelfId: number): Promise<t.ShelfSlotResponse[]> {
  const res = await api.get(`/shelves/${shelfId}/slots`)
  return res.data
}

export default api
