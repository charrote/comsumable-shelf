package com.smes.pda.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.smes.pda.data.model.ApiResult
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
    val lastScanResult: ReceiptScanResponse? = null,
    val scanHistory: List<ReceiptScanResponse> = emptyList(),
    val error: String? = null,
    val operator: String = ""
)

@HiltViewModel
class InboundViewModel @Inject constructor(
    private val receiptRepository: ReceiptRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(InboundUiState())
    val uiState: StateFlow<InboundUiState> = _uiState.asStateFlow()

    fun initReceipt(operator: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
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
        }
    }

    fun scanBarcode(barcode: String) {
        if (barcode.isBlank()) return
        val receiptId = _uiState.value.activeReceiptId ?: return
        val operator = _uiState.value.operator
        if (operator.isBlank()) return

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            when (val result = receiptRepository.scanInbound(receiptId, barcode, operator)) {
                is ApiResult.Success -> {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        lastScanResult = result.data,
                        scanHistory = _uiState.value.scanHistory + result.data
                    )
                }
                is ApiResult.Error -> {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = result.message
                    )
                }
            }
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun clearLastScan() {
        _uiState.value = _uiState.value.copy(lastScanResult = null)
    }
}
