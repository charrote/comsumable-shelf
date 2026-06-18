import React, { useState, useEffect, useCallback } from 'react'
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, RefreshControl,
} from 'react-native'
import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import type { RootStackParamList } from '../App'
import { useAuthStore } from '../store/authStore'
import { getDashboardSummaryApi } from '../api'
import type { DashboardSummary } from '../types/api'

type Nav = NativeStackNavigationProp<RootStackParamList>

const Colors = {
  primary: '#0066CC',
  success: '#00AA55',
  warning: '#FF9900',
  danger: '#DD3333',
  info: '#3399CC',
  card: '#FFFFFF',
  bg: '#F5F7FA',
  text: '#1A1A1A',
  textSecondary: '#666666',
}

export default function HomeScreen() {
  const navigation = useNavigation<Nav>()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const loadSummary = useCallback(async () => {
    try {
      const data = await getDashboardSummaryApi()
      setSummary(data)
    } catch {
      // Fallback defaults
      setSummary({ app_name: '智能物料管理系统',
        today_inbound: 0, today_outbound: 0, pending_issues: 0,
        on_shelf_pallets: 0, tracking_pallets: 0, pending_receipts: 0,
      })
    }
  }, [])

  useEffect(() => {
    setIsLoading(true)
    loadSummary().finally(() => setIsLoading(false))
  }, [loadSummary])

  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await loadSummary()
    setRefreshing(false)
  }, [loadSummary])

  const quickActions = [
    { key: 'Inbound', label: '收料入库', icon: '📦', color: Colors.primary },
    { key: 'Shelving', label: '料盘上架', icon: '📤', color: Colors.success },
    { key: 'Outbound', label: '扫码出库', icon: '📄', color: Colors.info },
    { key: 'Tracking', label: '库存跟踪', icon: '🔍', color: Colors.warning },
    { key: 'Settings', label: '设置', icon: '⚙️', color: Colors.textSecondary },
  ] as const

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>{summary?.app_name || '智能物料管理系统'}</Text>
          <Text style={styles.headerSub}>SMT 车间物料管理</Text>
        </View>
        <View style={styles.headerRight}>
          <Text style={styles.userName}>{user?.username || '操作员'}</Text>
          <TouchableOpacity onPress={logout} style={styles.logoutBtn}>
            <Text style={styles.logoutText}>退出</Text>
          </TouchableOpacity>
        </View>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[Colors.primary]} />
        }
      >
        {/* Summary Cards */}
        {isLoading && !summary ? (
          <ActivityIndicator style={{ marginTop: 24 }} size="large" color={Colors.primary} />
        ) : (
          <View style={styles.summaryGrid}>
            <View style={styles.summaryRow}>
              <SummaryCard title="今日入库" value={summary?.today_inbound ?? 0} unit="盘" color={Colors.primary} />
              <SummaryCard title="今日出库" value={summary?.today_outbound ?? 0} unit="盘" color={Colors.info} />
            </View>
            <View style={styles.summaryRow}>
              <SummaryCard title="亮灯出库" value={summary?.pending_issues ?? 0} unit="单" color={Colors.warning} />
              <SummaryCard title="在库料盘" value={summary?.on_shelf_pallets ?? 0} unit="盘" color={Colors.success} />
            </View>
          </View>
        )}

        {/* Quick Actions */}
        <Text style={styles.sectionTitle}>快速操作</Text>
        <View style={styles.actionGrid}>
          {quickActions.map((action) => (
            <TouchableOpacity
              key={action.key}
              style={[styles.actionCard, { borderLeftColor: action.color }]}
              onPress={() => navigation.navigate(action.key as any)}
            >
              <Text style={styles.actionIcon}>{action.icon}</Text>
              <Text style={[styles.actionLabel, { color: action.color }]}>{action.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Pending Reminders */}
        <Text style={styles.sectionTitle}>待办提醒</Text>
        <View style={styles.reminderCard}>
          {(summary?.pending_issues ?? 0) > 0 && (
            <View style={styles.reminderRow}>
              <Text style={styles.reminderDot}>⚡</Text>
              <Text style={styles.reminderText}>
                {summary?.pending_issues} 组亮灯等待出库
              </Text>
            </View>
          )}
          {(summary?.tracking_pallets ?? 0) > 0 && (
            <View style={styles.reminderRow}>
              <Text style={styles.reminderDot}>🔄</Text>
              <Text style={styles.reminderText}>
                {summary?.tracking_pallets} 盘退库待处理
              </Text>
            </View>
          )}
          {(summary?.pending_receipts ?? 0) > 0 && (
            <View style={styles.reminderRow}>
              <Text style={styles.reminderDot}>📦</Text>
              <Text style={styles.reminderText}>
                {summary?.pending_receipts} 单待入库确认
              </Text>
            </View>
          )}
          {(summary?.pending_issues ?? 0) === 0 &&
           (summary?.tracking_pallets ?? 0) === 0 &&
           (summary?.pending_receipts ?? 0) === 0 && (
            <View style={styles.reminderRow}>
              <Text style={styles.reminderDot}>✅</Text>
              <Text style={styles.reminderText}>暂无待办事项</Text>
            </View>
          )}
        </View>

        <Text style={styles.version}>版本 1.0.0</Text>
      </ScrollView>
    </View>
  )
}

function SummaryCard({ title, value, unit, color }: {
  title: string; value: number; unit: string; color: string
}) {
  return (
    <View style={[styles.summaryCard, { borderTopColor: color }]}>
      <Text style={[styles.summaryValue, { color }]}>{value}</Text>
      <Text style={styles.summaryUnit}>{title}</Text>
      <Text style={styles.summaryUnitSmall}>{unit}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: Colors.primary, paddingHorizontal: 16, paddingTop: 50, paddingBottom: 16,
  },
  headerTitle: { fontSize: 22, fontWeight: 'bold', color: '#fff' },
  headerSub: { fontSize: 13, color: 'rgba(255,255,255,0.8)', marginTop: 2 },
  headerRight: { alignItems: 'flex-end' },
  userName: { fontSize: 14, color: '#fff', fontWeight: '600' },
  logoutBtn: { marginTop: 4, paddingHorizontal: 10, paddingVertical: 3, backgroundColor: 'rgba(255,255,255,0.2)', borderRadius: 4 },
  logoutText: { fontSize: 12, color: '#fff' },
  scrollView: { flex: 1 },
  scrollContent: { padding: 12, paddingBottom: 32 },
  summaryGrid: { gap: 8, marginBottom: 4 },
  summaryRow: { flexDirection: 'row', gap: 8 },
  summaryCard: {
    flex: 1, backgroundColor: Colors.card, borderRadius: 12, padding: 12,
    alignItems: 'center', borderTopWidth: 3, elevation: 2, shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 4,
  },
  summaryValue: { fontSize: 28, fontWeight: 'bold' },
  summaryUnit: { fontSize: 14, color: Colors.text, marginTop: 2 },
  summaryUnitSmall: { fontSize: 12, color: Colors.textSecondary },
  sectionTitle: {
    fontSize: 18, fontWeight: 'bold', color: Colors.text,
    marginTop: 16, marginBottom: 8,
  },
  actionGrid: { gap: 8 },
  actionCard: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.card,
    borderRadius: 12, padding: 16, borderLeftWidth: 4, elevation: 1,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.08, shadowRadius: 3,
  },
  actionIcon: { fontSize: 28, marginRight: 14 },
  actionLabel: { fontSize: 18, fontWeight: '600' },
  reminderCard: {
    backgroundColor: Colors.card, borderRadius: 12, padding: 16, elevation: 1,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.08, shadowRadius: 3,
  },
  reminderRow: { flexDirection: 'row', alignItems: 'center', marginVertical: 4 },
  reminderDot: { fontSize: 18, marginRight: 10 },
  reminderText: { fontSize: 16, color: Colors.text },
  version: { textAlign: 'center', fontSize: 13, color: Colors.textSecondary, marginTop: 20 },
})
