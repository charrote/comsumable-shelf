package com.smes.pda.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import com.smes.pda.data.local.dao.InventoryDao
import com.smes.pda.data.local.entity.CachedInventory

@Database(entities = [CachedInventory::class], version = 1, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    abstract fun inventoryDao(): InventoryDao
}
