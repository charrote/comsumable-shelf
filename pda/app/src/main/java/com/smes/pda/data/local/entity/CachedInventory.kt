package com.smes.pda.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "cached_inventory")
data class CachedInventory(
    @PrimaryKey val pallet_id: Int,
    val material_code: String,
    val material_name: String?,
    val quantity: Double,
    val shelf_code: String?,
    val status: String,
    val last_sync_at: Long = System.currentTimeMillis()
)
