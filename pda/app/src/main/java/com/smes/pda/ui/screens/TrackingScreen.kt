package com.smes.pda.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.smes.pda.data.model.InventoryItem
import com.smes.pda.data.model.TrackingPalletItem
import com.smes.pda.ui.viewmodel.TrackingViewModel

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
fun TrackingScreen(viewModel: TrackingViewModel = hiltViewModel()) {
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.loadTracking()
    }

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
                            "库存查询",
                            fontSize = 22.sp,
                            fontWeight = FontWeight.Bold,
                            color = TextPrimary
                        )
                        Spacer(modifier = Modifier.weight(1f))
                        FilledTonalButton(
                            onClick = {
                                if (uiState.selectedTab == 0) viewModel.loadTracking()
                                else viewModel.loadOnShelfInventory()
                            },
                            shape = RoundedCornerShape(8.dp),
                            enabled = !uiState.isLoading
                        ) {
                            if (uiState.isLoading) {
                                CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                            } else {
                                Icon(Icons.Default.Refresh, contentDescription = "刷新", modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(4.dp))
                                Text("刷新", fontSize = 14.sp)
                            }
                        }
                    }
                }
            }

            // Tab: tracking / on-shelf
            item {
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = CardBg,
                    shadowElevation = 2.dp
                ) {
                    Row(modifier = Modifier.fillMaxWidth()) {
                        TabItem(
                            label = "跟踪中",
                            count = uiState.trackingReels.size,
                            selected = uiState.selectedTab == 0,
                            modifier = Modifier.weight(1f),
                            onClick = {
                                viewModel.selectTab(0)
                            }
                        )
                        TabItem(
                            label = "在库",
                            count = uiState.onShelfInventory?.pallets?.size ?: 0,
                            selected = uiState.selectedTab == 1,
                            modifier = Modifier.weight(1f),
                            onClick = {
                                viewModel.selectTab(1)
                                viewModel.loadOnShelfInventory()
                            }
                        )
                    }
                }
            }

            // Content
            if (uiState.isLoading) {
                item {
                    Box(
                        modifier = Modifier.fillMaxWidth().height(200.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator(color = Primary)
                    }
                }
            } else if (uiState.selectedTab == 0) {
                // Tracking tab
                if (uiState.trackingReels.isEmpty()) {
                    item { EmptyStateCard(message = "暂无跟踪中的物料") }
                } else {
                    items(uiState.trackingReels) { pallet ->
                        TrackingPalletCard(pallet = pallet)
                    }
                }
            } else {
                // On-shelf tab
                val pallets = uiState.onShelfInventory?.pallets ?: emptyList()
                if (pallets.isEmpty()) {
                    item { EmptyStateCard(message = "暂无在库料盘") }
                } else {
                    val summary = uiState.onShelfInventory?.summary
                    if (summary != null) {
                        item { InventorySummaryCard(summary) }
                    }
                    items(pallets) { item ->
                        InventoryItemCard(item = item)
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
private fun TabItem(
    label: String,
    count: Int,
    selected: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Surface(
        modifier = modifier,
        color = if (selected) Primary.copy(alpha = 0.08f) else Color.Transparent,
        shape = RoundedCornerShape(12.dp),
        onClick = onClick
    ) {
        Row(
            modifier = Modifier.padding(vertical = 14.dp, horizontal = 16.dp),
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                label,
                fontSize = 18.sp,
                fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
                color = if (selected) Primary else TextSecondary
            )
            if (count > 0) {
                Spacer(modifier = Modifier.width(8.dp))
                Surface(
                    shape = RoundedCornerShape(10.dp),
                    color = if (selected) Primary else TextSecondary.copy(alpha = 0.2f)
                ) {
                    Text(
                        "$count",
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                        fontSize = 13.sp,
                        color = if (selected) Color.White else TextSecondary,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
        }
    }
}

@Composable
private fun TrackingPalletCard(pallet: TrackingPalletItem) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBg),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(10.dp)
                    .clip(CircleShape)
                    .background(if (pallet.xrMatched) Success else Warning)
            )
            Spacer(modifier = Modifier.width(10.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text("料号: ${pallet.materialCode ?: "--"}", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = TextPrimary)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("数量: ${pallet.quantity?.toInt() ?: 0}", fontSize = 16.sp, color = TextPrimary)
                    Spacer(modifier = Modifier.width(12.dp))
                    Text("状态: ${pallet.status ?: "--"}", fontSize = 16.sp, color = TextSecondary)
                }
                if (pallet.lastOutTime != null) {
                    Text("上次出库: ${pallet.lastOutTime}", fontSize = 14.sp, color = TextSecondary)
                }
            }
            if (pallet.xrMatched) {
                Surface(shape = RoundedCornerShape(4.dp), color = Success.copy(alpha = 0.12f)) {
                    Text("已配对", modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp), fontSize = 13.sp, color = Success, fontWeight = FontWeight.Medium)
                }
            }
        }
    }
}

@Composable
private fun InventorySummaryCard(summary: com.smes.pda.data.model.InventorySummary) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = Primary.copy(alpha = 0.06f))
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(14.dp),
            horizontalArrangement = Arrangement.SpaceEvenly
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("${summary.totalPallets}", fontSize = 22.sp, fontWeight = FontWeight.Bold, color = Primary)
                Text("总料盘", fontSize = 14.sp, color = TextSecondary)
            }
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("${summary.totalQuantity.toInt()}", fontSize = 22.sp, fontWeight = FontWeight.Bold, color = Primary)
                Text("总数量", fontSize = 14.sp, color = TextSecondary)
            }
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("${summary.exhaustedPallets}", fontSize = 22.sp, fontWeight = FontWeight.Bold, color = Danger)
                Text("已耗尽", fontSize = 14.sp, color = TextSecondary)
            }
        }
    }
}

@Composable
private fun InventoryItemCard(item: InventoryItem) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBg),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .clip(CircleShape)
                    .background(
                        when (item.status) {
                            "on_shelf" -> Success
                            "exhausted" -> Danger
                            "tracking" -> Warning
                            else -> TextSecondary
                        }
                    )
            )
            Spacer(modifier = Modifier.width(10.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(item.materialCode ?: "--", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = TextPrimary)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("数量: ${item.quantity?.toInt() ?: 0}", fontSize = 16.sp, color = TextPrimary)
                    if (item.shelfCode != null) {
                        Spacer(modifier = Modifier.width(12.dp))
                        Text("储位: ${item.shelfCode}", fontSize = 16.sp, color = TextSecondary)
                    }
                }
            }
        }
    }
}

@Composable
private fun EmptyStateCard(message: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBg)
    ) {
        Box(
            modifier = Modifier.fillMaxWidth().padding(32.dp),
            contentAlignment = Alignment.Center
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(Icons.Default.Inventory2, contentDescription = null, tint = TextSecondary.copy(alpha = 0.3f), modifier = Modifier.size(48.dp))
                Spacer(modifier = Modifier.height(8.dp))
                Text(message, fontSize = 18.sp, color = TextSecondary)
            }
        }
    }
}
