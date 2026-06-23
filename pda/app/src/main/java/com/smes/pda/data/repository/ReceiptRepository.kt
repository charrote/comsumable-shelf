package com.smes.pda.data.repository

import com.smes.pda.data.api.HttpException
import com.smes.pda.data.api.HttpService
import com.smes.pda.data.model.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
open class ReceiptRepository @Inject constructor(
    private val httpService: HttpService
) {
    open suspend fun createReceipt(operator: String, type: String = "inbound"): ApiResult<ReceiptDetailResponse> {
        return try {
            val body = CreateReceiptRequest(type = if (type == "restock") "restock" else "normal", operator = operator)
            val response: ReceiptDetailResponse = httpService.post("receipts", body)
            ApiResult.Success(response)
        } catch (e: HttpException) {
            ApiResult.Error(e.responseBody, e.statusCode)
        } catch (e: Exception) {
            ApiResult.Error(e.message ?: "创建入库单失败")
        }
    }

    open suspend fun manualEntry(
        receiptId: Int,
        request: ManualEntryRequest,
    ): ApiResult<ReceiptScanResponse> {
        return try {
            val response: ReceiptScanResponse = httpService.post("receipts/$receiptId/manual-entry", request)
            ApiResult.Success(response)
        } catch (e: HttpException) {
            ApiResult.Error(e.responseBody, e.statusCode)
        } catch (e: Exception) {
            ApiResult.Error(e.message ?: "手工录入失败")
        }
    }

    open suspend fun scanInbound(
        receiptId: Int,
        barcode: String,
        operator: String,
        qty: Double? = null
    ): ApiResult<ReceiptScanResponse> {
        return try {
            val body = ScanRequest(barcode = barcode, operator = operator, qty = qty)
            val response: ReceiptScanResponse = httpService.post("receipts/$receiptId/scan", body)
            ApiResult.Success(response)
        } catch (e: HttpException) {
            ApiResult.Error(e.responseBody, e.statusCode)
        } catch (e: Exception) {
            ApiResult.Error(e.message ?: "扫码入库失败")
        }
    }
}
