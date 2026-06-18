package com.smes.pda.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.smes.pda.BuildConfig
import com.smes.pda.ui.viewmodel.HomeViewModel
import com.smes.pda.ui.viewmodel.HomeUiState
import java.text.SimpleDateFormat
import java.util.*

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
fun HomeScreen(viewModel: HomeViewModel = hiltViewModel()) {
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.loadSummary()
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = PageBg
    ) {
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding(),
            contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            // Header
            item { HomeHeader(title = uiState.summary.appName) }

            // Summary cards
            item { SummaryCardsRow(uiState = uiState) }

            // Quick actions
            item { QuickActionsSection() }

            // Pending reminders
            item { PendingRemindersSection(uiState = uiState) }

            // Error
            uiState.error?.let { error ->
                item {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = CardDefaults.cardColors(containerColor = Danger.copy(alpha = 0.08f))
                    ) {
                        Text(
                            error,
                            modifier = Modifier.padding(12.dp),
                            color = Danger,
                            fontSize = 16.sp
                        )
                    }
                }
            }

            // Version
            item {
                Text(
                    "版本 ${BuildConfig.VERSION_NAME}",
                    fontSize = 14.sp,
                    color = TextSecondary,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp),
                    textAlign = androidx.compose.ui.text.style.TextAlign.Center
                )
            }
        }
    }
}

@Composable
private fun HomeHeader(title: String) {
    Surface(
        color = CardBg,
        shadowElevation = 2.dp,
        shape = RoundedCornerShape(bottomStart = 12.dp, bottomEnd = 12.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    title,
                    fontSize = 24.sp,
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    "SMT车间物料管理",
                    fontSize = 14.sp,
                    color = TextSecondary
                )
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    Icons.Default.Person,
                    contentDescription = null,
                    tint = Primary,
                    modifier = Modifier.size(28.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text("操作员", fontSize = 16.sp, color = TextPrimary)
            }
        }
    }
}

@Composable
private fun SummaryCardsRow(uiState: HomeUiState) {
    if (uiState.isLoading) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(100.dp),
            contentAlignment = Alignment.Center
        ) {
            CircularProgressIndicator(color = Primary)
        }
    } else {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            SummaryCard(
                title = "入库",
                value = "${uiState.summary.todayInbound}",
                unit = "盘",
                color = Primary,
                modifier = Modifier.weight(1f)
            )
            SummaryCard(
                title = "出库",
                value = "${uiState.summary.todayOutbound}",
                unit = "盘",
                color = Info,
                modifier = Modifier.weight(1f)
            )
        }
        Spacer(modifier = Modifier.height(2.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            SummaryCard(
                title = "亮灯中",
                value = "${uiState.summary.pendingIssues}",
                unit = "灯组",
                color = Warning,
                modifier = Modifier.weight(1f)
            )
            SummaryCard(
                title = "在架",
                value = "${uiState.summary.onShelfPallets}",
                unit = "盘",
                color = Success,
                modifier = Modifier.weight(1f)
            )
        }
    }
}

@Composable
private fun SummaryCard(
    title: String,
    value: String,
    unit: String,
    color: Color,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBg),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                value,
                fontSize = 28.sp,
                fontWeight = FontWeight.Bold,
                color = color
            )
            Text(
                "$title $unit",
                fontSize = 14.sp,
                color = TextSecondary
            )
        }
    }
}

@Composable
private fun QuickActionsSection() {
    Text(
        "快速操作",
        fontSize = 18.sp,
        fontWeight = FontWeight.Bold,
        color = TextPrimary,
        modifier = Modifier.padding(top = 4.dp, bottom = 4.dp)
    )

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            QuickActionButton(
                icon = Icons.Default.AddCircle,
                label = "扫码入库",
                color = Primary,
                modifier = Modifier.weight(1f),
                onClick = { }
            )
            QuickActionButton(
                icon = Icons.AutoMirrored.Filled.Assignment,
                label = "BOM发料",
                color = Info,
                modifier = Modifier.weight(1f),
                onClick = { }
            )
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            QuickActionButton(
                icon = Icons.Default.Refresh,
                label = "退库点数",
                color = Success,
                modifier = Modifier.weight(1f),
                onClick = { }
            )
            QuickActionButton(
                icon = Icons.Default.Search,
                label = "库存查询",
                color = Warning,
                modifier = Modifier.weight(1f),
                onClick = { }
            )
        }
    }
}

@Composable
private fun QuickActionButton(
    icon: ImageVector,
    label: String,
    color: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Card(
        modifier = modifier
            .heightIn(min = 72.dp)
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.08f)),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                icon,
                contentDescription = label,
                tint = color,
                modifier = Modifier.size(32.dp)
            )
            Spacer(modifier = Modifier.width(12.dp))
            Text(
                label,
                fontSize = 18.sp,
                fontWeight = FontWeight.Medium,
                color = TextPrimary
            )
        }
    }
}

@Composable
private fun PendingRemindersSection(uiState: HomeUiState) {
    val hasPending = uiState.summary.pendingIssues > 0 || uiState.summary.trackingPallets > 0

    Text(
        "待办提醒",
        fontSize = 18.sp,
        fontWeight = FontWeight.Bold,
        color = TextPrimary,
        modifier = Modifier.padding(top = 8.dp, bottom = 4.dp)
    )

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBg),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            if (uiState.summary.pendingIssues > 0) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Default.Lightbulb,
                        contentDescription = null,
                        tint = Warning,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        "${uiState.summary.pendingIssues} 组亮灯等待出库",
                        fontSize = 16.sp,
                        color = TextPrimary
                    )
                }
            }
            if (uiState.summary.trackingPallets > 0) {
                if (uiState.summary.pendingIssues > 0) Spacer(modifier = Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Default.Sync,
                        contentDescription = null,
                        tint = Info,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        "${uiState.summary.trackingPallets} 盘跟踪中料盘",
                        fontSize = 16.sp,
                        color = TextPrimary
                    )
                }
            }
            if (uiState.summary.pendingReceipts > 0) {
                Spacer(modifier = Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Default.Inbox,
                        contentDescription = null,
                        tint = Primary,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        "${uiState.summary.pendingReceipts} 单待入库",
                        fontSize = 16.sp,
                        color = TextPrimary
                    )
                }
            }
            if (!hasPending) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Default.CheckCircle,
                        contentDescription = null,
                        tint = Success,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("暂无待办事项", fontSize = 16.sp, color = TextSecondary)
                }
            }
        }
    }
}
