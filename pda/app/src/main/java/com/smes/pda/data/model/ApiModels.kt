package com.smes.pda.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// ======================== Auth ========================

@Serializable
data class LoginRequest(
    val username: String,
    val password: String
)

@Serializable
data class TokenResponse(
    @SerialName("access_token") val accessToken: String,
    @SerialName("token_type") val tokenType: String = "bearer",
    @SerialName("expires_in") val expiresIn: Int = 0
)

@Serializable
data class UserResponse(
    val id: Int,
    val username: String,
    val role: String,
    @SerialName("customer_id") val customerId: Int? = null,
    @SerialName("customer_name") val customerName: String? = null
)

// ======================== Receipt ========================

@Serializable
data class CreateReceiptRequest(
    val type: String = "normal",
    val operator: String,
    @SerialName("customer_id") val customerId: Int = 1
)

@Serializable
data class ReceiptDetailResponse(
    val id: Int,
    @SerialName("receipt_no") val receiptNo: String? = null,
    @SerialName("customer_id") val customerId: Int? = null,
    @SerialName("created_at") val createdAt: String? = null,
    val operator: String? = null,
    val status: String? = null,
    val items: List<ReceiptItemDto> = emptyList()
)

@Serializable
data class ReceiptItemDto(
    val id: Int,
    @SerialName("material_id") val materialId: Int? = null,
    val quantity: Double? = null,
    val barcode: String? = null,
    @SerialName("reel_id") val inventoryPalletId: Int? = null,
    @SerialName("customer_material_code") val customerMaterialCode: String? = null,
    @SerialName("internal_label_printed") val internalLabelPrinted: Boolean? = null,
    @SerialName("label_printed_at") val labelPrintedAt: String? = null
)

@Serializable
data class MaterialCandidateDto(
    @SerialName("material_id") val materialId: Int,
    val code: String,
    val name: String,
    val confidence: Double,
    @SerialName("extracted_code") val extractedCode: String = ""
)

@Serializable
data class ManualEntryRequest(
    val operator: String,
    @SerialName("material_code") val materialCode: String,
    @SerialName("material_name") val materialName: String = "",
    val spec: String? = null,
    val quantity: Double = 1.0,
    @SerialName("batch_no") val batchNo: String? = null,
    @SerialName("date_code") val dateCode: String? = null,
    @SerialName("supplier_code") val supplierCode: String? = null,
    @SerialName("print_label") val printLabel: Boolean? = null,
    @SerialName("printer_ip") val printerIp: String? = null,
    @SerialName("printer_port") val printerPort: Int? = null,
)

@Serializable
data class ScanRequest(
    val barcode: String,
    val operator: String,
    val qty: Double? = null,
    @SerialName("manual_material_id") val manualMaterialId: Int? = null,
    @SerialName("is_new_material") val isNewMaterial: Boolean? = null,
    @SerialName("new_material_code") val newMaterialCode: String? = null,
    @SerialName("new_material_name") val newMaterialName: String? = null,
    @SerialName("printer_ip") val printerIp: String? = null,
    @SerialName("printer_port") val printerPort: Int? = null
)

@Serializable
data class ReceiptScanResponse(
    val status: String,
    val action: String? = null,
    @SerialName("reel_id") val inventoryPalletId: Int? = null,
    @SerialName("assigned_slot") val assignedSlot: Int? = null,
    val quantity: Double = 0.0,
    @SerialName("duplicate_flag") val duplicateFlag: Boolean = false,
    val warning: String? = null,
    val candidates: List<MaterialCandidateDto>? = null,
    @SerialName("customer_material_code") val customerMaterialCode: String? = null,
    @SerialName("material_id") val materialId: Int? = null,
    @SerialName("material_code") val materialCode: String? = null,
    @SerialName("material_name") val materialName: String? = null,
    val confidence: Double? = null,
    @SerialName("label_printed") val labelPrinted: Boolean? = null,
    val message: String? = null
)

// ======================== Issue ========================

@Serializable
data class IssueListItem(
    val id: Int,
    @SerialName("order_no") val orderNo: String? = null,
    @SerialName("bom_header_id") val bomHeaderId: Int? = null,
    @SerialName("bom_name") val bomName: String? = null,
    @SerialName("customer_id") val customerId: Int? = null,
    @SerialName("required_date") val requiredDate: String? = null,
    val status: String? = null,
    @SerialName("total_materials") val totalMaterials: Int? = null,
    @SerialName("created_at") val createdAt: String? = null
)

@Serializable
data class IssueDataWrapper(
    val data: List<IssueListItem> = emptyList()
)

@Serializable
data class IssueDetailResponse(
    val id: Int,
    @SerialName("order_no") val orderNo: String? = null,
    @SerialName("bom_header_id") val bomHeaderId: Int? = null,
    @SerialName("customer_id") val customerId: Int? = null,
    @SerialName("required_date") val requiredDate: String? = null,
    val status: String? = null,
    @SerialName("created_at") val createdAt: String? = null,
    val details: List<IssueDetailItem> = emptyList()
)

@Serializable
data class IssueDetailItem(
    val id: Int,
    @SerialName("material_id") val materialId: Int? = null,
    @SerialName("required_qty") val requiredQty: Double? = null,
    @SerialName("picked_qty") val pickedQty: Double? = null,
    @SerialName("reel_ids") val reelIds: String? = null,
    @SerialName("pick_strategy") val pickStrategy: String? = null,
    val status: String? = null
)

