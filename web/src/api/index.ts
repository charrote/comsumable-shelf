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

// ── Hardware Debug ──
export const getHardwareDebugStatusApi = () =>
  apiClient.get('/hardware-debug/status')
export const hardwareDebugConnectApi = (ip: string, port: number = 502) =>
  apiClient.post('/hardware-debug/connect', { ip, port })
export const hardwareDebugDisconnectApi = () =>
  apiClient.post('/hardware-debug/disconnect')
export const hardwareDebugPingApi = () =>
  apiClient.get('/hardware-debug/ping')

// Mainboard
export const getMainboardInfoApi = () =>
  apiClient.get('/hardware-debug/mainboard/info')
export const getMainboardConfigApi = () =>
  apiClient.get('/hardware-debug/mainboard/config')
export const getMainboardRelaysApi = () =>
  apiClient.get('/hardware-debug/mainboard/relays')
export const setMainboardRelayApi = (relayNum: number, on: boolean) =>
  apiClient.post('/hardware-debug/mainboard/relay', { relay_num: relayNum, on })
export const calibrateMainboardApi = () =>
  apiClient.post('/hardware-debug/mainboard/calibrate')
export const resetMainboardApi = () =>
  apiClient.post('/hardware-debug/mainboard/reset')
export const saveMainboardConfigApi = () =>
  apiClient.post('/hardware-debug/mainboard/save-config')

// Raw Modbus
export const debugReadRegistersApi = (address: number, count: number, funcCode: number = 3, station: number = 200) =>
  apiClient.post('/hardware-debug/read-registers', { address, count, func_code: funcCode, station })
export const debugWriteRegisterApi = (address: number, value: number, station: number = 200) =>
  apiClient.post('/hardware-debug/write-register', { address, value, station })
export const debugReadCoilsApi = (address: number, count: number, station: number = 200) =>
  apiClient.post('/hardware-debug/read-coils', { address, count, station })
export const debugWriteCoilApi = (address: number, on: boolean, station: number = 200) =>
  apiClient.post('/hardware-debug/write-coil', { address, on, station })
export const debugWriteCoilsApi = (address: number, values: boolean[], station: number = 200) =>
  apiClient.post('/hardware-debug/write-coils', { address, values, station })
export const debugReadDigitalInputsApi = (address: number, count: number, station: number = 200) =>
  apiClient.post('/hardware-debug/read-digital-inputs', { address, count, station })

// LED Boards
export const getDebugBoardsApi = () =>
  apiClient.get('/hardware-debug/boards')
export const getDebugBoardInfoApi = (station: number) =>
  apiClient.get(`/hardware-debug/boards/${station}/info`)
export const getDebugBoardSlotsApi = (station: number, slotCount: number = 20) =>
  apiClient.get(`/hardware-debug/boards/${station}/slots`, { params: { slot_count: slotCount } })
export const getDebugBoardAdValuesApi = (station: number) =>
  apiClient.get(`/hardware-debug/boards/${station}/ad-values`)
export const getDebugBoardCalibrationApi = (station: number) =>
  apiClient.get(`/hardware-debug/boards/${station}/calibration`)
export const debugControlLedApi = (station: number, slotNum: number, color: string) =>
  apiClient.post(`/hardware-debug/boards/${station}/led`, { slot_num: slotNum, color })
export const debugControlAllLedsApi = (station: number, colors: string[]) =>
  apiClient.post(`/hardware-debug/boards/${station}/led-all`, { colors })
export const debugLedTestApi = (station: number) =>
  apiClient.post(`/hardware-debug/boards/${station}/led-test`)
export const debugCalibrateBoardApi = (station: number) =>
  apiClient.post(`/hardware-debug/boards/${station}/calibrate`)
export const debugResetBoardApi = (station: number) =>
  apiClient.post(`/hardware-debug/boards/${station}/reset`)
export const debugSetJudgmentApi = (station: number, value: number) =>
  apiClient.post(`/hardware-debug/boards/${station}/set-judgment`, { value })

// Logs
export const getHardwareDebugLogsApi = (since?: number, level?: string, limit?: number) =>
  apiClient.get('/hardware-debug/logs', { params: { since, level, limit } })
export const clearHardwareDebugLogsApi = () =>
  apiClient.post('/hardware-debug/logs/clear')

// Mainboard slot states (from controller's cache)
export const getMainboardSlotsApi = (face: 'A' | 'B', count: number = 700) =>
  apiClient.get('/hardware-debug/mainboard/slots', { params: { face, count } })

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
