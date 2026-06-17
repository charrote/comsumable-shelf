package com.smes.pda.data.model

data class ReceiptScanResponse(
    val id: Int,
    val status: String,
    val action: String? = null,
    val inventoryPalletId: Int? = null,
    val barcode: String? = null,
    val materialName: String? = null,
    val qty: Int? = null,
    val duplicateFlag: Boolean = false,
    val message: String? = null,
    val assignedSlot: String? = null
)
