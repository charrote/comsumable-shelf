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
export const batchDeleteMaterialsApi = (ids: number[]) =>
  apiClient.post('/materials/batch-delete', { ids })
export const batchDeleteMaterialsPermanentlyApi = (ids: number[]) =>
  apiClient.post('/materials/batch-delete-permanently', { ids })
export const batchUpdateMaterialsApi = (ids: number[], fields: any) =>
  apiClient.put('/materials/batch-update', { ids, fields })
export const uploadMaterialsApi = (file: File, customerCode?: string) => {
  const formData = new FormData()
  formData.append('file', file)
  const params: any = {}
  if (customerCode) params.customer_code = customerCode
  return apiClient.post('/materials/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params,
  })
}
export const downloadMaterialTemplateApi = async () => {
  const res = await apiClient.get('/materials/template', { responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([res.data]))
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', '物料主数据导入模板.xlsx')
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}
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
export const createSlotApi = (shelfId: number, data: any) =>
  apiClient.post(`/shelves/${shelfId}/slots`, data)
export const updateSlotApi = (shelfId: number, slotId: number, data: any) =>
  apiClient.put(`/shelves/${shelfId}/slots/${slotId}`, data)
export const deleteSlotApi = (shelfId: number, slotId: number) =>
  apiClient.delete(`/shelves/${shelfId}/slots/${slotId}`)
export const rackTestApi = (shelfId: number, testMode: number = 15) =>
  apiClient.post(`/shelves/${shelfId}/rack-test`, { test_mode: testMode })
export const getSlotStatesExtendedApi = (shelfId: number) =>
  apiClient.get(`/shelves/${shelfId}/slots/state-extended`)

// Inventory
export const getInventoryApi = (params: any) =>
  apiClient.get('/inventory', { params })
export const getTrackingApi = () =>
  apiClient.get('/inventory/tracking')
export const directOutboundApi = (reelId: number, data: {
  operator: string
  note?: string
  release_slot?: boolean
}) => apiClient.post(`/inventory/reels/${reelId}/direct-out`, data)
export const exportInventoryApi = async (params: any) => {
  const res = await apiClient.get('/inventory/export', { params, responseType: 'blob' })
  const disposition = res.headers['content-disposition'] || ''
  const match = disposition.match(/filename\*=UTF-8''(.+)/)
  const filename = match ? decodeURIComponent(match[1]) : `库存列表.xlsx`
  const url = window.URL.createObjectURL(new Blob([res.data]))
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

// Receipt
export const createReceiptApi = (data: { type: string; operator: string; customer_id?: number; purchase_order_no?: string }) =>
  apiClient.post('/receipts', data)
export const manualEntryApi = (
  receiptId: number,
  data: {
    operator: string
    material_code: string
    material_name?: string
    spec?: string
    quantity: number
    batch_no?: string
    date_code?: string
    supplier_code?: string
    print_label?: boolean
  }
) => apiClient.post(`/receipts/${receiptId}/manual-entry`, data)
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
    print_label?: boolean
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
export const deleteReceiptApi = (id: number) =>
  apiClient.delete(`/receipts/${id}`)
export const batchDeleteReceiptsApi = (ids: number[]) =>
  apiClient.post('/receipts/batch-delete', { ids })
export const cancelReceiptItemsApi = (receiptId: number, receiptReelIds: number[]) =>
  apiClient.post(`/receipts/${receiptId}/items/cancel`, { receipt_reel_ids: receiptReelIds })

// Issue
export const getIssueListApi = (params: any) =>
  apiClient.get('/issues', { params })
export const getIssueApi = (orderId: number) =>
  apiClient.get(`/issues/${orderId}`)
export const createIssueApi = (data: any) =>
  apiClient.post('/issues', data)
export const calculateIssueApi = (orderId: number, data: { strategy: string }) =>
  apiClient.post(`/issues/${orderId}/calculate`, data)
export const assignLedApi = (orderId: number) =>
  apiClient.post(`/issues/${orderId}/assign`)
export const confirmPickApi = (orderId: number, data: { barcode: string; reel_id?: number; operator?: string }) =>
  apiClient.post(`/issues/${orderId}/confirm-pick`, data)
export const cancelIssueApi = (orderId: number) =>
  apiClient.post(`/issues/${orderId}/cancel`)

// XR
export const getXRListApi = (params: any) =>
  apiClient.get('/xr', { params })
export const uploadXrApi = (data: { reel_id: string; qty: number }) =>
  apiClient.post('/xr/upload', data)
export const matchXRApi = (batchId: number, data: { reel_id: number }) =>
  apiClient.post(`/xr/${batchId}/match`, data)
export const confirmXRRestockApi = (batchId: number, data: { shelf_slot_id?: number; cell_id?: string }) =>
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
export const uploadBomApi = (file: File, customerCode?: string, version?: string, productCode?: string, productName?: string) => {
  const formData = new FormData()
  formData.append('file', file)
  const params: any = {}
  if (customerCode) params.customer_code = customerCode
  if (version) params.version = version
  if (productCode) params.product_code = productCode
  if (productName) params.product_name = productName
  return apiClient.post('/bom/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params,
  })
}
export const generateIssueFromBomApi = (bomId: number, data: any) =>
  apiClient.post(`/bom/${bomId}/generate-issue`, data)
export const exportBomApi = async (bomId: number) => {
  const res = await apiClient.get(`/bom/${bomId}/export`, { responseType: 'blob' })
  const disposition = res.headers['content-disposition'] || ''
  const match = disposition.match(/filename\*=UTF-8''(.+)/)
  const filename = match ? decodeURIComponent(match[1]) : `BOM-${bomId}.xlsx`
  const url = window.URL.createObjectURL(new Blob([res.data]))
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}
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
export const uploadBomQixinApi = (file: File, customerCode?: string, version?: string, productCode?: string, productName?: string) => {
  const formData = new FormData()
  formData.append('file', file)
  const params: any = {}
  if (customerCode) params.customer_code = customerCode
  if (version) params.version = version
  if (productCode) params.product_code = productCode
  if (productName) params.product_name = productName
  return apiClient.post('/bom/upload-qixin', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params,
  })
}
export const downloadBomQixinTemplateApi = async () => {
  const res = await apiClient.get('/bom/template-qixin', { responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([res.data]))
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', '七鑫BOM导入模板.xlsx')
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

// Dashboard
export const getDashboardPendingListsApi = () =>
  apiClient.get('/dashboard/pending-lists')

// Report
export const getDailyReportApi = (date: string, customerId?: number) =>
  apiClient.get('/reports/daily', { params: { date, customer_id: customerId } })
export const getRecentTransactionsApi = (limit = 20) =>
  apiClient.get('/transactions/recent', { params: { limit } })
export const getCustomerSummaryApi = (params: any) =>
  apiClient.get('/reports/customer-summary', { params })

// Settings
export const getSettingsApi = () =>
  apiClient.get('/settings')
export const updateSettingApi = (key: string, value: string, description?: string) =>
  apiClient.put(`/settings/${key}`, { key, value, description })
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

// ── Barcode Definition ──
export const getBarcodeDefinitionsApi = () =>
  apiClient.get('/barcode-definitions')
export const getBarcodeDefinitionApi = (id: number) =>
  apiClient.get(`/barcode-definitions/${id}`)
export const createBarcodeDefinitionApi = (data: {
  name: string
  delimiter: string
  sample_barcode: string
  segments: { segment_index: number; segment_sample?: string; field_mapping: string; field_label: string }[]
}) => apiClient.post('/barcode-definitions', data)
export const updateBarcodeDefinitionApi = (id: number, data: any) =>
  apiClient.put(`/barcode-definitions/${id}`, data)
export const deleteBarcodeDefinitionApi = (id: number) =>
  apiClient.delete(`/barcode-definitions/${id}`)
export const previewBarcodeSplitApi = (sampleBarcode: string, delimiter: string) =>
  apiClient.post('/barcode-definitions/preview', { sample_barcode: sampleBarcode, delimiter })
export const testBarcodeDefinitionApi = (definitionId: number, barcode: string) =>
  apiClient.post('/barcode-definitions/test', { definition_id: definitionId, barcode })
export const getFieldMappingsApi = () =>
  apiClient.get('/barcode-definitions/field-mappings')

// ── Light Control Debug ──
export const getDebugShelvesApi = () =>
  apiClient.get('/light-debug/shelves')
export const debugSingleLightApi = (data: {
  cell_id: string
  led_color: number
  blink?: boolean
  turn_on_time?: number
}) => apiClient.post('/light-debug/single', data)
export const debugBatchLightApi = (data: {
  cells: { cell_id: string; led_color: number; blink?: boolean }[]
  turn_on_time?: number
  voice_text?: string
}) => apiClient.post('/light-debug/batch', data)
export const debugIndicatorApi = (data: {
  rack_id: string
  indicator_id?: number
  indicator_status?: number
  blink?: boolean
}) => apiClient.post('/light-debug/indicator', data)
export const debugRackTestApi = (data: {
  rack_id: string
  test_mode?: number
  interval?: number
}) => apiClient.post('/light-debug/test', data)
export const debugCellListApi = (data: {
  rack_id?: string
  filter?: string
  page_index?: number
  page_size?: number
}) => apiClient.post('/light-debug/cell-list', data)
export const debugTurnOffApi = (data: { cell_id: string }) =>
  apiClient.post('/light-debug/turn-off', data)
export const debugTurnOffAllApi = (data: { rack_id: string; page_size?: number }) =>
  apiClient.post('/light-debug/turn-off-all', data)
export const getCallbackEventsApi = (params?: { limit?: number; shelf_id?: number }) =>
  apiClient.get('/light-debug/callback-events', { params })
export const debugSensorTestApi = (data: {
  rack_id: string
  interval?: number
}) => apiClient.post('/light-debug/sensor-test', data)

// ── Suppliers ──
export const getSuppliersApi = () =>
  apiClient.get('/suppliers')
export const getAllSuppliersApi = () =>
  apiClient.get('/suppliers/all')
export const createSupplierApi = (data: {
  code: string
  name: string
  contact_name?: string
  contact_phone?: string
  address?: string
}) => apiClient.post('/suppliers', data)
export const updateSupplierApi = (id: number, data: {
  code: string
  name: string
  contact_name?: string
  contact_phone?: string
  address?: string
}) => apiClient.put(`/suppliers/${id}`, data)
export const deleteSupplierApi = (id: number) =>
  apiClient.delete(`/suppliers/${id}`)
export const uploadSuppliersApi = (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  return apiClient.post('/suppliers/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
export const downloadSupplierTemplateApi = async () => {
  const res = await apiClient.get('/suppliers/template', { responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([res.data]))
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', '供应商导入模板.xlsx')
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

// ── Data Backup ──
export const getBackupsApi = () =>
  apiClient.get('/backups')
export const getBackupApi = (id: number) =>
  apiClient.get(`/backups/${id}`)
export const createBackupApi = () =>
  apiClient.post('/backups')
export const restoreBackupApi = (id: number) =>
  apiClient.post(`/backups/${id}/restore`)
export const deleteBackupApi = (id: number) =>
  apiClient.delete(`/backups/${id}`)
