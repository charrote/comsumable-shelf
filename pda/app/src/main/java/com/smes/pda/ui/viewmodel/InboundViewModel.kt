package com.smes.pda.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.smes.pda.data.model.ApiResult
import com.smes.pda.data.model.ManualEntryRequest
import com.smes.pda.data.model.ReceiptScanResponse
import com.smes.pda.data.repository.ReceiptRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class InboundUiState(
    val isLoading: Boolean = false,
    val activeReceiptId: Int? = null,
    val scanHistory: List<ReceiptScanResponse> = emptyList(),
    val error: String? = null,
    val operator: String = "",
    val lastBarcode: String = "",         // 最近一次扫码的条码，非空时弹框
    val confirmError: String? = null,     // 确认时的错误（显示在弹框内）
    val lastConfirmResult: ReceiptScanResponse? = null,  // 最近一次确认成功的结果
    // ── 手工录入模式 ──
    val manualMode: Boolean = false,
    val manualMaterialCode: String = "",
    val manualMaterialName: String = "",
    val manualSpec: String = "",
    val manualQty: String = "1",
    val manualBatch: String = "",
    val manualDateCode: String = "",
)

@HiltViewModel
class InboundViewModel @Inject constructor(
    private val receiptRepository: ReceiptRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(InboundUiState())
    val uiState: StateFlow<InboundUiState> = _uiState.asStateFlow()

    fun initReceipt(operator: String) {
        viewModelScope.launch {
            try {
                _uiState.value = _uiState.value.copy(isLoading = true, error = null)
                when (val result = receiptRepository.createReceipt(operator)) {
                    is ApiResult.Success -> {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            activeReceiptId = result.data.id,
                            operator = operator
                        )
                    }
                    is ApiResult.Error -> {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            error = result.message
                        )
                    }
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "异常: ${e.message ?: e.javaClass.simpleName}"
                )
            }
        }
    }

    /**
     * 扫码：仅存条码，不调 API。
     * 等用户在弹框里确认数量后，才调用 [confirmScan] 真正落库。
     */
    fun scanBarcode(barcode: String) {
        if (barcode.isBlank()) return
        _uiState.value = _uiState.value.copy(
            lastBarcode = barcode,
            confirmError = null
        )
    }

    /**
     * 用户确认数量后，唯一一次调 API 落库。
     */
    fun confirmScan(quantity: Double) {
        val receiptId = _uiState.value.activeReceiptId ?: return
        val barcode = _uiState.value.lastBarcode
        val operator = _uiState.value.operator
        if (barcode.isBlank() || operator.isBlank()) return

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, confirmError = null)
            when (val result = receiptRepository.scanInbound(receiptId, barcode, operator, qty = quantity)) {
                is ApiResult.Success -> {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        lastBarcode = "",
                        confirmError = null,
                        lastConfirmResult = result.data,
                        scanHistory = _uiState.value.scanHistory + result.data
                    )
                }
                is ApiResult.Error -> {
                    // 确认失败：弹框保持打开，显示错误，用户可重试
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        confirmError = result.message
                    )
                }
            }
        }
    }

    // ── 手工录入模式切换 ──
    fun toggleManualMode(enabled: Boolean) {
        _uiState.value = _uiState.value.copy(
            manualMode = enabled,
            lastBarcode = "",  // 退出扫码确认弹框
        )
    }

    // ── 更新手工录入字段 ──
    fun updateManualField(
        materialCode: String? = null,
        materialName: String? = null,
        spec: String? = null,
        qty: String? = null,
        batch: String? = null,
        dateCode: String? = null,
    ) {
        _uiState.value = _uiState.value.copy(
            manualMaterialCode = materialCode ?: _uiState.value.manualMaterialCode,
            manualMaterialName = materialName ?: _uiState.value.manualMaterialName,
            manualSpec = spec ?: _uiState.value.manualSpec,
            manualQty = qty ?: _uiState.value.manualQty,
            manualBatch = batch ?: _uiState.value.manualBatch,
            manualDateCode = dateCode ?: _uiState.value.manualDateCode,
        )
    }

    // ── 手工录入提交 ──
    fun submitManualEntry() {
        val state = _uiState.value
        val receiptId = state.activeReceiptId ?: return
        val operator = state.operator
        val code = state.manualMaterialCode.trim()
        if (code.isBlank()) {
            _uiState.value = state.copy(error = "请输入物料编码")
            return
        }
        val qty = state.manualQty.toDoubleOrNull()
        if (qty == null || qty <= 0) {
            _uiState.value = state.copy(error = "请输入有效数量")
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val request = ManualEntryRequest(
                operator = operator,
                materialCode = code,
                materialName = state.manualMaterialName.trim(),
                spec = state.manualSpec.trim().ifBlank { null },
                quantity = qty,
                batchNo = state.manualBatch.trim().ifBlank { null },
                dateCode = state.manualDateCode.trim().ifBlank { null },
            )
            when (val result = receiptRepository.manualEntry(receiptId, request)) {
                is ApiResult.Success -> {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        manualMaterialCode = "",
                        manualMaterialName = "",
                        manualSpec = "",
                        manualQty = "1",
                        manualBatch = "",
                        manualDateCode = "",
                        lastConfirmResult = result.data,
                        scanHistory = _uiState.value.scanHistory + result.data,
                        error = null,
                    )
                }
                is ApiResult.Error -> {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = result.message,
                    )
                }
            }
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    /** 用户取消弹框 */
    fun cancelConfirm() {
        _uiState.value = _uiState.value.copy(
            lastBarcode = "",
            confirmError = null
        )
    }
}
