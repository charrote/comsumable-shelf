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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.DialogProperties
import androidx.hilt.navigation.compose.hiltViewModel
import com.smes.pda.data.model.ReceiptScanResponse
import com.smes.pda.ui.viewmodel.InboundViewModel

private val Primary = Color(0xFF0066CC)
private val Success = Color(0xFF00AA55)
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
    var manualCode by remember { mutableStateOf("") }
    var manualName by remember { mutableStateOf("") }
    var manualSpec by remember { mutableStateOf("") }
    var manualQty by remember { mutableStateOf("1") }
    var manualBatch by remember { mutableStateOf("") }
    var manualDateCode by remember { mutableStateOf("") }

    // ── 弹框是否可见：有条码等待确认 ──
    val showConfirmDialog = uiState.lastBarcode.isNotEmpty()

    // 成功确认后清除 quantityInput，准备下次扫码
    LaunchedEffect(uiState.lastConfirmResult) {
        if (uiState.lastConfirmResult != null) {
            quantityInput = ""
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
                    // ── 模式切换 ──
                    item {
                        ModeToggle(
                            manualMode = uiState.manualMode,
                            onToggle = { viewModel.toggleManualMode(it) }
                        )
                    }

                    if (!uiState.manualMode) {
                        // ── 扫码模式 ──
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
                                isLoading = false
                            )
                        }
                    } else {
                        // ── 手工录入模式 ──
                        item {
                            ManualEntryArea(
                                materialCode = manualCode,
                                materialName = manualName,
                                spec = manualSpec,
                                qty = manualQty,
                                batch = manualBatch,
                                dateCode = manualDateCode,
                                onCodeChange = { manualCode = it },
                                onNameChange = { manualName = it },
                                onSpecChange = { manualSpec = it },
                                onQtyChange = { manualQty = it },
                                onBatchChange = { manualBatch = it },
                                onDateCodeChange = { manualDateCode = it },
                                onSubmit = {
                                    viewModel.updateManualField(
                                        materialCode = manualCode.trim(),
                                        materialName = manualName.trim(),
                                        spec = manualSpec.trim().ifBlank { null },
                                        qty = manualQty,
                                        batch = manualBatch.trim().ifBlank { null },
                                        dateCode = manualDateCode.trim().ifBlank { null },
                                    )
                                    viewModel.submitManualEntry()
                                },
                                isLoading = uiState.isLoading
                            )
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

    // ── 条形码确认弹框（扫码后立即弹出，不调 API） ──
    if (showConfirmDialog) {
        ScanConfirmDialog(
            barcode = uiState.lastBarcode,
            quantityInput = quantityInput,
            isLoading = uiState.isLoading,
            errorMessage = uiState.confirmError,
            onQuantityChange = { quantityInput = it },
            onConfirm = {
                val qty = quantityInput.toDoubleOrNull()
                if (qty != null && qty > 0) {
                    viewModel.confirmScan(qty)
                }
            },
            onCancel = {
                viewModel.cancelConfirm()
                quantityInput = ""
            }
        )
    }
}

@Composable
private fun ModeToggle(manualMode: Boolean, onToggle: (Boolean) -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBg),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(4.dp),
            horizontalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            // 扫码按钮
            Button(
                onClick = { onToggle(false) },
                modifier = Modifier.weight(1f),
                shape = RoundedCornerShape(6.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (!manualMode) Primary else Color(0xFFE8ECF0),
                    contentColor = if (!manualMode) Color.White else TextSecondary,
                ),
                contentPadding = PaddingValues(vertical = 8.dp)
            ) {
                Text(
                    text = "\uD83D\uDCF7 扫码",
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Bold
                )
            }
            // 手工按钮
            Button(
                onClick = { onToggle(true) },
                modifier = Modifier.weight(1f),
                shape = RoundedCornerShape(6.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (manualMode) Primary else Color(0xFFE8ECF0),
                    contentColor = if (manualMode) Color.White else TextSecondary,
                ),
                contentPadding = PaddingValues(vertical = 8.dp)
            ) {
                Text(
                    text = "\u270F\uFE0F 手工",
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

@Composable
private fun ManualEntryArea(
    materialCode: String,
    materialName: String,
    spec: String,
    qty: String,
    batch: String,
    dateCode: String,
    onCodeChange: (String) -> Unit,
    onNameChange: (String) -> Unit,
    onSpecChange: (String) -> Unit,
    onQtyChange: (String) -> Unit,
    onBatchChange: (String) -> Unit,
    onDateCodeChange: (String) -> Unit,
    onSubmit: () -> Unit,
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
            Text(
                text = "\u270F\uFE0F 手工录入",
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold,
                color = TextPrimary,
                modifier = Modifier.padding(bottom = 12.dp)
            )

            // 物料编码（必填）
            FormField(
                label = "物料编码 *",
                value = materialCode,
                onValueChange = onCodeChange,
                placeholder = "必填：输入物料编码"
            )

            // 物料名称
            FormField(
                label = "物料名称",
                value = materialName,
                onValueChange = onNameChange,
                placeholder = "输入物料名称"
            )

            // 规格
            FormField(
                label = "规格",
                value = spec,
                onValueChange = onSpecChange,
                placeholder = "如：0805"
            )

            // 数量（必填）
            FormField(
                label = "数量 *",
                value = qty,
                onValueChange = onQtyChange,
                placeholder = "1",
                keyboardType = androidx.compose.ui.text.input.KeyboardType.Number
            )

            // 批次号
            FormField(
                label = "批次号",
                value = batch,
                onValueChange = onBatchChange,
                placeholder = "选填"
            )

            // 生产周期
            FormField(
                label = "生产周期",
                value = dateCode,
                onValueChange = onDateCodeChange,
                placeholder = "如：2401"
            )

            Spacer(modifier = Modifier.height(12.dp))

            Button(
                onClick = onSubmit,
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 52.dp),
                enabled = materialCode.isNotBlank() && !isLoading,
                shape = RoundedCornerShape(8.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Success)
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(24.dp),
                        strokeWidth = 3.dp,
                        color = Color.White
                    )
                } else {
                    Text(
                        text = "确认手工入库",
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}

@Composable
private fun FormField(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    placeholder: String,
    keyboardType: androidx.compose.ui.text.input.KeyboardType = androidx.compose.ui.text.input.KeyboardType.Text,
) {
    Text(
        text = label,
        fontSize = 14.sp,
        color = TextSecondary,
        fontWeight = FontWeight.SemiBold,
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 6.dp, bottom = 2.dp)
    )
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp),
        placeholder = {
            Text(placeholder, fontSize = 15.sp, color = TextSecondary)
        },
        singleLine = true,
        keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = keyboardType),
        textStyle = LocalTextStyle.current.copy(fontSize = 16.sp, color = TextPrimary),
        shape = RoundedCornerShape(8.dp)
    )
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
private fun ScanConfirmDialog(
    barcode: String,
    quantityInput: String,
    isLoading: Boolean = false,
    errorMessage: String? = null,
    onQuantityChange: (String) -> Unit,
    onConfirm: () -> Unit,
    onCancel: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onCancel,
        properties = DialogProperties(
            dismissOnBackPress = false,
            dismissOnClickOutside = false,
            usePlatformDefaultWidth = false
        ),
        title = {
            Text(
                text = "\u2705 确认入库",
                fontSize = 22.sp,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )
        },
        text = {
            Column(modifier = Modifier.padding(horizontal = 4.dp)) {
                // 条形码（用户在扫码枪/PDA 上扫到的原始值）
                Text(
                    text = "条形码",
                    fontSize = 16.sp,
                    color = TextSecondary
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = barcode,
                    fontSize = 24.sp,
                    color = TextPrimary,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(16.dp))

                // 入库数量 - 用户必须在此输入
                Text(
                    text = "入库数量",
                    fontSize = 18.sp,
                    color = TextSecondary,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(6.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = quantityInput,
                        onValueChange = onQuantityChange,
                        modifier = Modifier
                            .weight(1f)
                            .heightIn(min = 56.dp),
                        enabled = !isLoading,
                        placeholder = {
                            Text(
                                "输入数量",
                                fontSize = 18.sp,
                                color = TextSecondary
                            )
                        },
                        singleLine = true,
                        textStyle = LocalTextStyle.current.copy(
                            fontSize = 22.sp,
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

                // 确认失败的错误信息
                errorMessage?.let { msg ->
                    Spacer(modifier = Modifier.height(12.dp))
                    Text(
                        text = msg,
                        fontSize = 16.sp,
                        color = Danger,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
        },
        confirmButton = {
            Button(
                onClick = onConfirm,
                enabled = !isLoading &&
                    quantityInput.toDoubleOrNull() != null &&
                    (quantityInput.toDoubleOrNull() ?: 0.0) > 0,
                shape = RoundedCornerShape(8.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Success)
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        strokeWidth = 2.dp,
                        color = Color.White
                    )
                } else {
                    Text(
                        text = "确认入库",
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        },
        dismissButton = {
            TextButton(
                onClick = onCancel,
                enabled = !isLoading
            ) {
                Text(
                    text = "取消",
                    fontSize = 18.sp,
                    color = TextSecondary
                )
            }
        }
    )
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