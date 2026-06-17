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
export const getMappingsApi = (params?: { customer_id?: number }) =>
  apiClient.get('/materials/mappings', { params })
export const createMappingApi = (data: {
  customer_id: number
  customer_material_code: string
  internal_material_id: number
}) => apiClient.post('/materials/mappings', data)
export const updateMappingApi = (id: number, data: any) =>
  apiClient.put(`/materials/mappings/${id}`, data)
export const deleteMappingApi = (id: number) =>
  apiClient.delete(`/materials/mappings/${id}`)

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
export const directOutboundApi = (reelId: number, data: {
  quantity: number
  operator: string
  note?: string
  release_slot?: boolean
}) => apiClient.post(`/inventory/reels/${reelId}/direct-out`, data)

// Receipt
export const createReceiptApi = (data: { type: string; operator: string; customer_id?: number }) =>
  apiClient.post('/receipts', data)
export const scanReceiptApi = (
  receiptId: number,
  data: {
    barcode: string
    operator: string
    qty?: number
    manual_material_id?: number
    is_new_material?: boolean
    new_material_code?: string
    new_material_name?: string
    printer_ip?: string
    printer_port?: number
  }
) => apiClient.post(`/receipts/${receiptId}/scan`, data)
export const scanPreviewApi = (receiptId: number, data: { barcode: string; operator: string; qty?: number }) =>
  apiClient.post(`/receipts/${receiptId}/scan-preview`, data)
export const getReceiptListApi = (params?: any) =>
  apiClient.get('/receipts', { params })
export const getReceiptApi = (id: number) =>
  apiClient.get(`/receipts/${id}`)
export const assignSlotApi = (receiptId: number, data: { detail_id: number; shelf_slot_id: number }) =>
  apiClient.post(`/receipts/${receiptId}/assign-slot`, data)
export const confirmReceiptApi = (id: number) =>
  apiClient.put(`/receipts/${id}/confirm`)
export const completeReceiptApi = (id: number) =>
  apiClient.put(`/receipts/${id}/complete`)
export const reprintLabelApi = (
  receiptId: number,
  data: { receipt_reel_id: number; printer_ip?: string; printer_port?: number }
) => apiClient.post(`/receipts/${receiptId}/reprint`, data)

// Issue
export const getIssueListApi = (params: any) =>
  apiClient.get('/issues', { params })
export const createIssueApi = (data: any) =>
  apiClient.post('/issues', data)
export const calculateIssueApi = (orderId: number, data: { strategy: string }) =>
  apiClient.post(`/issues/${orderId}/calculate`, data)
export const assignLedApi = (orderId: number) =>
  apiClient.post(`/issues/${orderId}/assign`)
export const confirmPickApi = (orderId: number, data: { barcode: string; reel_id: number }) =>
  apiClient.post(`/issues/${orderId}/confirm-pick`, data)

// XR
export const getXRListApi = (params: any) =>
  apiClient.get('/xr', { params })
export const uploadXrApi = (data: { reel_id: string; qty: number }) =>
  apiClient.post('/xr/upload', data)
export const matchXRApi = (batchId: number, data: { reel_id: number }) =>
  apiClient.post(`/xr/${batchId}/match`, data)
export const confirmXRRestockApi = (batchId: number, data: { shelf_slot_id: number }) =>
  apiClient.post(`/xr/${batchId}/confirm-restock`, data)

// BOM
export const getBomListApi = (params?: { customer_id?: number; product_code?: string; status?: string }) =>
  apiClient.get('/bom', { params })
export const createBomApi = (data: { customer_id: number; product_material_id: number; version?: string; description?: string }) =>
  apiClient.post('/bom', data)
export const getBomApi = (bomId: number) =>
  apiClient.get(`/bom/${bomId}`)
export const updateBomApi = (bomId: number, data: { version?: string; status?: string; description?: string }) =>
  apiClient.put(`/bom/${bomId}`, data)
export const deleteBomApi = (bomId: number) =>
  apiClient.delete(`/bom/${bomId}`)
export const addBomItemApi = (bomId: number, data: any) =>
  apiClient.post(`/bom/${bomId}/items`, data)
export const updateBomItemApi = (bomId: number, itemId: number, data: any) =>
  apiClient.put(`/bom/${bomId}/items/${itemId}`, data)
export const deleteBomItemApi = (bomId: number, itemId: number) =>
  apiClient.delete(`/bom/${bomId}/items/${itemId}`)
export const uploadBomApi = (file: File, customerCode?: string, version?: string) => {
  const formData = new FormData()
  formData.append('file', file)
  const params: any = {}
  if (customerCode) params.customer_code = customerCode
  if (version) params.version = version
  return apiClient.post('/bom/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params,
  })
}
export const generateIssueFromBomApi = (bomId: number, data: any) =>
  apiClient.post(`/bom/${bomId}/generate-issue`, data)
export const downloadBomTemplateApi = async () => {
  const res = await apiClient.get('/bom/template', { responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([res.data]))
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', 'BOM导入模板.xlsx')
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

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

// Customers
export const getCustomersApi = () =>
  apiClient.get('/customers')
export const createCustomerApi = (data: { name: string; code: string; contact_name?: string; contact_phone?: string; address?: string }) =>
  apiClient.post('/customers', data)
export const updateCustomerApi = (id: number, data: { name: string; code: string; contact_name?: string; contact_phone?: string; address?: string }) =>
  apiClient.put(`/customers/${id}`, data)
export const deleteCustomerApi = (id: number) =>
  apiClient.delete(`/customers/${id}`)
