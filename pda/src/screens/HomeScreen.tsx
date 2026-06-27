import React, { useState, useEffect, useCallback } from 'react'
import {
  View, Text, StyleSheet, ScrollView,
  ActivityIndicator, RefreshControl,
} from 'react-native'
import { getDashboardSummaryApi } from '../api'
import type { DashboardSummary } from '../types/api'

const Colors = {
  primary: '#0066CC',
  success: '#00AA55',
  warning: '#FF9900',
  info: '#3399CC',
  card: '#FFFFFF',
  bg: '#F5F7FA',
  text: '#1A1A1A',
  textSecondary: '#666666',
}

export default function HomeScreen() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const loadSummary = useCallback(async () => {
    try {
      const data = await getDashboardSummaryApi()
      setSummary(data)
    } catch {
      setSummary({
        app_name: '智能物料管理系统',
        today_inbound: 0, today_outbound: 0, pending_issues: 0,
        on_shelf_pallets: 0, pending_shelving_pallets: 0,
        physical_inventory: 0,
        tracking_pallets: 0, pending_receipts: 0,
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

  return (
    <View style={styles.container}>
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
              <SummaryCard
                title="在库料盘"
                value={summary?.physical_inventory ?? 0}
                unit="盘"
                subtitle={summary ? `上架${summary.on_shelf_pallets} · 待上架${summary.pending_shelving_pallets}` : ''}
                color={Colors.success}
              />
            </View>
          </View>
        )}

        {/* Pending Reminders */}
        <Text style={styles.sectionTitle}>待办提醒</Text>
        <View style={styles.reminderCard}>
          {(summary?.pending_issues ?? 0) > 0 && (
            <View style={styles.reminderRow}>
              <View style={[styles.reminderDot, { backgroundColor: Colors.warning }]} />
              <Text style={styles.reminderText}>
                {summary?.pending_issues} 组亮灯等待出库
              </Text>
            </View>
          )}
          {(summary?.pending_receipts ?? 0) > 0 && (
            <View style={styles.reminderRow}>
              <View style={[styles.reminderDot, { backgroundColor: Colors.primary }]} />
              <Text style={styles.reminderText}>
                {summary?.pending_receipts} 单待入库确认
              </Text>
            </View>
          )}
          {(summary?.pending_shelving_pallets ?? 0) > 0 && (
            <View style={styles.reminderRow}>
              <View style={[styles.reminderDot, { backgroundColor: Colors.warning }]} />
              <Text style={styles.reminderText}>
                {summary?.pending_shelving_pallets} 盘待上架
              </Text>
            </View>
          )}
          {(summary?.pending_issues ?? 0) === 0 &&
           (summary?.pending_receipts ?? 0) === 0 &&
           (summary?.pending_shelving_pallets ?? 0) === 0 && (
            <View style={styles.reminderRow}>
              <View style={[styles.reminderDot, { backgroundColor: Colors.success }]} />
              <Text style={styles.reminderText}>暂无待办事项</Text>
            </View>
          )}
        </View>

        <Text style={styles.version}>版本 3.0.0</Text>
      </ScrollView>
    </View>
  )
}

function SummaryCard({ title, value, unit, subtitle }: {
  title: string; value: number; unit: string; subtitle?: string
}) {
  return (
    <View style={styles.summaryCard}>
      <Text style={styles.summaryValue}>{value}</Text>
      <Text style={styles.summaryUnit}>{title}</Text>
      <Text style={styles.summaryUnitSmall}>{unit}</Text>
      {subtitle ? (
        <Text style={[styles.summaryUnitSmall, { marginTop: 2, fontSize: 11 }]}>{subtitle}</Text>
      ) : null}
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg },
  scrollView: { flex: 1 },
  scrollContent: { padding: 12, paddingBottom: 32 },
  summaryGrid: { gap: 8, marginBottom: 4 },
  summaryRow: { flexDirection: 'row', gap: 8 },
  summaryCard: {
    flex: 1, backgroundColor: Colors.card, borderRadius: 12, padding: 12,
    alignItems: 'center', elevation: 2, shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 4,
  },
  summaryValue: { fontSize: 28, fontWeight: 'bold', color: Colors.text },
  summaryUnit: { fontSize: 14, color: Colors.text, marginTop: 2 },
  summaryUnitSmall: { fontSize: 12, color: Colors.textSecondary },
  sectionTitle: {
    fontSize: 18, fontWeight: 'bold', color: Colors.text,
    marginTop: 16, marginBottom: 8,
  },
  reminderCard: {
    backgroundColor: Colors.card, borderRadius: 12, padding: 16, elevation: 1,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.08, shadowRadius: 3,
  },
  reminderRow: { flexDirection: 'row', alignItems: 'center', marginVertical: 4 },
  reminderDot: { width: 8, height: 8, borderRadius: 4, marginRight: 12 },
  reminderText: { fontSize: 16, color: Colors.text },
  version: { textAlign: 'center', fontSize: 13, color: Colors.textSecondary, marginTop: 20 },
})
