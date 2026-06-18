package com.smes.pda.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Assignment
import androidx.compose.material.icons.filled.*
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
import com.smes.pda.data.model.IssueListItem
import com.smes.pda.ui.viewmodel.OutboundViewModel

private val Primary = Color(0xFF0066CC)
private val Success = Color(0xFF00AA55)
private val Warning = Color(0xFFFF9900)
private val Danger = Color(0xFFDD3333)
private val Info = Color(0xFF3399CC)
private val CardBg = Color(0xFFFFFFFF)
private val PageBg = Color(0xFFF5F7FA)
private val TextPrimary = Color(0xFF1A1A1A)
private val TextSecondary = Color(0xFF666666)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OutboundScreen(viewModel: OutboundViewModel = hiltViewModel()) {
    val uiState by viewModel.uiState.collectAsState()
    var barcodeInput by remember { mutableStateOf("") }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = PageBg
    ) {
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .padding(horizontal = 12.dp),
            contentPadding = PaddingValues(vertical = 10.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            // Header
            item {
                Surface(
                    color = CardBg,
                    shadowElevation = 2.dp,
                    shape = RoundedCornerShape(bottomStart = 12.dp, bottomEnd = 12.dp)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 16.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            "BOM 发料",
                            fontSize = 22.sp,
                            fontWeight = FontWeight.Bold,
                            color = TextPrimary
                        )
                        Spacer(modifier = Modifier.weight(1f))
                        FilledTonalButton(
                            onClick = { },
                            shape = RoundedCornerShape(8.dp),
                            colors = ButtonDefaults.filledTonalButtonColors(containerColor = Primary.copy(alpha = 0.12f))
                        ) {
                            Icon(Icons.Default.CloudUpload, contentDescription = null, modifier = Modifier.size(18.dp), tint = Primary)
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("上传", color = Primary, fontSize = 16.sp)
                        }
                    }
                }
            }

            // Operator input (if blank)
            if (uiState.operator.isBlank()) {
                item {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = CardDefaults.cardColors(containerColor = CardBg),
                        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                    ) {
                        var operatorInput by remember { mutableStateOf("") }
                        Column(
                            modifier = Modifier.padding(16.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Text("操作员", fontSize = 22.sp, fontWeight = FontWeight.Bold, color = TextPrimary)
                            Spacer(modifier = Modifier.height(12.dp))
                            OutlinedTextField(
                                value = operatorInput,
                                onValueChange = { operatorInput = it },
                                modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp),
                                placeholder = { Text("请输入操作员姓名", fontSize = 18.sp, color = TextSecondary) },
                                singleLine = true,
                                textStyle = LocalTextStyle.current.copy(fontSize = 18.sp, color = TextPrimary),
                                shape = RoundedCornerShape(8.dp)
                            )
                            Spacer(modifier = Modifier.height(16.dp))
                            Button(
                                onClick = { viewModel.setOperator(operatorInput) },
                                modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp),
                                enabled = operatorInput.isNotBlank(),
                                shape = RoundedCornerShape(8.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = Primary)
                            ) {
                                Text("确认", fontSize = 18.sp, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            }

            // Issue list (when operator set but no issue selected)
            if (uiState.operator.isNotBlank() && uiState.selectedIssue == null) {
                item {
                    Button(
                        onClick = { viewModel.loadPendingIssues() },
                        modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp),
                        enabled = !uiState.isLoading,
                        shape = RoundedCornerShape(8.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Primary)
                    ) {
                        if (uiState.isLoading) {
                            CircularProgressIndicator(modifier = Modifier.size(24.dp), strokeWidth = 3.dp, color = Color.White)
                        } else {
                            Icon(Icons.Default.Refresh, contentDescription = null, modifier = Modifier.size(20.dp))
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("加载待处理出库单", fontSize = 18.sp)
                        }
                    }
                }

                if (uiState.pendingIssues.isEmpty() && !uiState.isLoading) {
                    item {
                        Spacer(modifier = Modifier.height(8.dp))
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                            colors = CardDefaults.cardColors(containerColor = CardBg)
                        ) {
                            Box(modifier = Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) {
                                Text("暂无待处理的出库单", fontSize = 18.sp, color = TextSecondary)
                            }
                        }
                    }
                }

                items(uiState.pendingIssues) { issue ->
                    IssueOrderCard(issue = issue, onClick = { viewModel.selectIssue(issue.id) })
                }
            }

            // Issue detail & picking (when issue selected)
            if (uiState.selectedIssue != null) {
                // Issue info header
                item {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = CardDefaults.cardColors(containerColor = CardBg),
                        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.Description, contentDescription = null, tint = Primary, modifier = Modifier.size(24.dp))
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    uiState.selectedIssue?.orderNo ?: "出库单",
                                    fontSize = 20.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = TextPrimary
                                )
                                Spacer(modifier = Modifier.weight(1f))
                                Surface(
                                    shape = RoundedCornerShape(4.dp),
                                    color = if (uiState.selectedIssue?.status == "pending") Warning.copy(alpha = 0.15f) else Success.copy(alpha = 0.15f)
                                ) {
                                    Text(
                                        uiState.selectedIssue?.status ?: "",
                                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                                        fontSize = 14.sp,
                                        color = if (uiState.selectedIssue?.status == "pending") Warning else Success,
                                        fontWeight = FontWeight.Medium
                                    )
                                }
                            }
                            uiState.selectedIssue?.let { issue ->
                                Spacer(modifier = Modifier.height(8.dp))
                                Text("物料项: ${issue.details.size}", fontSize = 16.sp, color = TextSecondary)
                            }
                        }
                    }
                }

                // Calculate & Assign buttons
                item {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Button(
                            onClick = { viewModel.calculate() },
                            modifier = Modifier.weight(1f).heightIn(min = 48.dp),
                            enabled = !uiState.isLoading,
                            shape = RoundedCornerShape(8.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = Info)
                        ) {
                            if (uiState.isLoading && uiState.calcResult == null) {
                                CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp, color = Color.White)
                            } else {
                                Icon(Icons.Default.Calculate, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("计算", fontSize = 16.sp)
                            }
                        }
                        Button(
                            onClick = { viewModel.assign() },
                            modifier = Modifier.weight(1f).heightIn(min = 48.dp),
                            enabled = !uiState.isLoading && uiState.calcResult != null,
                            shape = RoundedCornerShape(8.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = Primary)
                        ) {
                            if (uiState.isLoading && uiState.assignResult == null) {
                                CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp, color = Color.White)
                            } else {
                                Icon(Icons.Default.Lightbulb, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("亮灯", fontSize = 16.sp)
                            }
                        }
                    }
                }

                // Scan & confirm pick
                if (uiState.calcResult != null) {
                    item {
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                            colors = CardDefaults.cardColors(containerColor = CardBg),
                            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text("扫描条码确认拣料", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = TextPrimary)
                                Spacer(modifier = Modifier.height(10.dp))
                                OutlinedTextField(
                                    value = barcodeInput,
                                    onValueChange = { barcodeInput = it },
                                    modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp),
                                    placeholder = { Text("扫描料盘条码", fontSize = 18.sp, color = TextSecondary) },
                                    singleLine = true,
                                    enabled = !uiState.isLoading,
                                    textStyle = LocalTextStyle.current.copy(fontSize = 18.sp, color = TextPrimary),
                                    shape = RoundedCornerShape(8.dp)
                                )
                                Spacer(modifier = Modifier.height(10.dp))
                                Button(
                                    onClick = {
                                        if (barcodeInput.isNotBlank()) {
                                            uiState.currentPickReelId?.let { reelId ->
                                                viewModel.confirmPick(barcodeInput, reelId)
                                            }
                                            barcodeInput = ""
                                        }
                                    },
                                    modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp),
                                    enabled = barcodeInput.isNotBlank() && !uiState.isLoading,
                                    shape = RoundedCornerShape(8.dp),
                                    colors = ButtonDefaults.buttonColors(containerColor = Success)
                                ) {
                                    if (uiState.isLoading) {
                                        CircularProgressIndicator(modifier = Modifier.size(24.dp), strokeWidth = 3.dp, color = Color.White)
                                    } else {
                                        Icon(Icons.Default.QrCodeScanner, contentDescription = null, modifier = Modifier.size(22.dp))
                                        Spacer(modifier = Modifier.width(8.dp))
                                        Text("确认出库", fontSize = 18.sp, fontWeight = FontWeight.Bold)
                                    }
                                }
                            }
                        }
                    }
                }

                // Confirm result
                uiState.confirmResult?.let { result ->
                    item {
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                            colors = CardDefaults.cardColors(
                                containerColor = if (result.allPicked) Success.copy(alpha = 0.08f) else CardBg
                            ),
                            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                        ) {
                            Column(
                                modifier = Modifier.padding(16.dp),
                                horizontalAlignment = Alignment.CenterHorizontally
                            ) {
                                Text(
                                    "状态: ${result.status}",
                                    fontSize = 18.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = if (result.allPicked) Success else TextPrimary
                                )
                                Spacer(modifier = Modifier.height(8.dp))
                                Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) {
                                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                        Text("已拣", fontSize = 14.sp, color = TextSecondary)
                                        Text("${result.pickedQty.toInt()}", fontSize = 24.sp, fontWeight = FontWeight.Bold, color = Primary)
                                    }
                                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                        Text("剩余", fontSize = 14.sp, color = TextSecondary)
                                        Text("${result.remainingQty.toInt()}", fontSize = 24.sp, fontWeight = FontWeight.Bold, color = if (result.allPicked) Success else Warning)
                                    }
                                }
                                if (result.allPicked) {
                                    Spacer(modifier = Modifier.height(8.dp))
                                    Surface(shape = RoundedCornerShape(4.dp), color = Success.copy(alpha = 0.15f)) {
                                        Text("本单已完成!", modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp), fontSize = 16.sp, color = Success, fontWeight = FontWeight.Bold)
                                    }
                                }
                                if (result.clearedLeds.isNotEmpty()) {
                                    Spacer(modifier = Modifier.height(6.dp))
                                    Text("已清除 ${result.clearedLeds.size} 个亮灯", fontSize = 14.sp, color = TextSecondary)
                                }
                            }
                        }
                    }
                }
            }

            // Error
            uiState.error?.let { error ->
                item {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = CardDefaults.cardColors(containerColor = Danger.copy(alpha = 0.08f))
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Default.Error, contentDescription = null, tint = Danger, modifier = Modifier.size(20.dp))
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(error, fontSize = 16.sp, color = Danger, modifier = Modifier.weight(1f))
                            TextButton(onClick = { viewModel.clearError() }) {
                                Text("关闭", fontSize = 14.sp, color = Danger)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun IssueOrderCard(issue: IssueListItem, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBg),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        onClick = onClick
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                Icons.AutoMirrored.Filled.Assignment,
                contentDescription = null,
                tint = Primary,
                modifier = Modifier.size(32.dp)
            )
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(issue.orderNo ?: "#${issue.id}", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = TextPrimary)
                if (issue.bomName != null) {
                    Text("BOM: ${issue.bomName}", fontSize = 16.sp, color = TextSecondary)
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Surface(
                        shape = RoundedCornerShape(4.dp),
                        color = if (issue.status == "pending") Warning.copy(alpha = 0.15f) else Success.copy(alpha = 0.15f)
                    ) {
                        Text(
                            issue.status ?: "",
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            fontSize = 13.sp,
                            color = if (issue.status == "pending") Warning else Success
                        )
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("物料: ${issue.totalMaterials ?: 0}项", fontSize = 14.sp, color = TextSecondary)
                }
            }
            Icon(
                Icons.Default.TouchApp,
                contentDescription = "选择",
                tint = TextSecondary.copy(alpha = 0.5f),
                modifier = Modifier.size(24.dp)
            )
        }
    }
}
