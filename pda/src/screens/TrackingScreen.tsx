import React, { useState, useEffect, useCallback } from 'react'
import { View, Text, StyleSheet, FlatList, ActivityIndicator, TouchableOpacity } from 'react-native'
import { getTrackingInventoryApi, getInventoryApi } from '../api'
import type { TrackingPalletResponse, PalletInfo } from '../types/api'

type Tab = 'tracking' | 'onshelf'

export default function TrackingScreen() {
  const [tab, setTab] = useState<Tab>('tracking')
  const [trackingList, setTrackingList] = useState<TrackingPalletResponse[]>([])
  const [onShelfList, setOnShelfList] = useState<PalletInfo[]>([])
  const [isLoading, setIsLoading] = useState(false)

  const loadTracking = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await getTrackingInventoryApi()
      setTrackingList(res.pallets || [])
    } catch {
      // ignore
    } finally {
      setIsLoading(false)
    }
  }, [])

  const loadOnShelf = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await getInventoryApi()
      setOnShelfList(res.pallets || [])
    } catch {
      // ignore
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadTracking()
  }, [loadTracking])

  useEffect(() => {
    if (tab === 'onshelf') loadOnShelf()
  }, [tab, loadOnShelf])

  const renderTabBar = () => (
    <View style={styles.tabBar}>
      <TouchableOpacity
        style={[styles.tab, tab === 'tracking' && styles.tabActive]}
        onPress={() => setTab('tracking')}
      >
        <Text style={[styles.tabText, tab === 'tracking' && styles.tabTextActive]}>跟踪中</Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.tab, tab === 'onshelf' && styles.tabActive]}
        onPress={() => setTab('onshelf')}
      >
        <Text style={[styles.tabText, tab === 'onshelf' && styles.tabTextActive]}>在库</Text>
      </TouchableOpacity>
    </View>
  )

  const data = tab === 'tracking' ? trackingList : onShelfList

  return (
    <View style={styles.container}>
      <Text style={styles.title}>库存跟踪</Text>
      {renderTabBar()}

      {isLoading ? (
        <ActivityIndicator style={{ marginTop: 40 }} />
      ) : (
        <FlatList
          data={data}
          keyExtractor={(item) => String((item as any).pallet_id)}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <Text style={styles.cardTitle}>料号: {(item as any).material_code}</Text>
              <Text style={styles.cardBody}>数量: {(item as any).quantity}</Text>
              <Text style={styles.cardBody}>状态: {(item as any).status}</Text>
              {'last_out_time' in item && item.last_out_time ? (
                <Text style={styles.cardBody}>最后出库: {item.last_out_time}</Text>
              ) : null}
              {'shelf_code' in item && item.shelf_code ? (
                <Text style={styles.cardBody}>货架: {item.shelf_code}</Text>
              ) : null}
              {'xr_matched' in item ? (
                <Text style={styles.cardBody}>
                  XR匹配: {item.xr_matched ? '是' : '否'}
                </Text>
              ) : null}
            </View>
          )}
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
  container: { flex: 1, padding: 24, backgroundColor: '#f5f5f5' },
  title: { fontSize: 22, fontWeight: 'bold', marginBottom: 16, color: '#333' },
  tabBar: { flexDirection: 'row', marginBottom: 16, borderRadius: 8, overflow: 'hidden', borderWidth: 1, borderColor: '#1890ff' },
  tab: { flex: 1, paddingVertical: 10, alignItems: 'center', backgroundColor: '#fff' },
  tabActive: { backgroundColor: '#1890ff' },
  tabText: { fontSize: 16, color: '#1890ff', fontWeight: '600' },
  tabTextActive: { color: '#fff' },
  card: { backgroundColor: '#fff', padding: 16, borderRadius: 8, marginBottom: 12, borderWidth: 1, borderColor: '#eee' },
  cardTitle: { fontSize: 16, fontWeight: '600', color: '#333', marginBottom: 4 },
  cardBody: { fontSize: 14, color: '#666', marginTop: 2 },
  emptyText: { textAlign: 'center', color: '#999', marginTop: 40, fontSize: 16 },
})
