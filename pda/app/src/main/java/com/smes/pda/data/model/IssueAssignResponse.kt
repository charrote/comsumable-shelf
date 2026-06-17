package com.smes.pda.data.model

data class LedCommand(
    val palletId: Int,
    val location: String,
    val ledColor: String = "red",
    val ledAction: String = "flash"
)

data class IssueAssignResponse(
    val orderId: Int,
    val ledCommands: List<LedCommand> = emptyList(),
    val message: String? = null
)
