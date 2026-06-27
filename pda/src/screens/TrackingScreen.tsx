import React, { useState, useEffect, useCallback } from 'react'
import {
  View, Text, StyleSheet, FlatList, ActivityIndicator, TouchableOpacity,
  TextInput, RefreshControl,
} from 'react-native'
import { getInventoryApi } from '../api'
import type { ReelInfo } from '../types/api'

const Colors = {
  primary: '#0066CC', success: '#00AA55', warning: '#FF9900', danger: '#DD3333',
  info: '#3399CC', card: '#FFFFFF', bg: '#F5F7FA', text: '#1A1A1A', textSecondary: '#666666',
}

type Tab = 'pending' | 'onshelf'

export default function TrackingScreen() {
  const [tab, setTab] = useState<Tab>('pending')
  const [allReels, setAllReels] = useState<ReelInfo[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [searchKeyword, setSearchKeyword] = useState('')

  // Status 中文映射
  const statusLabels: Record<string, string> = {
    pending_shelving: '待上架',
    on_shelf: '在架',
    in_use: '使用中',
    tracking: '跟踪中',
    exhausted: '已耗尽',
    ready_restock: '待退库',
  }

  const statusColorsMap: Record<string, string> = {
    pending_shelving: Colors.warning,
    on_shelf: Colors.success,
    in_use: Colors.info,
    tracking: Colors.warning,
    exhausted: Colors.danger,
    ready_restock: '#9B59B6',
  }

  const loadAll = useCallback(async () => {
    try {
      const res = await getInventoryApi()
      setAllReels(res.pallets || [])
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    setIsLoading(true)
    loadAll().finally(() => setIsLoading(false))
  }, [loadAll])

  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await loadAll()
    setRefreshing(false)
  }, [loadAll])

  // ── 按 Tab 过滤 ──
  const pendingList = allReels.filter(r => r.status === 'pending_shelving')
  const onshelfList = allReels.filter(r => r.status === 'on_shelf')

  // 搜索过滤
  const filterByKeyword = (list: ReelInfo[]) =>
    searchKeyword
      ? list.filter(item =>
          item.material_code?.toLowerCase().includes(searchKeyword.toLowerCase()) ||
          item.shelf_code?.toLowerCase().includes(searchKeyword.toLowerCase())
        )
      : list

  const currentList = tab === 'pending'
    ? filterByKeyword(pendingList)
    : filterByKeyword(onshelfList)

  // 统计
  const pendingCount = pendingList.length
  const onshelfCount = onshelfList.length
  const physicalInventory = pendingCount + onshelfCount
  const totalQty = allReels.reduce((sum, r) => sum + (r.quantity || 0), 0)

  const renderTabBar = () => (
    <View style={styles.tabBar}>
      <TouchableOpacity
        style={[styles.tab, tab === 'pending' && styles.tabActive]}
        onPress={() => setTab('pending')}
      >
        <Text style={[styles.tabText, tab === 'pending' && styles.tabTextActive]}>
          待上架 ({pendingCount})
        </Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.tab, tab === 'onshelf' && styles.tabActive]}
        onPress={() => setTab('onshelf')}
      >
        <Text style={[styles.tabText, tab === 'onshelf' && styles.tabTextActive]}>
          在库 ({onshelfCount})
        </Text>
      </TouchableOpacity>
    </View>
  )

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

      {/* Summary bar */}
      {allReels.length > 0 && (
        <View style={styles.summaryBar}>
          <Text style={[styles.summaryText, { color: Colors.success }]}>
            物理在库: {physicalInventory} 盘
          </Text>
          <Text style={styles.summaryText}>在架 {onshelfCount}</Text>
          {pendingCount > 0 && (
            <Text style={[styles.summaryText, { color: Colors.warning }]}>
              待上架 {pendingCount}
            </Text>
          )}
          <Text style={styles.summaryText}>总量: {totalQty}</Text>
        </View>
      )}

      {isLoading ? (
        <ActivityIndicator style={{ marginTop: 40 }} size="large" color={Colors.primary} />
      ) : (
        <FlatList
          data={currentList}
          keyExtractor={(item) => String(item.reel_id)}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[Colors.primary]} />}
          renderItem={({ item }) => {
            const itemStatus = item.status || ''
            const statusColor = statusColorsMap[itemStatus] || Colors.warning
            return (
              <View style={styles.card}>
                <View style={styles.cardHeader}>
                  <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
                  <Text style={styles.cardTitle}>{item.material_code}</Text>
                  {itemStatus && (
                    <View style={styles.statusLabel}>
                      <Text style={[styles.statusLabelText, { color: statusColor }]}>
                        {statusLabels[itemStatus] || itemStatus}
                      </Text>
                    </View>
                  )}
                </View>
                {item.material_name ? (
                  <Text style={styles.cardSub}>{item.material_name}</Text>
                ) : null}
                <View style={styles.cardRow}>
                  <Text style={styles.cardBody}>数量: {item.quantity}</Text>
                  {item.shelf_code ? (
                    <Text style={styles.cardBody}>料架: {item.shelf_code}</Text>
                  ) : (
                    <Text style={[styles.cardBody, { color: Colors.warning }]}>未上架</Text>
                  )}
                </View>
                {item.first_in_time ? (
                  <Text style={styles.cardSmall}>入库时间: {item.first_in_time}</Text>
                ) : null}
              </View>
            )
          }}
          ListEmptyComponent={
            <Text style={styles.emptyText}>
              {tab === 'pending' ? '暂无待上架物料' : '暂无在库物料'}
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
