package com.smes.pda.data.model

data class MaterialCalcResult(
    val materialId: Int,
    val materialName: String,
    val requiredQty: Int,
    val shortage: Int = 0
)

data class PalletSelection(
    val palletId: Int,
    val barcode: String,
    val materialName: String,
    val availableQty: Int,
    val pickQty: Int,
    val location: String? = null
)

data class IssueCalculateResponse(
    val orderId: Int,
    val materialCalcResults: List<MaterialCalcResult> = emptyList(),
    val palletsSelected: List<PalletSelection> = emptyList(),
    val shortage: Int = 0,
    val strategy: String? = null
)
