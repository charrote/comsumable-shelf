package com.smes.pda.data.model

data class ReceiptDetailResponse(
    val id: Int,
    val type: String? = null,
    val operator: String? = null,
    val status: String? = null,
    val createdAt: String? = null
)
