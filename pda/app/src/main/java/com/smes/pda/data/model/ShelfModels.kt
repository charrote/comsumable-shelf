package com.smes.pda.data.model

import kotlinx.serialization.Serializable

@Serializable
data class ShelfResponse(
    val id: Int,
    val code: String,
    val name: String? = null,
    val a_sides: Int,
    val b_sides: Int,
    val total_slots: Int,
    val controller_ip: String? = null,
    val controller_port: Int = 502,
    val location: String? = null,
    val active: Int = 1
)

@Serializable
data class ShelfSlotResponse(
    val id: Int,
    val shelf_id: Int,
    val side: String,
    val board_address: Int,
    val slot_on_board: Int,
    val global_index: Int,
    val modbus_tcp_id: Int,
    val modbus_coil_base: Int
)
