package com.smes.pda.data.model

import kotlinx.serialization.Serializable

@Serializable
data class MaterialResponse(
    val id: Int,
    val code: String,
    val name: String,
    val spec: String? = null,
    val unit: String = "盘",
    val qty_per_pallet: Double? = null,
    val category: String? = null,
    val stock_balance: Double? = null
)
