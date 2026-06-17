package com.smes.pda.data.repository

import com.smes.pda.data.api.HttpException
import com.smes.pda.data.api.HttpService
import com.smes.pda.data.model.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
open class InventoryRepository @Inject constructor(
    private val httpService: HttpService
) {
    open suspend fun getInventory(
        customerId: Int? = null,
        materialId: Int? = null
    ): ApiResult<InventoryResponse> {
        return try {
            val params = buildString {
                if (customerId != null) append("customer_id=$customerId&")
                if (materialId != null) append("material_id=$materialId")
            }
            val path = if (params.isEmpty()) "inventory" else "inventory?$params"
            val response: InventoryResponse = httpService.get(path)
            ApiResult.Success(response)
        } catch (e: HttpException) {
            ApiResult.Error(e.responseBody, e.statusCode)
        } catch (e: Exception) {
            ApiResult.Error(e.message ?: "查询库存失败")
        }
    }

    open suspend fun getTrackingInventory(): ApiResult<List<TrackingPalletItem>> {
        return try {
            val wrapper: TrackingListWrapper = httpService.get("inventory/tracking")
            ApiResult.Success(wrapper.pallets)
        } catch (e: HttpException) {
            ApiResult.Error(e.responseBody, e.statusCode)
        } catch (e: Exception) {
            ApiResult.Error(e.message ?: "查询跟踪库存失败")
        }
    }

    /** Get dashboard summary for the home screen */
    open suspend fun getDashboardSummary(): ApiResult<DashboardResponse> {
        return try {
            // We aggregate from inventory stats
            val inventory: InventoryResponse = httpService.get("inventory")
            val tracking: TrackingListWrapper = httpService.get("inventory/tracking")

            val onShelf = inventory.pallets.count { it.status == "on_shelf" }

            val dash = DashboardResponse(
                onShelfPallets = onShelf,
                trackingPallets = tracking.pallets.size
            )
            ApiResult.Success(dash)
        } catch (e: HttpException) {
            ApiResult.Error(e.responseBody, e.statusCode)
        } catch (e: Exception) {
            ApiResult.Error(e.message ?: "获取首页摘要失败")
        }
    }
}
