package com.smes.pda.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavType
import androidx.navigation.compose.*
import com.smes.pda.data.model.ApiResult
import com.smes.pda.data.model.IssueOrderResponse
import com.smes.pda.ui.screens.RestockScreen
import com.smes.pda.ui.theme.ConsumableShelfTheme
import com.smes.pda.ui.viewmodel.*

sealed class Screen(val route: String, val title: String) {
    object Home : Screen("home", "首页")
    object Inbound : Screen("inbound", "扫码入库")
    object Outbound : Screen("outbound", "扫码出库")
    object Restock : Screen("restock", "补料上架")
    object Tracking : Screen("tracking", "库存跟踪")
    object Settings : Screen("settings", "设置")
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            ConsumableShelfTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    Navigation()
                }
            }
        }
    }
}

@Composable
fun Navigation() {
    val navController = rememberNavController()
    var selectedScreen by remember { mutableIntStateOf(0) }
    val screens = listOf(
        Screen.Home, Screen.Inbound, Screen.Outbound,
        Screen.Restock, Screen.Tracking, Screen.Settings
    )

    Scaffold(
        bottomBar = {
            NavigationBar {
                screens.forEachIndexed { index, screen ->
                    NavigationBarItem(
                        icon = {
                            Icon(
                                imageVector = when (screen) {
                                    Screen.Home -> Icons.Default.Home
                                    Screen.Inbound -> Icons.Default.AddCircle
                                    Screen.Outbound -> Icons.Default.RemoveCircle
                                    Screen.Restock -> Icons.Default.Refresh
                                    Screen.Tracking -> Icons.Default.Assignment
                                    Screen.Settings -> Icons.Default.Settings
                                },
                                contentDescription = screen.title
                            )
                        },
                        label = { Text(screen.title) },
                        selected = selectedScreen == index,
                        onClick = {
                            selectedScreen = index
                            navController.navigate(screen.route) {
                                popUpTo(navController.graph.startDestinationId) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    )
                }
            }
        }
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = Screen.Home.route,
            modifier = Modifier.padding(padding)
        ) {
            composable(Screen.Home.route) { HomeScreen() }
            composable(Screen.Inbound.route) { InboundScreen() }
            composable(Screen.Outbound.route) { OutboundScreen() }
            composable(Screen.Restock.route) { RestockScreen() }
            composable(Screen.Tracking.route) { TrackingScreen() }
            composable(Screen.Settings.route) { SettingsScreen() }
        }
    }
}

@Composable
fun HomeScreen() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text("智能物料架 PDA", style = MaterialTheme.typography.headlineMedium)
        Spacer(modifier = Modifier.height(8.dp))
        Text("SMT车间物料管理系统", style = MaterialTheme.typography.bodyLarge)
        Spacer(modifier = Modifier.height(24.dp))
        Text(
            "版本 1.0.0",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
fun InboundScreen(viewModel: InboundViewModel = hiltViewModel()) {
    val uiState by viewModel.uiState.collectAsState()
    var barcodeInput by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        if (uiState.activeReceiptId == null && uiState.operator.isEmpty()) {
            // will init when user enters operator
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text("扫码入库", style = MaterialTheme.typography.headlineSmall)
        Spacer(modifier = Modifier.height(8.dp))

        if (uiState.activeReceiptId == null) {
            OutboundPalletInputCard(
                title = "操作员",
                placeholder = "请输入操作员姓名",
                buttonText = "开始入库",
                onConfirm = { operator ->
                    viewModel.initReceipt(operator)
                }
            )
        } else {
            OutboundPalletInputCard(
                title = "条码/储位输入",
                placeholder = "扫描条码或输入储位",
                buttonText = "确认",
                barcodeValue = barcodeInput,
                onBarcodeChange = { barcodeInput = it },
                isLoading = uiState.isLoading,
                onScan = {
                    if (barcodeInput.isNotBlank()) {
                        viewModel.scanBarcode(barcodeInput)
                        barcodeInput = ""
                    }
                }
            )

            uiState.lastScanResult?.let { result ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 8.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = if (result.status == "ok")
                            MaterialTheme.colorScheme.primaryContainer
                        else
                            MaterialTheme.colorScheme.errorContainer
                    )
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text("结果: ${result.message}")
                        Text("操作: ${result.action}")
                        result.assignedSlot?.let { Text("储位: $it") }
                    }
                }
            }

            uiState.error?.let { error ->
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    error,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall
                )
            }
        }
    }
}

