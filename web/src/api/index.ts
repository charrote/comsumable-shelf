import api from './client'

export const apiClient = api

// Auth
export const loginApi = (data: { username: string; password: string }) =>
  apiClient.post('/auth/login', data)
export const getUserApi = () => apiClient.get('/auth/me')

// Material
export const getMaterialsApi = (params: any) =>
  apiClient.get('/materials', { params })
export const getMaterialApi = (id: number) =>
  apiClient.get(`/materials/${id}`)
export const createMaterialApi = (data: any) =>
  apiClient.post('/materials', data)
export const updateMaterialApi = (id: number, data: any) =>
  apiClient.put(`/materials/${id}`, data)
export const deleteMaterialApi = (id: number) =>
  apiClient.delete(`/materials/${id}`)

// Shelf
export const getShelvesApi = (params?: any) =>
  apiClient.get('/shelves', { params })
export const createShelfApi = (data: any) =>
  apiClient.post('/shelves', data)
export const updateShelfApi = (id: number, data: any) =>
  apiClient.put(`/shelves/${id}`, data)
export const deleteShelfApi = (id: number) =>
  apiClient.delete(`/shelves/${id}`)
export const getShelfSlotsApi = (shelfId: number) =>
  apiClient.get(`/shelves/${shelfId}/slots`)
export const createShelfSlotsApi = (shelfId: number, slots: any[]) =>
  apiClient.post(`/shelves/${shelfId}/slots`, { slots })
export const getSlotLedStatusApi = (shelfId: number, side: 'A' | 'B') =>
  apiClient.get(`/shelves/${shelfId}/led/${side}`)

// Inventory
export const getInventoryApi = (params: any) =>
  apiClient.get('/inventory', { params })
export const getTrackingApi = () =>
  apiClient.get('/inventory/tracking')

// Receipt
export const createReceiptApi = (data: { type: string; operator: string }) =>
  apiClient.post('/receipts', data)
export const scanReceiptApi = (receiptId: number, data: { barcode: string; operator: string }) =>
  apiClient.post(`/receipts/${receiptId}/scan`, data)
export const getReceiptListApi = (params: any) =>
  apiClient.get('/receipts', { params })
export const getReceiptDetailApi = (id: number) =>
  apiClient.get(`/receipts/${id}`)
export const assignSlotApi = (receiptId: number, data: { detail_id: number; shelf_slot_id: number }) =>
  apiClient.post(`/receipts/${receiptId}/assign-slot`, data)
export const confirmReceiptApi = (id: number) =>
  apiClient.put(`/receipts/${id}/confirm`)

// Issue
export const getIssueListApi = (params: any) =>
  apiClient.get('/issues', { params })
export const createIssueApi = (data: any) =>
  apiClient.post('/issues', data)
export const calculateIssueApi = (orderId: number, data: { strategy: string }) =>
  apiClient.post(`/issues/${orderId}/calculate`, data)
export const assignLedApi = (orderId: number) =>
  apiClient.post(`/issues/${orderId}/assign`)
export const confirmPickApi = (orderId: number, data: { barcode: string; pallet_id: number }) =>
  apiClient.post(`/issues/${orderId}/confirm-pick`, data)

// XR
export const getXRListApi = (params: any) =>
  apiClient.get('/xr', { params })
export const matchXRApi = (batchId: number, data: { pallet_id: number }) =>
  apiClient.post(`/xr/${batchId}/match`, data)
export const confirmXRRestockApi = (batchId: number, data: { shelf_slot_id: number }) =>
  apiClient.post(`/xr/${batchId}/confirm-restock`, data)

// BOM
export const uploadBomApi = (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  return apiClient.post('/bom/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
export const getBomApi = (bomId: number) =>
  apiClient.get(`/bom/${bomId}`)
export const generateIssueFromBomApi = (bomId: number, data: any) =>
  apiClient.post(`/bom/${bomId}/generate-issue`, data)

// Report
export const getDailyReportApi = (date: string, customerId?: number) =>
  apiClient.get('/reports/daily', { params: { date, customer_id: customerId } })
export const getCustomerSummaryApi = (params: any) =>
  apiClient.get('/reports/customer-summary', { params })

// Settings
export const getSettingsApi = () =>
  apiClient.get('/settings')
export const updateSettingApi = (key: string, value: string, description?: string) =>
  apiClient.put(`/settings/${key}`, { key, value, description })
export const getPollingStatusApi = (shelfId: number) =>
  apiClient.get(`/shelves/${shelfId}/polling`)
export const startPollingApi = (shelfId: number) =>
  apiClient.post(`/shelves/${shelfId}/polling/start`)
export const stopPollingApi = (shelfId: number) =>
  apiClient.post(`/shelves/${shelfId}/polling/stop`)
export const clearLedCommandApi = (shelfId: number, slotId: number) =>
  apiClient.post(`/shelves/${shelfId}/led/clear`, { slot_id: slotId })

// Users
export const getUsersApi = (params: any) =>
  apiClient.get('/users', { params })
export const createUserApi = (data: any) =>
  apiClient.post('/users', data)
export const updateUserApi = (id: number, data: any) =>
  apiClient.put(`/users/${id}`, data)
export const deleteUserApi = (id: number) =>
  apiClient.delete(`/users/${id}`)
