package com.smes.pda.data.model

data class IssueConfirmPickResponse(
    val status: String,
    val pickedQty: Int = 0,
    val allPicked: Boolean = false,
    val message: String? = null,
    val remainingQty: Int = 0
)
