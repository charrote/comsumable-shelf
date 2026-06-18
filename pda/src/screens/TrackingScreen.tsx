import React, { useState, useEffect, useCallback } from 'react'
import {
  View, Text, StyleSheet, FlatList, ActivityIndicator, TouchableOpacity,
  TextInput, RefreshControl,
} from 'react-native'
import { getTrackingInventoryApi, getInventoryApi, getMaterialsApi } from '../api'
import type { TrackingReelResponse, ReelInfo, MaterialResponse } from '../types/api'

const Colors = {
  primary: '#0066CC', success: '#00AA55', warning: '#FF9900', danger: '#DD3333',
  info: '#3399CC', card: '#FFFFFF', bg: '#F5F7FA', text: '#1A1A1A', textSecondary: '#666666',
}

type Tab = 'tracking' | 'onshelf'

export default function TrackingScreen() {
  const [tab, setTab] = useState<Tab>('tracking')
  const [trackingList, setTrackingList] = useState<TrackingReelResponse[]>([])
  const [onShelfList, setOnShelfList] = useState<ReelInfo[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [searchKeyword, setSearchKeyword] = useState('')
  const [materials, setMaterials] = useState<MaterialResponse[]>([])

  const loadTracking = useCallback(async () => {
    try {
      const res = await getTrackingInventoryApi()
      setTrackingList(res.pallets || [])
    } catch {
      // ignore
    }
  }, [])

  const loadOnShelf = useCallback(async () => {
    try {
      const res = await getInventoryApi()
      setOnShelfList(res.pallets || [])
    } catch {
      // ignore
    }
  }, [])

  const loadMaterials = useCallback(async () => {
    try {
      const res = await getMaterialsApi()
      setMaterials(Array.isArray(res) ? res : [])
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    setIsLoading(true)
    Promise.all([loadTracking(), loadMaterials()]).finally(() => setIsLoading(false))
  }, [loadTracking, loadMaterials])

  useEffect(() => {
    if (tab === 'onshelf') {
      setIsLoading(true)
      loadOnShelf().finally(() => setIsLoading(false))
    }
  }, [tab, loadOnShelf])

  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    if (tab === 'tracking') {
      await loadTracking()
    } else {
      await loadOnShelf()
    }
    setRefreshing(false)
  }, [tab, loadTracking, loadOnShelf])

  // Filter on-shelf items by search keyword
  const filteredOnShelf = searchKeyword
    ? onShelfList.filter(item =>
        item.material_code?.toLowerCase().includes(searchKeyword.toLowerCase()) ||
        item.shelf_code?.toLowerCase().includes(searchKeyword.toLowerCase())
      )
    : onShelfList

  // Summary
  const totalOnShelf = onShelfList.filter(r => r.status === 'on_shelf').length
  const totalQty = onShelfList.reduce((sum, r) => sum + (r.quantity || 0), 0)
  const exhaustedCount = onShelfList.filter(r => r.status === 'exhausted').length

  const renderTabBar = () => (
    <View style={styles.tabBar}>
      <TouchableOpacity
        style={[styles.tab, tab === 'tracking' && styles.tabActive]}
        onPress={() => setTab('tracking')}
      >
        <Text style={[styles.tabText, tab === 'tracking' && styles.tabTextActive]}>
          跟踪中 ({trackingList.length})
        </Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.tab, tab === 'onshelf' && styles.tabActive]}
        onPress={() => setTab('onshelf')}
      >
        <Text style={[styles.tabText, tab === 'onshelf' && styles.tabTextActive]}>
          在库 ({totalOnShelf})
        </Text>
      </TouchableOpacity>
    </View>
  )

  const data = tab === 'tracking' ? trackingList : filteredOnShelf

  return (
    <View style={styles.container}>
      {/* Search Bar */}
      <View style={styles.searchRow}>
        <TextInput
          style={styles.searchInput}
          placeholder="搜索物料编码/料架..."
          value={searchKeyword}
          onChangeText={setSearchKeyword}
        />
        <TouchableOpacity style={styles.searchBtn} onPress={onRefresh}>
          <Text style={styles.searchBtnText}>刷新</Text>
        </TouchableOpacity>
      </View>

      {renderTabBar()}

      {/* Summary for on-shelf */}
      {tab === 'onshelf' && onShelfList.length > 0 && (
        <View style={styles.summaryBar}>
          <Text style={styles.summaryText}>在库: {totalOnShelf} 盘</Text>
          <Text style={styles.summaryText}>总量: {totalQty}</Text>
          <Text style={[styles.summaryText, { color: Colors.danger }]}>耗尽: {exhaustedCount}</Text>
        </View>
      )}

      {isLoading ? (
        <ActivityIndicator style={{ marginTop: 40 }} size="large" color={Colors.primary} />
      ) : (
        <FlatList
          data={data}
          keyExtractor={(item) => String((item as any).reel_id)}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[Colors.primary]} />}
          renderItem={({ item }) => {
            const isTracking = 'last_out_time' in item
            const statusColor = isTracking
              ? (item as TrackingReelResponse).xr_matched ? Colors.success : Colors.warning
              : (item as ReelInfo).status === 'on_shelf' ? Colors.success :
                (item as ReelInfo).status === 'exhausted' ? Colors.danger : Colors.warning
            return (
              <View style={styles.card}>
                <View style={styles.cardHeader}>
                  <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
                  <Text style={styles.cardTitle}>{item.material_code}</Text>
                  {(item as any).status && (
                    <View style={styles.statusLabel}>
                      <Text style={[styles.statusLabelText, { color: statusColor }]}>{(item as any).status}</Text>
                    </View>
                  )}
                </View>
                {item.material_name ? (
                  <Text style={styles.cardSub}>{item.material_name}</Text>
                ) : null}
                <View style={styles.cardRow}>
                  <Text style={styles.cardBody}>数量: {item.quantity}</Text>
                  {'shelf_code' in item && item.shelf_code ? (
                    <Text style={styles.cardBody}>料架: {item.shelf_code}</Text>
                  ) : null}
                </View>
                {'last_out_time' in item && item.last_out_time ? (
                  <Text style={styles.cardSmall}>最后出库: {item.last_out_time}</Text>
                ) : null}
                {'first_in_time' in item && item.first_in_time ? (
                  <Text style={styles.cardSmall}>入库时间: {item.first_in_time}</Text>
                ) : null}
                {'xr_matched' in item ? (
                  <Text style={[styles.cardSmall, { color: (item as TrackingReelResponse).xr_matched ? Colors.success : Colors.warning }]}>
                    XR匹配: {(item as TrackingReelResponse).xr_matched ? '✅ 已配对' : '⏳ 待配对'}
                  </Text>
                ) : null}
              </View>
            )
          }}
          ListEmptyComponent={
            <Text style={styles.emptyText}>
              {tab === 'tracking' ? '暂无跟踪中的物料' : '暂无在库物料'}
            </Text>
          }
        />
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 12, backgroundColor: Colors.bg },
  searchRow: { flexDirection: 'row', gap: 8, marginBottom: 10 },
  searchInput: { flex: 1, backgroundColor: Colors.card, padding: 12, borderRadius: 8, fontSize: 16, borderWidth: 1, borderColor: '#ddd' },
  searchBtn: { backgroundColor: Colors.primary, paddingHorizontal: 16, borderRadius: 8, justifyContent: 'center' },
  searchBtnText: { color: '#fff', fontSize: 15, fontWeight: '600' },
  tabBar: { flexDirection: 'row', marginBottom: 8, borderRadius: 8, overflow: 'hidden', borderWidth: 1, borderColor: Colors.primary },
  tab: { flex: 1, paddingVertical: 10, alignItems: 'center', backgroundColor: '#fff' },
  tabActive: { backgroundColor: Colors.primary },
  tabText: { fontSize: 15, color: Colors.primary, fontWeight: '600' },
  tabTextActive: { color: '#fff' },
  summaryBar: { flexDirection: 'row', justifyContent: 'space-around', backgroundColor: Colors.card, borderRadius: 8, padding: 10, marginBottom: 8, elevation: 1, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.05, shadowRadius: 2 },
  summaryText: { fontSize: 14, fontWeight: '600', color: Colors.text },
  card: { backgroundColor: Colors.card, padding: 14, borderRadius: 8, marginBottom: 8, borderWidth: 1, borderColor: '#eee', elevation: 1, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.05, shadowRadius: 2 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 4 },
  statusDot: { width: 8, height: 8, borderRadius: 4, marginRight: 8 },
  cardTitle: { fontSize: 16, fontWeight: '600', color: Colors.text, flex: 1 },
  cardSub: { fontSize: 14, color: Colors.textSecondary, marginLeft: 16, marginBottom: 4 },
  statusLabel: { paddingHorizontal: 6, paddingVertical: 1, borderRadius: 3, backgroundColor: '#f5f5f5' },
  statusLabelText: { fontSize: 11, fontWeight: '600' },
  cardRow: { flexDirection: 'row', gap: 16, marginLeft: 16, marginTop: 4 },
  cardBody: { fontSize: 14, color: Colors.text },
  cardSmall: { fontSize: 12, color: Colors.textSecondary, marginLeft: 16, marginTop: 2 },
  emptyText: { textAlign: 'center', color: Colors.textSecondary, marginTop: 40, fontSize: 16 },
})
