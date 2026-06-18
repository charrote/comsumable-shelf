package com.smes.pda.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import dagger.hilt.android.AndroidEntryPoint
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Assignment
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.compose.*
import com.smes.pda.ui.screens.HomeScreen
import com.smes.pda.ui.screens.InboundScreen
import com.smes.pda.ui.screens.OutboundScreen
import com.smes.pda.ui.screens.RestockScreen
import com.smes.pda.ui.screens.TrackingScreen
import com.smes.pda.ui.screens.SettingsScreen
import com.smes.pda.ui.theme.ConsumableShelfTheme

sealed class Screen(val route: String, val title: String) {
    object Home : Screen("home", "首页")
    object Inbound : Screen("inbound", "扫码入库")
    object Outbound : Screen("outbound", "扫码出库")
    object Restock : Screen("restock", "补料上架")
    object Tracking : Screen("tracking", "库存跟踪")
    object Settings : Screen("settings", "设置")
}

@AndroidEntryPoint
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
                                    Screen.Tracking -> Icons.AutoMirrored.Filled.Assignment
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
