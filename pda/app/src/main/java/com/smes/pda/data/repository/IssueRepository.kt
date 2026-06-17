package com.smes.pda.data.repository

import com.smes.pda.data.api.HttpException
import com.smes.pda.data.api.HttpService
import com.smes.pda.data.model.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
open class IssueRepository @Inject constructor(
    private val httpService: HttpService
) {
    open suspend fun listIssues(
        customerId: Int? = null,
        status: String? = null
    ): ApiResult<List<IssueListItem>> {
        return try {
            val params = buildString {
                if (customerId != null) append("customer_id=$customerId&")
                if (status != null) append("status=$status")
            }
            val path = if (params.isEmpty()) "issues" else "issues?$params"
            val wrapper: IssueDataWrapper = httpService.get(path)
            ApiResult.Success(wrapper.data)
        } catch (e: HttpException) {
            ApiResult.Error(e.responseBody, e.statusCode)
        } catch (e: Exception) {
            ApiResult.Error(e.message ?: "加载发料单列表失败")
        }
    }

    open suspend fun getIssueDetail(orderId: Int): ApiResult<IssueDetailResponse> {
        return try {
            val response: IssueDetailResponse = httpService.get("issues/$orderId")
            ApiResult.Success(response)
        } catch (e: HttpException) {
            ApiResult.Error(e.responseBody, e.statusCode)
        } catch (e: Exception) {
            ApiResult.Error(e.message ?: "获取发料单详情失败")
        }
    }

    open suspend fun calculate(
        orderId: Int,
        strategy: String = "config"
    ): ApiResult<CalculateResponse> {
        return try {
            val body = CalculateRequest(strategy = strategy)
            val response: CalculateResponse = httpService.post("issues/$orderId/calculate", body)
            ApiResult.Success(response)
        } catch (e: HttpException) {
            ApiResult.Error(e.responseBody, e.statusCode)
        } catch (e: Exception) {
            ApiResult.Error(e.message ?: "计算 FIFO 分配失败")
        }
    }

    open suspend fun assign(orderId: Int): ApiResult<AssignResponse> {
        return try {
            val response: AssignResponse = httpService.postEmpty("issues/$orderId/assign")
            ApiResult.Success(response)
        } catch (e: HttpException) {
            ApiResult.Error(e.responseBody, e.statusCode)
        } catch (e: Exception) {
            ApiResult.Error(e.message ?: "下发亮灯指令失败")
        }
    }

    open suspend fun confirmPick(
        orderId: Int,
        barcode: String,
        palletId: Int,
        operator: String
    ): ApiResult<ConfirmPickResponse> {
        return try {
            val body = ConfirmPickRequest(barcode = barcode, palletId = palletId, operator = operator)
            val response: ConfirmPickResponse = httpService.post("issues/$orderId/confirm-pick", body)
            ApiResult.Success(response)
        } catch (e: HttpException) {
            ApiResult.Error(e.responseBody, e.statusCode)
        } catch (e: Exception) {
            ApiResult.Error(e.message ?: "确认拣料失败")
        }
    }
}
