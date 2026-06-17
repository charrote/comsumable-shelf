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
export interface MaterialCandidate {
  material_id: number
  code: string
  name: string
  confidence: number
  extracted_code: string
}

export interface ReceiptScanRequest {
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

export interface ReceiptScanResponse {
  status: string              // ok | duplicate | pending_review | error
  action: string              // first_in | duplicate | pending_review | new_material
  reel_id?: number
  assigned_slot?: number
  quantity: number
  duplicate_flag: boolean
  warning?: string

  // Pending review
  candidates?: MaterialCandidate[]
  customer_material_code?: string

  // Matched / newly created material info
  material_id?: number
  material_code?: string
  material_name?: string
  confidence?: number

  // Label printing
  label_printed?: boolean

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
  id: number
  material_id: number
  quantity: number
  barcode?: string
  customer_material_code?: string
  reel_id?: number
  internal_label_printed?: boolean
  label_printed_at?: string
}

// Issues (Outbound)
export interface IssueCalculateRequest {
  strategy?: string
}

export interface ReelSelection {
  reel_id: number
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
  reels_selected: ReelSelection[]
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
  reel_id: number
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
export interface ReelInfo {
  reel_id: number
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
  reels: ReelInfo[]
  summary?: {
    total_reels?: number
    total_quantity?: number
    exhausted_reels?: number
  }
}

export interface TrackingReelResponse {
  reel_id: number
  material_code: string
  material_name?: string
  quantity: number
  last_out_time?: string
  status: string
  xr_matched: boolean
}

// Direct Outbound
export interface DirectOutRequest {
  quantity: number
  operator: string
  note?: string
  release_slot?: boolean
}

export interface DirectOutResponse {
  status: string           // ok | exhausted | error
  reel_id: number
  quantity_before: number
  quantity_after: number
  reel_status: string
  slot_released: boolean
  message: string
}

// Customer Material Mapping
export interface CustomerMaterialMappingResponse {
  id: number
  customer_id: number
  customer_material_code: string
  internal_material_id: number
  internal_material_code: string
  internal_material_name: string
  customer_name: string
  active: number
  created_at?: string
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
