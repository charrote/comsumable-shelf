package com.smes.pda.data.local.dao

import androidx.room.*
import com.smes.pda.data.local.entity.CachedInventory
import kotlinx.coroutines.flow.Flow

@Dao
interface InventoryDao {
    @Query("SELECT * FROM cached_inventory ORDER BY last_sync_at DESC")
    fun getAll(): Flow<List<CachedInventory>>

    @Query("SELECT * FROM cached_inventory WHERE status = :status ORDER BY last_sync_at DESC")
    fun getByStatus(status: String): Flow<List<CachedInventory>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(items: List<CachedInventory>)

    @Query("DELETE FROM cached_inventory")
    suspend fun clearAll()

    @Query("DELETE FROM cached_inventory WHERE pallet_id = :palletId")
    suspend fun deleteById(palletId: Int)
}
