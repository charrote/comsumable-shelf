package com.smes.pda.data.model

data class IssueOrderResponse(
    val id: Int,
    val orderNo: String? = null,
    val customerId: Int? = null,
    val customerName: String? = null,
    val status: String? = null,
    val materialName: String? = null,
    val requiredQty: Int? = null,
    val pickedQty: Int? = null,
    val createdAt: String? = null
)
