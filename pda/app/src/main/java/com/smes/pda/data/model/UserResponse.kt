package com.smes.pda.data.model

data class UserResponse(
    val id: Int,
    val username: String,
    val displayName: String? = null,
    val role: String? = null
)
