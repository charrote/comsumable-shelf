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

// BOM
export interface BOMResponse {
  id: number
  customer_id: number
  customer_name?: string
  product_material_id: number
  product_code?: string
  product_name?: string
  version: string
  status: string
  description?: string
  item_count?: number
  created_at?: string
  updated_at?: string
}

// Receipts (Inbound)
export interface ManualEntryRequest {
  operator: string
  material_code: string
  material_name?: string
  spec?: string
  quantity: number
  batch_no?: string
  date_code?: string
  supplier_code?: string
  print_label?: boolean
  printer_ip?: string
  printer_port?: number
}

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

export interface BarcodePreviewResponse {
  barcode: string
  status: string              // ok | pending_review | new_material | error
  confidence: number
  material_code: string
  material_name?: string
  material_id?: number
  quantity: number
  unit: string
  batch_no?: string
  date_code?: string
  spec?: string
  supplier_code?: string
  extracted_fields?: BarcodePreviewItem[]
  candidates?: MaterialCandidate[]
  message: string
}

export interface BarcodePreviewItem {
  field: string
  label: string
  value: string
  editable: boolean
}

export interface ReceiptCreate {
  type?: string
  operator: string
  customer_id?: number
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

// Shelving
export interface ShelvingBindRequest {
  reel_id: number
  shelf_id: number
  shelf_slot_id?: number
  operator: string
}

export interface ShelvingBindResponse {
  status: string
  reel_id: number
  shelf_id: number
  shelf_slot_id: number
  shelf_code?: string
  slot_code?: string
  message: string
}

export interface ShelvingScanResponse {
  status: string           // ok | already_bound | error
  reel_id: number
  material_code: string
  material_name?: string
  quantity: number
  shelf_slot_id?: number
  shelf_code?: string
  slot_code?: string
  message: string
}

// Issues (Outbound)
export interface IssueCreateRequest {
  bom_id: number
  production_quantity: number
  customer_id?: number
  required_date?: string
}

export interface IssueCalculateRequest {
  strategy?: string
}

export interface ReelSelection {
  reel_id: number
  quantity: number
  last_in_time: string
  shelf_slot_id: number
}

export interface ReelAssignment {
  reel_id: number
  reel_barcode?: string
  shelf_slot_id?: number
  slot_code?: string
  reel_qty: number
  original_quantity: number
  pick_quantity: number
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

export interface IssueAssignResponse {
  assigned: boolean
  led_commands_created: number
  shelf_id: number
  commands: { command_id: number; slot_id: number; color: string; status: string }[]
  message: string
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

export interface IssueOrderResponse {
  id: number
  order_no: string
  bom_id?: number
  product_code?: string
  product_name?: string
  production_quantity?: number
  customer_id?: number
  customer_name?: string
  status: string
  required_date?: string
  created_at?: string
  detail_count?: number
  details?: IssueDetailResponse[]
}

export interface IssueDetailResponse {
  id: number
  material_id: number
  material_code?: string
  material_name?: string
  material_unit?: string
  required_qty: number
  assigned_qty?: number
  picked_qty: number
  reel_assignments?: ReelAssignment[]
  shortage?: number
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
  pallets: ReelInfo[]
  summary?: {
    total_pallets?: number
    total_quantity?: number
    exhausted_pallets?: number
  }
}

export interface TrackingReelResponse {
  reel_id: number
  material_code: string
  material_name?: string
  quantity: number
  last_out_time?: string
  status: string
  xr_matched?: boolean
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
  max_quantity?: number
  last_event_at?: string
  last_sensor_state?: number
}

export interface SlotSensorState {
  slot_id: number
  side: string
  board_address: number
  slot_on_board: number
  has_material: boolean
  last_event_at?: string
  bound_reel_id?: number
}

// Dashboard
export interface DashboardSummary {
  app_name?: string
  today_inbound: number
  today_outbound: number
  pending_issues: number
  on_shelf_pallets: number
  tracking_pallets: number
  pending_receipts: number
}