@Composable
fun OutboundScreen(viewModel: OutboundViewModel = hiltViewModel()) {
    val uiState by viewModel.uiState.collectAsState()
    var barcodeInput by remember { mutableStateOf("") }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text("扫码出库", style = MaterialTheme.typography.headlineSmall)
        Spacer(modifier = Modifier.height(8.dp))

        if (uiState.operator.isBlank()) {
            OutboundPalletInputCard(
                title = "操作员",
                placeholder = "请输入操作员姓名",
                buttonText = "确认",
                onConfirm = { viewModel.setOperator(it) }
            )
        } else if (uiState.selectedIssue == null) {
            Button(
                onClick = { viewModel.loadPendingIssues() },
                modifier = Modifier.fillMaxWidth(),
                enabled = !uiState.isLoading
            ) {
                if (uiState.isLoading) {
                    CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                } else {
                    Text("加载待处理出库单")
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            uiState.pendingIssues.forEach { issue ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                    onClick = { viewModel.selectIssue(issue.id) }
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text("单号: ${issue.orderNo}", style = MaterialTheme.typography.titleSmall)
                        Text("状态: ${issue.status}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        } else {
            OutboundPalletInputCard(
                title = "扫描条码确认拣料",
                placeholder = "扫描料盘条码",
                buttonText = "确认出库",
                barcodeValue = barcodeInput,
                onBarcodeChange = { barcodeInput = it },
                isLoading = uiState.isLoading,
                onScan = {
                    if (barcodeInput.isNotBlank()) {
                        uiState.currentPickPalletId?.let { palletId ->
                            viewModel.confirmPick(barcodeInput, palletId)
                        }
                        barcodeInput = ""
                    }
                }
            )

            uiState.confirmResult?.let { result ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 8.dp)
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text("状态: ${result.status}")
                        Text("已拣: ${result.pickedQty}, 剩余: ${result.remainingQty}")
                        if (result.allPicked) {
                            Text("本单已完成!", color = MaterialTheme.colorScheme.primary)
                        }
                    }
                }
            }

            uiState.error?.let { error ->
                Spacer(modifier = Modifier.height(4.dp))
                Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
fun TrackingScreen(viewModel: TrackingViewModel = hiltViewModel()) {
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.loadTracking()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text("库存跟踪", style = MaterialTheme.typography.headlineSmall)
        Spacer(modifier = Modifier.height(8.dp))

        TabRow(selectedTabIndex = uiState.selectedTab) {
            Tab(
                selected = uiState.selectedTab == 0,
                onClick = { viewModel.selectTab(0) },
                text = { Text("跟踪中") }
            )
            Tab(
                selected = uiState.selectedTab == 1,
                onClick = {
                    viewModel.selectTab(1)
                    viewModel.loadOnShelfInventory()
                },
                text = { Text("在库") }
            )
        }

        Spacer(modifier = Modifier.height(8.dp))

        if (uiState.isLoading) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        } else if (uiState.selectedTab == 0) {
            if (uiState.trackingPallets.isEmpty()) {
                Text("暂无跟踪中的物料", color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                uiState.trackingPallets.forEach { pallet ->
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp)
                    ) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Text("料号: ${pallet.materialCode}", style = MaterialTheme.typography.titleSmall)
                            Text("数量: ${pallet.qty}", style = MaterialTheme.typography.bodySmall)
                            Text("状态: ${pallet.status}", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun SettingsScreen() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text("系统设置", style = MaterialTheme.typography.headlineSmall)
        Spacer(modifier = Modifier.height(16.dp))
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("服务器地址", style = MaterialTheme.typography.titleMedium)
                Spacer(modifier = Modifier.height(4.dp))
                Text("http://10.0.2.2:8080/api", style = MaterialTheme.typography.bodyMedium)
            }
        }
        Spacer(modifier = Modifier.height(8.dp))
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("版本", style = MaterialTheme.typography.titleMedium)
                Spacer(modifier = Modifier.height(4.dp))
                Text("1.0.0", style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
fun OutboundPalletInputCard(
    title: String,
    placeholder: String,
    buttonText: String,
    barcodeValue: String = "",
    onBarcodeChange: ((String) -> Unit)? = null,
    isLoading: Boolean = false,
    onScan: (() -> Unit)? = null,
    onConfirm: ((String) -> Unit)? = null
) {
    var inputValue by remember(barcodeValue) { mutableStateOf(barcodeValue) }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(8.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(8.dp))
            OutlinedTextField(
                value = inputValue,
                onValueChange = { newVal ->
                    inputValue = newVal
                    onBarcodeChange?.invoke(newVal)
                },
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text(placeholder) },
                singleLine = true,
                enabled = !isLoading
            )
            Spacer(modifier = Modifier.height(8.dp))
            Button(
                onClick = {
                    when {
                        onScan != null && inputValue.isNotBlank() -> onScan()
                        onConfirm != null && inputValue.isNotBlank() -> onConfirm(inputValue)
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = inputValue.isNotBlank() && !isLoading
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        strokeWidth = 2.dp
                    )
                } else {
                    Text(buttonText)
                }
            }
        }
    }
}
