package com.smes.pda.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.smes.pda.data.local.SettingsDataStore
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SettingsUiState(
    val apiUrl: String = "",
    val isSaving: Boolean = false,
    val saveSuccess: Boolean = false
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val settingsDataStore: SettingsDataStore
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    fun loadSettings() {
        viewModelScope.launch {
            val url = settingsDataStore.getApiUrl()
            _uiState.value = _uiState.value.copy(apiUrl = url)
        }
    }

    fun updateApiUrl(url: String) {
        _uiState.value = _uiState.value.copy(
            apiUrl = url,
            saveSuccess = false
        )
    }

    fun saveSettings() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSaving = true, saveSuccess = false)
            settingsDataStore.saveApiUrl(_uiState.value.apiUrl)
            _uiState.value = _uiState.value.copy(isSaving = false, saveSuccess = true)
        }
    }
}
