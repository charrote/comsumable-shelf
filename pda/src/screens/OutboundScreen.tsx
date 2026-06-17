import React, { useState, useCallback } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, Alert,
  FlatList, ActivityIndicator
} from 'react-native'
import { listIssuesApi, getIssueDetailApi, calculateIssueApi, confirmPickApi } from '../api'
import type { IssueOrderResponse, IssueConfirmPickResponse, PalletSelection } from '../types/api'

type Step = 'operator' | 'select_issue' | 'pick'

export default function OutboundScreen() {
  const [step, setStep] = useState<Step>('operator')
  const [operator, setOperator] = useState('')
  const [issues, setIssues] = useState<IssueOrderResponse[]>([])
  const [selectedIssue, setSelectedIssue] = useState<IssueOrderResponse | null>(null)
  const [barcode, setBarcode] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [pallets, setPallets] = useState<PalletSelection[]>([])
  const [pickResult, setPickResult] = useState<IssueConfirmPickResponse | null>(null)

  const loadIssues = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await listIssuesApi({ status: 'pending' })
      setIssues(res.data || [])
      if ((res.data || []).length === 0) {
        Alert.alert('提示', '暂无待处理的出库单')
      }
    } catch (e: any) {
      Alert.alert('错误', e?.response?.data?.detail || '加载出库单失败')
    } finally {
      setIsLoading(false)
    }
  }, [])

  const selectIssue = useCallback(async (issue: IssueOrderResponse) => {
    setIsLoading(true)
    try {
      const detail = await getIssueDetailApi(issue.id)
      const calcRes = await calculateIssueApi(issue.id)
      const allPallets = calcRes.materials.flatMap((m) => m.pallets_selected)
      setPallets(allPallets)
      setSelectedIssue(detail)
      setStep('pick')
    } catch (e: any) {
      Alert.alert('错误', e?.response?.data?.detail || '加载出库单详情失败')
    } finally {
      setIsLoading(false)
    }
  }, [])

  const handleConfirmPick = useCallback(async () => {
    if (!barcode || !selectedIssue || pallets.length === 0) return
    setIsLoading(true)
    try {
      const result = await confirmPickApi(selectedIssue.id, {
        barcode,
        pallet_id: pallets[0].pallet_id,
        operator,
      })
      setPickResult(result)
      setBarcode('')
      if (result.all_picked) {
        Alert.alert('完成', '本出库单已全部拣料完成')
        setStep('select_issue')
        setSelectedIssue(null)
        setPickResult(null)
        setPallets([])
        loadIssues()
      }
    } catch (e: any) {
      Alert.alert('拣料确认失败', e?.response?.data?.detail || '请重试')
    } finally {
      setIsLoading(false)
    }
  }, [barcode, selectedIssue, pallets, operator])

  if (step === 'operator') {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>扫码出库</Text>
        <TextInput
          style={styles.input}
          placeholder="操作员姓名"
          value={operator}
          onChangeText={setOperator}
        />
        <TouchableOpacity
          style={[styles.button, !operator && styles.buttonDisabled]}
          onPress={() => { setStep('select_issue'); loadIssues() }}
          disabled={!operator}
        >
          <Text style={styles.buttonText}>下一步</Text>
        </TouchableOpacity>
      </View>
    )
  }

  if (step === 'select_issue') {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>选择出库单</Text>
        <TouchableOpacity style={styles.link} onPress={loadIssues}>
          <Text style={styles.linkText}>刷新</Text>
        </TouchableOpacity>
        {isLoading ? <ActivityIndicator style={{ marginTop: 20 }} /> : null}
        <FlatList
          data={issues}
          keyExtractor={(item) => String(item.id)}
          renderItem={({ item }) => (
            <TouchableOpacity style={styles.issueCard} onPress={() => selectIssue(item)}>
              <Text style={styles.issueNo}>单号: {item.order_no}</Text>
              <Text style={styles.issueStatus}>状态: {item.status}</Text>
              <Text style={styles.issueDetail}>
                物料: {item.details?.length ?? 0} 项
              </Text>
            </TouchableOpacity>
          )}
          ListEmptyComponent={!isLoading ? <Text style={styles.emptyText}>暂无待处理出库单</Text> : null}
        />
      </View>
    )
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>拣料确认</Text>
      <Text style={styles.issueNo}>单号: {selectedIssue?.order_no}</Text>

      <Text style={styles.sectionTitle}>待拣料盘:</Text>
      {pallets.map((p, i) => (
        <View key={i} style={styles.palletCard}>
          <Text>料盘ID: {p.pallet_id}</Text>
          <Text>数量: {p.quantity}</Text>
          <Text>储位: {p.shelf_slot_id}</Text>
        </View>
      ))}

      <TextInput
        style={styles.input}
        placeholder="扫描料盘条码"
        value={barcode}
        onChangeText={setBarcode}
        autoFocus
      />
      <TouchableOpacity
        style={[styles.button, !barcode && styles.buttonDisabled]}
        onPress={handleConfirmPick}
        disabled={!barcode || isLoading}
      >
        {isLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>确认出库</Text>}
      </TouchableOpacity>

      {pickResult ? (
        <View style={[styles.resultBox, pickResult.status === 'ok' ? styles.successBox : styles.warningBox]}>
          <Text style={styles.resultText}>状态: {pickResult.status}</Text>
          <Text>已拣: {pickResult.picked_qty} / 剩余: {pickResult.remaining_qty}</Text>
        </View>
      ) : null}
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, backgroundColor: '#f5f5f5' },
  title: { fontSize: 22, fontWeight: 'bold', marginBottom: 16, color: '#333' },
  input: { backgroundColor: '#fff', padding: 14, borderRadius: 8, marginBottom: 16, fontSize: 18, borderWidth: 1, borderColor: '#ddd' },
  button: { backgroundColor: '#ff4d4f', padding: 16, borderRadius: 8, alignItems: 'center', marginBottom: 16 },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: '#fff', fontSize: 18, fontWeight: '600' },
  link: { marginBottom: 12 },
  linkText: { color: '#1890ff', fontSize: 16 },
  issueCard: { backgroundColor: '#fff', padding: 16, borderRadius: 8, marginBottom: 12, borderWidth: 1, borderColor: '#eee' },
  issueNo: { fontSize: 16, fontWeight: '600', color: '#333' },
  issueStatus: { fontSize: 14, color: '#666', marginTop: 4 },
  issueDetail: { fontSize: 14, color: '#999', marginTop: 4 },
  emptyText: { textAlign: 'center', color: '#999', marginTop: 40, fontSize: 16 },
  sectionTitle: { fontSize: 16, fontWeight: '600', marginBottom: 8, color: '#333' },
  palletCard: { backgroundColor: '#fff', padding: 12, borderRadius: 8, marginBottom: 8, borderWidth: 1, borderColor: '#eee' },
  resultBox: { padding: 12, borderRadius: 8, marginBottom: 16 },
  successBox: { backgroundColor: '#f6ffed', borderWidth: 1, borderColor: '#b7eb8f' },
  warningBox: { backgroundColor: '#fffbe6', borderWidth: 1, borderColor: '#ffe58f' },
  resultText: { fontSize: 16, fontWeight: '600', color: '#333' },
})
