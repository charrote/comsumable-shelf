import React, { useState, useCallback } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, Alert,
  FlatList, ActivityIndicator
} from 'react-native'
import { createReceiptApi, scanInboundApi } from '../api'
import type { ReceiptScanResponse } from '../types/api'

export default function RestockScreen() {
  const [operator, setOperator] = useState('')
  const [barcode, setBarcode] = useState('')
  const [receiptId, setReceiptId] = useState<number | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [history, setHistory] = useState<ReceiptScanResponse[]>([])
  const [lastResult, setLastResult] = useState<ReceiptScanResponse | null>(null)

  const startRestock = useCallback(async () => {
    if (!operator) return
    setIsLoading(true)
    try {
      const receipt = await createReceiptApi({ operator, type: 'restock' })
      setReceiptId(receipt.id)
    } catch (e: any) {
      Alert.alert('错误', e?.response?.data?.detail || '创建补料单失败')
    } finally {
      setIsLoading(false)
    }
  }, [operator])

  const handleScan = useCallback(async () => {
    if (!barcode || receiptId == null) return
    setIsLoading(true)
    try {
      const result = await scanInboundApi(receiptId, { barcode, operator })
      setLastResult(result)
      setHistory((prev) => [result, ...prev])
      setBarcode('')
    } catch (e: any) {
      Alert.alert('扫描失败', e?.response?.data?.detail || '请重试')
    } finally {
      setIsLoading(false)
    }
  }, [barcode, receiptId, operator])

  if (receiptId == null) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>补料上架</Text>
        <TextInput
          style={styles.input}
          placeholder="操作员姓名"
          value={operator}
          onChangeText={setOperator}
        />
        <TouchableOpacity
          style={[styles.button, !operator && styles.buttonDisabled]}
          onPress={startRestock}
          disabled={!operator || isLoading}
        >
          {isLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>开始补料</Text>}
        </TouchableOpacity>
      </View>
    )
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>补料上架</Text>
      <Text style={styles.receiptInfo}>补料单 #{receiptId}</Text>

      <TextInput
        style={styles.input}
        placeholder="扫描条码"
        value={barcode}
        onChangeText={setBarcode}
        autoFocus
      />
      <TouchableOpacity
        style={[styles.button, !barcode && styles.buttonDisabled]}
        onPress={handleScan}
        disabled={!barcode || isLoading}
      >
        {isLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>确认上架</Text>}
      </TouchableOpacity>

      {lastResult ? (
        <View style={[styles.resultBox, lastResult.status === 'ok' ? styles.successBox : styles.warningBox]}>
          <Text style={styles.resultText}>{lastResult.message}</Text>
          <Text style={styles.resultSub}>操作: {lastResult.action}</Text>
          {lastResult.assigned_slot ? <Text style={styles.resultSub}>储位: {lastResult.assigned_slot}</Text> : null}
        </View>
      ) : null}

      <Text style={styles.sectionTitle}>扫描记录 ({history.length})</Text>
      <FlatList
        data={history}
        keyExtractor={(_, i) => String(i)}
        renderItem={({ item }) => (
          <View style={styles.historyItem}>
            <Text style={styles.historyText}>{item.message}</Text>
          </View>
        )}
        style={styles.list}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, backgroundColor: '#f5f5f5' },
  title: { fontSize: 22, fontWeight: 'bold', marginBottom: 4, color: '#333' },
  receiptInfo: { fontSize: 14, color: '#666', marginBottom: 16 },
  input: { backgroundColor: '#fff', padding: 14, borderRadius: 8, marginBottom: 16, fontSize: 18, borderWidth: 1, borderColor: '#ddd' },
  button: { backgroundColor: '#fa8c16', padding: 16, borderRadius: 8, alignItems: 'center', marginBottom: 16 },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: '#fff', fontSize: 18, fontWeight: '600' },
  resultBox: { padding: 12, borderRadius: 8, marginBottom: 16 },
  successBox: { backgroundColor: '#f6ffed', borderWidth: 1, borderColor: '#b7eb8f' },
  warningBox: { backgroundColor: '#fffbe6', borderWidth: 1, borderColor: '#ffe58f' },
  resultText: { fontSize: 16, fontWeight: '600', color: '#333' },
  resultSub: { fontSize: 14, color: '#666', marginTop: 4 },
  sectionTitle: { fontSize: 16, fontWeight: '600', marginBottom: 8, color: '#333' },
  list: { flex: 1 },
  historyItem: { backgroundColor: '#fff', padding: 12, borderRadius: 8, marginBottom: 8, borderWidth: 1, borderColor: '#eee' },
  historyText: { fontSize: 14, color: '#333' },
})
