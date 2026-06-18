package com.smes.pda.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.smes.pda.data.model.ReceiptScanResponse
import com.smes.pda.ui.viewmodel.InboundViewModel

private val Primary = Color(0xFF0066CC)
private val Success = Color(0xFF00AA55)
private val Warning = Color(0xFFFF9900)
private val Danger = Color(0xFFDD3333)
private val CardBg = Color(0xFFFFFFFF)
private val PageBg = Color(0xFFF5F7FA)
private val TextPrimary = Color(0xFF1A1A1A)
private val TextSecondary = Color(0xFF666666)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InboundScreen(viewModel: InboundViewModel = hiltViewModel()) {
    val uiState by viewModel.uiState.collectAsState()
    var barcodeInput by remember { mutableStateOf("") }
    var quantityInput by remember { mutableStateOf("") }
    var showDuplicateWarning by remember { mutableStateOf(false) }

    LaunchedEffect(uiState.lastScanResult) {
        uiState.lastScanResult?.let { result ->
            if (result.duplicateFlag) {
                showDuplicateWarning = true
            }
        }
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = PageBg
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
        ) {
            Header()

            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
                contentPadding = PaddingValues(vertical = 10.dp)
            ) {
                if (uiState.activeReceiptId == null) {
                    item { OperatorSection(onConfirm = { op -> viewModel.initReceipt(op) }) }
                } else {
                    item {
                        ScanArea(
                            barcode = barcodeInput,
                            onBarcodeChange = { barcodeInput = it },
                            onScan = {
                                if (barcodeInput.isNotBlank()) {
                                    viewModel.scanBarcode(barcodeInput)
                                    barcodeInput = ""
                                }
                            },
                            isLoading = uiState.isLoading
                        )
                    }

                    if (showDuplicateWarning) {
                        uiState.lastScanResult?.let { result ->
                            item { DuplicateWarningCard(result = result, onDismiss = { showDuplicateWarning = false }) }
                        }
                    }

                    uiState.lastScanResult?.let { result ->
                        if (!result.duplicateFlag) {
                            item {
                                MaterialInfoCard(
                                    result = result,
                                    quantityInput = quantityInput,
                                    onQuantityChange = { quantityInput = it }
                                )
                            }
                            item { ConfirmInboundButton() }
                        }
                    }

                    if (uiState.scanHistory.isNotEmpty()) {
                        item { HistoryHeader() }
                        items(uiState.scanHistory.reversed()) { scan ->
                            HistoryItem(scan = scan)
                        }
                    }
                }

                uiState.error?.let { error ->
                    item {
                        ErrorCard(
                            error = error,
                            onDismiss = { viewModel.clearError() }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun Header() {
    Surface(
        color = CardBg,
        shadowElevation = 2.dp
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "\u2190 扫码入库",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )
        }
    }
}

@Composable
private fun OperatorSection(onConfirm: (String) -> Unit) {
    var operator by remember { mutableStateOf("") }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBg),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = "操作员",
                fontSize = 22.sp,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )
            Spacer(modifier = Modifier.height(12.dp))
            OutlinedTextField(
                value = operator,
                onValueChange = { operator = it },
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 56.dp),
                placeholder = {
                    Text("请输入操作员姓名", fontSize = 18.sp, color = TextSecondary)
                },
                singleLine = true,
                textStyle = LocalTextStyle.current.copy(fontSize = 18.sp, color = TextPrimary),
                shape = RoundedCornerShape(8.dp)
            )
            Spacer(modifier = Modifier.height(16.dp))
            Button(
                onClick = { if (operator.isNotBlank()) onConfirm(operator) },
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 52.dp),
                enabled = operator.isNotBlank(),
                shape = RoundedCornerShape(8.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Primary)
            ) {
                Text(
                    "开始入库",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

@Composable
private fun ScanArea(
    barcode: String,
    onBarcodeChange: (String) -> Unit,
    onScan: () -> Unit,
    isLoading: Boolean
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBg),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(120.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(Color(0xFFE8ECF0))
                    .border(2.dp, Primary.copy(alpha = 0.3f), RoundedCornerShape(12.dp)),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        text = "\uD83D\uDCF7",
                        fontSize = 36.sp
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "扫码区域",
                        fontSize = 18.sp,
                        color = TextSecondary,
                        fontWeight = FontWeight.Medium
                    )
                    Text(
                        text = "自动扫码模式",
                        fontSize = 14.sp,
                        color = TextSecondary.copy(alpha = 0.7f)
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            OutlinedTextField(
                value = barcode,
                onValueChange = onBarcodeChange,
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 56.dp),
                placeholder = {
                    Text("扫描或手动输入条码", fontSize = 18.sp, color = TextSecondary)
                },
                singleLine = true,
                enabled = !isLoading,
                textStyle = LocalTextStyle.current.copy(fontSize = 18.sp, color = TextPrimary),
                shape = RoundedCornerShape(8.dp)
            )

            Spacer(modifier = Modifier.height(10.dp))

            Button(
                onClick = onScan,
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 52.dp),
                enabled = barcode.isNotBlank() && !isLoading,
                shape = RoundedCornerShape(8.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Primary)
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(24.dp),
                        strokeWidth = 3.dp,
                        color = Color.White
                    )
                } else {
                    Text(
                        text = "扫描",
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}

@Composable
private fun MaterialInfoCard(
    result: ReceiptScanResponse,
    quantityInput: String,
    onQuantityChange: (String) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBg),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            InfoRow(label = "物料编码", value = result.materialCode ?: "--")
            Spacer(modifier = Modifier.height(8.dp))
            InfoRow(label = "物料名称", value = result.materialName ?: "--")

            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = "入库数量",
                fontSize = 18.sp,
                color = TextSecondary
            )
            Spacer(modifier = Modifier.height(6.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = quantityInput,
                    onValueChange = onQuantityChange,
                    modifier = Modifier
                        .weight(1f)
                        .heightIn(min = 56.dp),
                    placeholder = {
                        Text(
                            if (result.quantity > 0) "${result.quantity.toInt()}" else "输入数量",
                            fontSize = 18.sp,
                            color = TextSecondary
                        )
                    },
                    singleLine = true,
                    textStyle = LocalTextStyle.current.copy(
                        fontSize = 18.sp,
                        color = TextPrimary,
                        fontWeight = FontWeight.Bold
                    ),
                    shape = RoundedCornerShape(8.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "盘",
                    fontSize = 18.sp,
                    color = TextPrimary,
                    fontWeight = FontWeight.Medium
                )
            }

            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = "储位分配",
                fontSize = 18.sp,
                color = TextSecondary
            )
            Spacer(modifier = Modifier.height(6.dp))

            val slotText = result.assignedSlot?.let { "$it" } ?: "自动分配"
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(8.dp))
                    .background(Primary.copy(alpha = 0.08f))
                    .padding(horizontal = 12.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "\uD83D\uDCCD",
                    fontSize = 20.sp
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = slotText,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    color = Primary
                )
            }
        }
    }
}

