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
    @SerialName("inventory_pallet_id") val inventoryPalletId: Int? = null
)

@Serializable
data class ScanRequest(
    val barcode: String,
    val operator: String,
    val qty: Double? = null
)

@Serializable
data class ReceiptScanResponse(
    val status: String,
    val action: String? = null,
    @SerialName("inventory_pallet_id") val inventoryPalletId: Int? = null,
    @SerialName("assigned_slot") val assignedSlot: Int? = null,
    @SerialName("duplicate_flag") val duplicateFlag: Boolean = false,
    val warning: String? = null,
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
    @SerialName("pallet_ids") val palletIds: String? = null,
    @SerialName("pick_strategy") val pickStrategy: String? = null,
    val status: String? = null
)

@Serializable
data class CalculateRequest(
    val strategy: String = "config"
)

@Serializable
data class PalletSelection(
    @SerialName("pallet_id") val palletId: Int,
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
    @SerialName("pallets_selected") val palletsSelected: List<PalletSelection> = emptyList(),
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
    @SerialName("pallet_id") val palletId: Int,
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
    @SerialName("pallet_id") val palletId: Int,
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

@Serializable
data class TrackingPalletItem(
    @SerialName("pallet_id") val palletId: Int,
    @SerialName("material_code") val materialCode: String? = null,
    val quantity: Double? = null,
    @SerialName("last_out_time") val lastOutTime: String? = null,
    val status: String? = null,
    @SerialName("xr_matched") val xrMatched: Boolean = false
)

@Serializable
data class TrackingListWrapper(
    val pallets: List<TrackingPalletItem> = emptyList()
)

// ======================== Dashboard (Home) ========================

@Serializable
data class DashboardResponse(
    @SerialName("today_inbound") val todayInbound: Int = 0,
    @SerialName("today_outbound") val todayOutbound: Int = 0,
    @SerialName("on_shelf_pallets") val onShelfPallets: Int = 0,
    @SerialName("tracking_pallets") val trackingPallets: Int = 0,
    @SerialName("pending_issues") val pendingIssues: Int = 0,
    @SerialName("pending_receipts") val pendingReceipts: Int = 0
)