@Serializable
data class CalculateRequest(
    val strategy: String = "config"
)

@Serializable
data class ReelSelection(
    @SerialName("reel_id") val reelId: Int,
    val quantity: Double,
    @SerialName("last_in_time") val lastInTime: String? = null,
    @SerialName("shelf_slot_id") val shelfSlotId: Int? = null
)

@Serializable
data class MaterialCalcResult(
    @SerialName("material_id") val materialId: Int,
    @SerialName("material_code") val materialCode: String = "",
    @SerialName("material_name") val materialName: String = "",
    @SerialName("required_qty") val requiredQty: Double,
    @SerialName("available_qty") val availableQty: Double = 0.0,
    val strategy: String = "",
    @SerialName("reels_selected") val palletsSelected: List<ReelSelection> = emptyList(),
    @SerialName("total_selected") val totalSelected: Double = 0.0,
    val shortage: Double = 0.0
)

@Serializable
data class CalculateResponse(
    @SerialName("issue_order_id") val issueOrderId: Int,
    @SerialName("calculated_at") val calculatedAt: String? = null,
    @SerialName("strategy_used") val strategyUsed: String = "",
    val materials: List<MaterialCalcResult> = emptyList()
)

@Serializable
data class AssignResponse(
    val assigned: Boolean = false,
    @SerialName("led_commands_created") val ledCommandsCreated: Int = 0,
    @SerialName("shelf_id") val shelfId: Int = 0,
    val commands: List<LedCommandDto> = emptyList(),
    val message: String? = null
)

@Serializable
data class LedCommandDto(
    @SerialName("command_id") val commandId: Int? = null,
    @SerialName("slot_id") val slotId: Int? = null,
    val color: String? = null,
    val status: String? = null
)

@Serializable
data class ConfirmPickRequest(
    val barcode: String,
    @SerialName("reel_id") val reelId: Int,
    val operator: String
)

@Serializable
data class ConfirmPickResponse(
    val status: String,
    @SerialName("picked_qty") val pickedQty: Double = 0.0,
    @SerialName("remaining_qty") val remainingQty: Double = 0.0,
    @SerialName("all_picked") val allPicked: Boolean = false,
    @SerialName("cleared_leds") val clearedLeds: List<Int> = emptyList(),
    val message: String? = null
)

// ======================== Inventory ========================

@Serializable
data class InventoryItem(
    @SerialName("reel_id") val reelId: Int,
    @SerialName("material_code") val materialCode: String? = null,
    val quantity: Double? = null,
    @SerialName("original_quantity") val originalQuantity: Double? = null,
    @SerialName("shelf_slot_id") val shelfSlotId: Int? = null,
    @SerialName("shelf_code") val shelfCode: String? = null,
    @SerialName("first_in_time") val firstInTime: String? = null,
    @SerialName("last_in_time") val lastInTime: String? = null,
    val status: String? = null
)

@Serializable
data class InventorySummary(
    @SerialName("total_pallets") val totalPallets: Int = 0,
    @SerialName("total_quantity") val totalQuantity: Double = 0.0,
    @SerialName("exhausted_pallets") val exhaustedPallets: Int = 0
) {
    fun nonNull() = this // convenience
}

@Serializable
data class InventoryResponse(
    val pallets: List<InventoryItem> = emptyList(),
    val summary: InventorySummary? = null
)

// Type alias for ViewModel usage
typealias TrackingPalletItem = TrackingReelItem

@Serializable
data class TrackingReelItem(
    @SerialName("reel_id") val reelId: Int,
    @SerialName("material_code") val materialCode: String? = null,
    val quantity: Double? = null,
    @SerialName("last_out_time") val lastOutTime: String? = null,
    val status: String? = null,
    @SerialName("xr_matched") val xrMatched: Boolean = false
)

@Serializable
data class TrackingListWrapper(
    val pallets: List<TrackingReelItem> = emptyList()
)

// ======================== Direct Outbound ========================

@Serializable
data class DirectOutRequest(
    val quantity: Double,
    val operator: String,
    val note: String? = null,
    @SerialName("release_slot") val releaseSlot: Boolean = true
)

@Serializable
data class DirectOutResponse(
    val status: String,
    @SerialName("reel_id") val inventoryPalletId: Int,
    @SerialName("quantity_before") val quantityBefore: Double,
    @SerialName("quantity_after") val quantityAfter: Double,
    @SerialName("reel_status") val reelStatus: String,
    @SerialName("slot_released") val slotReleased: Boolean = false,
    val message: String
)

// ======================== Dashboard (Home) ========================

@Serializable
data class DashboardResponse(
    @SerialName("app_name") val appName: String = "智能物料管理系统",
    @SerialName("today_inbound") val todayInbound: Int = 0,
    @SerialName("today_outbound") val todayOutbound: Int = 0,
    @SerialName("on_shelf_pallets") val onShelfPallets: Int = 0,
    @SerialName("tracking_pallets") val trackingPallets: Int = 0,
    @SerialName("pending_issues") val pendingIssues: Int = 0,
    @SerialName("pending_receipts") val pendingReceipts: Int = 0
)
