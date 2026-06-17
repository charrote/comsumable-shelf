package com.smes.pda.data.repository

import com.smes.pda.data.model.ApiResult
import com.smes.pda.data.model.ReceiptDetailResponse
import com.smes.pda.data.model.ReceiptScanResponse
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
open class ReceiptRepository @Inject constructor() {

    open suspend fun createReceipt(operator: String, type: String = "inbound"): ApiResult<ReceiptDetailResponse> {
        return ApiResult.Error("Not implemented")
    }

    open suspend fun scanInbound(
        receiptId: Int,
        barcode: String,
        operator: String
    ): ApiResult<ReceiptScanResponse> {
        return ApiResult.Error("Not implemented")
    }
}
