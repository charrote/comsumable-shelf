package com.smes.pda.data.repository

import com.smes.pda.data.model.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
open class IssueRepository @Inject constructor() {

    open suspend fun listIssues(
        customerId: Int? = null,
        status: String? = null
    ): ApiResult<List<IssueOrderResponse>> {
        return ApiResult.Error("Not implemented")
    }

    open suspend fun getIssueDetail(orderId: Int): ApiResult<IssueOrderResponse> {
        return ApiResult.Error("Not implemented")
    }

    open suspend fun calculate(
        orderId: Int,
        strategy: String = "tail_first"
    ): ApiResult<IssueCalculateResponse> {
        return ApiResult.Error("Not implemented")
    }

    open suspend fun assign(orderId: Int): ApiResult<IssueAssignResponse> {
        return ApiResult.Error("Not implemented")
    }

    open suspend fun confirmPick(
        orderId: Int,
        barcode: String,
        palletId: Int,
        operator: String
    ): ApiResult<IssueConfirmPickResponse> {
        return ApiResult.Error("Not implemented")
    }
}
