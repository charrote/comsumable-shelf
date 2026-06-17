package com.smes.pda.data.model

data class InventoryPalletItem(
    val palletId: Int,
    val barcode: String,
    val materialName: String? = null,
    val customerName: String? = null,
    val location: String? = null,
    val qty: Int? = null,
    val status: String? = null
)

data class InventorySummary(
    val totalPallets: Int = 0,
    val totalMaterials: Int = 0,
    val totalQty: Int = 0
)

data class InventoryResponse(
    val pallets: List<InventoryPalletItem> = emptyList(),
    val summary: InventorySummary? = null
)
