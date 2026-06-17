package com.smes.pda.data.repository

import com.smes.pda.data.model.ApiResult
import com.smes.pda.data.model.InventoryResponse
import com.smes.pda.data.model.TrackingListResponse
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
open class InventoryRepository @Inject constructor() {

    open suspend fun getInventory(
        customerId: Int? = null,
        materialId: Int? = null
    ): ApiResult<InventoryResponse> {
        return ApiResult.Error("Not implemented")
    }

    open suspend fun getTrackingInventory(): ApiResult<TrackingListResponse> {
        return ApiResult.Error("Not implemented")
    }
}
