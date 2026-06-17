// Auth
export interface LoginRequest {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export interface UserResponse {
  id: number
  username: string
  role: string
  customer_id?: number
  customer_name?: string
}

// Materials
export interface MaterialResponse {
  id: number
  code: string
  name: string
  spec?: string
  unit: string
  qty_per_pallet?: number
  category?: string
  stock_balance?: number
}

// Receipts (Inbound)
export interface ReceiptScanRequest {
  barcode: string
  operator: string
}

export interface ReceiptScanResponse {
  status: string
  action: string
  inventory_pallet_id?: number
  assigned_slot?: number
  duplicate_flag: boolean
  warning?: string
  message: string
}

export interface ReceiptCreate {
  type?: string
  operator: string
}

export interface ReceiptDetailResponse {
  id: number
  receipt_no: string
  customer_id: number
  created_at: string
  operator: string
  status: string
  items: ReceiptItem[]
}

export interface ReceiptItem {
  material_id: number
  quantity: number
  barcode?: string
}

// Issues (Outbound)
export interface IssueCalculateRequest {
  strategy?: string
}

export interface PalletSelection {
  pallet_id: number
  quantity: number
  last_in_time: string
  shelf_slot_id: number
}

export interface MaterialCalcResult {
  material_id: number
  material_code: string
  material_name: string
  required_qty: number
  available_qty: number
  strategy: string
  pallets_selected: PalletSelection[]
  total_selected: number
  shortage: number
}

export interface IssueCalculateResponse {
  issue_order_id: number
  calculated_at: string
  strategy_used: string
  materials: MaterialCalcResult[]
}

export interface IssueConfirmPickRequest {
  barcode: string
  pallet_id: number
  operator: string
}

export interface IssueConfirmPickResponse {
  status: string
  picked_qty: number
  remaining_qty: number
  all_picked: boolean
  cleared_leds: number[]
  message: string
}

export interface IssueAssignResponse {
  assigned: boolean
  led_commands_created: number
  shelf_id: number
  commands: { command_id: number; slot_id: number; color: string; status: string }[]
  message: string
}

export interface IssueOrderResponse {
  id: number
  order_no: string
  customer_id: number
  status: string
  created_at?: string
  details?: IssueDetailResponse[]
}

export interface IssueDetailResponse {
  id: number
  material_id: number
  material_code?: string
  material_name?: string
  required_qty: number
  picked_qty: number
  status: string
}

// Inventory
export interface PalletInfo {
  pallet_id: number
  material_code: string
  material_name?: string
  quantity: number
  original_quantity?: number
  shelf_slot_id?: number
  shelf_code?: string
  first_in_time?: string
  last_in_time?: string
  status: string
}

export interface InventoryResponse {
  pallets: PalletInfo[]
  summary?: {
    total_pallets?: number
    total_quantity?: number
    exhausted_pallets?: number
  }
}

export interface TrackingPalletResponse {
  pallet_id: number
  material_code: string
  material_name?: string
  quantity: number
  last_out_time?: string
  status: string
  xr_matched: boolean
}

// Shelves
export interface ShelfResponse {
  id: number
  code: string
  name?: string
  a_sides: number
  b_sides: number
  total_slots: number
  controller_ip?: string
  controller_port: number
  location?: string
  active: number
}

export interface ShelfSlotResponse {
  id: number
  shelf_id: number
  side: string
  board_address: number
  slot_on_board: number
  global_index: number
  modbus_tcp_id: number
  modbus_coil_base: number
}