@Composable
private fun ConfirmInboundButton() {
    Button(
        onClick = { },
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 56.dp),
        shape = RoundedCornerShape(12.dp),
        colors = ButtonDefaults.buttonColors(containerColor = Success)
    ) {
        Text(
            text = "\u2705 确认入库",
            fontSize = 20.sp,
            fontWeight = FontWeight.Bold
        )
    }
}

@Composable
private fun DuplicateWarningCard(
    result: ReceiptScanResponse,
    onDismiss: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = Warning.copy(alpha = 0.12f)),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = "\u26A0\uFE0F 检测到重复扫码",
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                color = Danger
            )
            Spacer(modifier = Modifier.height(10.dp))
            Text(
                text = "物料: ${result.materialCode ?: "--"}  ${result.materialName ?: ""}",
                fontSize = 18.sp,
                color = TextPrimary
            )
            result.warning?.let {
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = it,
                    fontSize = 18.sp,
                    color = Danger
                )
            }
            result.assignedSlot?.let { slot ->
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = "已存在库存: 储位 $slot",
                    fontSize = 18.sp,
                    color = TextPrimary
                )
            }
            Spacer(modifier = Modifier.height(14.dp))
            OutlinedButton(
                onClick = {
                    onDismiss()
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 52.dp),
                shape = RoundedCornerShape(8.dp),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = Primary)
            ) {
                Text(
                    text = "\uD83D\uDD19 重新扫码",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

@Composable
private fun HistoryHeader() {
    Text(
        text = "最近入库记录",
        fontSize = 18.sp,
        fontWeight = FontWeight.Bold,
        color = TextPrimary,
        modifier = Modifier.padding(top = 4.dp, bottom = 2.dp)
    )
}

@Composable
private fun HistoryItem(scan: ReceiptScanResponse) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = CardBg),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .clip(CircleShape)
                    .background(
                        if (scan.duplicateFlag) Danger else Success
                    )
            )
            Spacer(modifier = Modifier.width(10.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "${scan.materialCode ?: "--"} \u00D7 ${scan.quantity.toInt()} @ \u50A8\u4F4D ${scan.assignedSlot ?: "--"}",
                    fontSize = 16.sp,
                    color = TextPrimary
                )
                scan.message?.let {
                    Text(
                        text = it,
                        fontSize = 14.sp,
                        color = TextSecondary
                    )
                }
            }
        }
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = "$label: ",
            fontSize = 18.sp,
            color = TextSecondary
        )
        Text(
            text = value,
            fontSize = 18.sp,
            fontWeight = FontWeight.Bold,
            color = TextPrimary
        )
    }
}

@Composable
private fun ErrorCard(error: String, onDismiss: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = Danger.copy(alpha = 0.08f))
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = error,
                fontSize = 16.sp,
                color = Danger,
                modifier = Modifier.weight(1f)
            )
            TextButton(onClick = onDismiss) {
                Text("\u2716", fontSize = 18.sp, color = Danger)
            }
        }
    }
}