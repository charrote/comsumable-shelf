package com.smes.pda.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.smes.pda.data.model.*
import com.smes.pda.data.repository.IssueRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class OutboundUiState(
    val isLoading: Boolean = false,
    val pendingIssues: List<IssueListItem> = emptyList(),
    val selectedIssue: IssueDetailResponse? = null,
    val calcResult: CalculateResponse? = null,
    val assignResult: AssignResponse? = null,
    val confirmResult: ConfirmPickResponse? = null,
    val currentPickReelId: Int? = null,
    val error: String? = null,
    val operator: String = ""
)

@HiltViewModel
class OutboundViewModel @Inject constructor(
    private val issueRepository: IssueRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(OutboundUiState())
    val uiState: StateFlow<OutboundUiState> = _uiState.asStateFlow()

    fun loadPendingIssues(customerId: Int? = null) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            when (val result = issueRepository.listIssues(customerId, "pending")) {
                is ApiResult.Success -> {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        pendingIssues = result.data
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

    fun selectIssue(orderId: Int) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            when (val result = issueRepository.getIssueDetail(orderId)) {
                is ApiResult.Success -> {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        selectedIssue = result.data
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

    fun calculate(strategy: String = "tail_first") {
        val orderId = _uiState.value.selectedIssue?.id ?: return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            when (val result = issueRepository.calculate(orderId, strategy)) {
                is ApiResult.Success -> {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        calcResult = result.data
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

    fun assign() {
        val orderId = _uiState.value.selectedIssue?.id ?: return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            when (val result = issueRepository.assign(orderId)) {
                is ApiResult.Success -> {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        assignResult = result.data
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

    fun confirmPick(barcode: String, reelId: Int) {
        val orderId = _uiState.value.selectedIssue?.id ?: return
        val operator = _uiState.value.operator
        if (operator.isBlank()) return

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            when (val result = issueRepository.confirmPick(orderId, barcode, reelId, operator)) {
                is ApiResult.Success -> {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        confirmResult = result.data
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

    fun setOperator(operator: String) {
        _uiState.value = _uiState.value.copy(operator = operator)
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }
}
