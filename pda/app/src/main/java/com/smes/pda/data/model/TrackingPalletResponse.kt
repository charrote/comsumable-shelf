package com.smes.pda.data.model

data class TrackingPalletResponse(
    val palletId: Int,
    val barcode: String,
    val materialName: String? = null,
    val materialCode: String? = null,
    val customerName: String? = null,
    val location: String? = null,
    val status: String? = null,
    val qty: Int? = null,
    val quantity: Int? = null,
    val lastAction: String? = null,
    val lastActionTime: String? = null
)

data class TrackingListResponse(
    val pallets: List<TrackingPalletResponse> = emptyList(),
    val total: Int = 0
)
