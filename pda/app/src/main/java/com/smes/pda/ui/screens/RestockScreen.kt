package com.smes.pda.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.smes.pda.ui.viewmodel.RestockViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RestockScreen(viewModel: RestockViewModel = hiltViewModel()) {
    val uiState by viewModel.uiState.collectAsState()
    var barcodeInput by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        if (uiState.activeReceiptId == null && uiState.operator.isNotEmpty()) {
            viewModel.initRestock(uiState.operator)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text("补料上架", style = MaterialTheme.typography.headlineSmall)
        Spacer(modifier = Modifier.height(8.dp))

        if (uiState.activeReceiptId == null) {
            OperatorInputCard(
                onConfirm = { operator ->
                    viewModel.initRestock(operator)
                }
            )
        } else {
            ScanInputCard(
                barcode = barcodeInput,
                onBarcodeChange = { barcodeInput = it },
                onScan = {
                    if (barcodeInput.isNotBlank()) {
                        viewModel.scanBarcode(barcodeInput)
                        barcodeInput = ""
                    }
                },
                isLoading = uiState.isLoading,
                label = "扫描补料条码"
            )

            uiState.lastScanResult?.let { result ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 8.dp)
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text(
                            "结果: ${result.message}",
                            style = MaterialTheme.typography.bodyMedium
                        )
                        Text(
                            "操作: ${result.action}",
                            style = MaterialTheme.typography.bodySmall
                        )
                        result.assignedSlot?.let {
                            Text("分配储位: $it")
                        }
                    }
                }
            }

            if (uiState.scanHistory.isNotEmpty()) {
                Spacer(modifier = Modifier.height(12.dp))
                Text("扫描记录", style = MaterialTheme.typography.titleSmall)
                LazyColumn(modifier = Modifier.fillMaxSize()) {
                    items(uiState.scanHistory.reversed()) { scan ->
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 4.dp)
                        ) {
                            Text(
                                scan.message ?: "",
                                modifier = Modifier.padding(8.dp),
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                    }
                }
            }
        }

        uiState.error?.let { error ->
            Spacer(modifier = Modifier.height(8.dp))
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.errorContainer
                ),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    error,
                    modifier = Modifier.padding(12.dp),
                    color = MaterialTheme.colorScheme.onErrorContainer
                )
            }
        }
    }
}

@Composable
fun OperatorInputCard(onConfirm: (String) -> Unit) {
    var operator by remember { mutableStateOf("") }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text("操作员", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = operator,
                onValueChange = { operator = it },
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("请输入操作员姓名") },
                singleLine = true
            )
            Spacer(modifier = Modifier.height(8.dp))
            Button(
                onClick = { if (operator.isNotBlank()) onConfirm(operator) },
                modifier = Modifier.fillMaxWidth(),
                enabled = operator.isNotBlank()
            ) {
                Text("开始补料上架")
            }
        }
    }
}

@Composable
fun ScanInputCard(
    barcode: String,
    onBarcodeChange: (String) -> Unit,
    onScan: () -> Unit,
    isLoading: Boolean,
    label: String = "扫描条码"
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(label, style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = barcode,
                onValueChange = onBarcodeChange,
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("扫描条码或输入") },
                singleLine = true,
                enabled = !isLoading
            )
            Spacer(modifier = Modifier.height(8.dp))
            Button(
                onClick = onScan,
                modifier = Modifier.fillMaxWidth(),
                enabled = barcode.isNotBlank() && !isLoading
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        strokeWidth = 2.dp
                    )
                } else {
                    Text("确认")
                }
            }
        }
    }
}
