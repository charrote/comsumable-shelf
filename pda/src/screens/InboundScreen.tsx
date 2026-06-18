import React, { useState, useEffect, useCallback } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, Alert,
  FlatList, ActivityIndicator, ScrollView,
} from 'react-native'
import { createReceiptApi, scanPreviewApi, scanInboundApi } from '../api'
import type { ReceiptScanResponse, BarcodePreviewResponse, MaterialCandidate } from '../types/api'
import { useAuthStore } from '../store/authStore'

const Colors = {
  primary: '#0066CC', success: '#00AA55', warning: '#FF9900', danger: '#DD3333',
  info: '#3399CC', card: '#FFFFFF', bg: '#F5F7FA', text: '#1A1A1A', textSecondary: '#666666',
}

type Step = 'start' | 'scanning'

type ConfirmMode = 'auto' | 'select_material' | 'new_material'

export default function InboundScreen() {
  const user = useAuthStore((s) => s.user)
  const [step, setStep] = useState<Step>('start')
  const [operator, setOperator] = useState(user?.username || '')
  const [barcode, setBarcode] = useState('')
  const [receiptId, setReceiptId] = useState<number | null>(null)
  const [receiptNo, setReceiptNo] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [history, setHistory] = useState<ReceiptScanResponse[]>([])

  // Preview state
  const [preview, setPreview] = useState<BarcodePreviewResponse | null>(null)
  const [confirmMode, setConfirmMode] = useState<ConfirmMode>('auto')
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null)
  const [newMaterialCode, setNewMaterialCode] = useState('')
  const [newMaterialName, setNewMaterialName] = useState('')
  const [manualQty, setManualQty] = useState('')

  const startReceipt = useCallback(async () => {
    if (!operator.trim()) {
      Alert.alert('提示', '请输入操作员姓名')
      return
    }
    setIsLoading(true)
    try {
      const receipt = await createReceiptApi({ operator: operator.trim() })
      setReceiptId(receipt.id)
      setReceiptNo(receipt.receipt_no)
      setStep('scanning')
    } catch (e: any) {
      Alert.alert('错误', e?.response?.data?.detail || '创建入库单失败')
    } finally {
      setIsLoading(false)
    }
  }, [operator])

  // Handle barcode scan: preview first
  const handleBarcodeSubmit = useCallback(async () => {
    if (!barcode.trim() || receiptId == null) return
    setIsLoading(true)
    setPreview(null)
    setConfirmMode('auto')
    setSelectedMaterialId(null)
    setNewMaterialCode('')
    setNewMaterialName('')
    try {
      const res = await scanPreviewApi(receiptId, { barcode: barcode.trim(), operator })
      setPreview(res)

      // Determine confirm mode based on status
      if (res.status === 'ok' && res.candidates && res.candidates.length > 0) {
        // Auto-proceed
        await doConfirmScan(res.barcode, res.material_id!, undefined, false, parseFloat(manualQty) || res.quantity)
      } else if (res.status === 'pending_review' && res.candidates && res.candidates.length > 0) {
        setConfirmMode('select_material')
        setManualQty(String(res.quantity || 1))
      } else if (res.status === 'new_material') {
        setConfirmMode('new_material')
        setNewMaterialCode(res.material_code || barcode.trim())
        setNewMaterialName(res.material_name || '')
        setManualQty(String(res.quantity || 1))
      } else if (res.status === 'ok') {
        // Direct auto-proceed
        await doConfirmScan(res.barcode, res.material_id!, undefined, false, parseFloat(manualQty) || res.quantity)
      }
    } catch (e: any) {
      Alert.alert('扫描失败', e?.response?.data?.detail || '条码解析失败，请重试')
    } finally {
      setIsLoading(false)
    }
  }, [barcode, receiptId, operator, manualQty])

  // Execute the actual scan/confirm
  const doConfirmScan = async (
    bc: string,
    matId?: number,
    _matCode?: string,
    isNew?: boolean,
    qty?: number,
  ) => {
    if (receiptId == null) return
    setIsLoading(true)
    try {
      const result = await scanInboundApi(receiptId, {
        barcode: bc,
        operator,
        qty: qty || 1,
        manual_material_id: matId || undefined,
        is_new_material: isNew || false,
        new_material_code: isNew ? newMaterialCode : undefined,
        new_material_name: isNew ? newMaterialName : undefined,
      })
      setHistory((prev) => [result, ...prev])
      setBarcode('')
      setPreview(null)
      setConfirmMode('auto')
      setSelectedMaterialId(null)
      setNewMaterialCode('')
      setNewMaterialName('')
      setManualQty('')

      if (result.status === 'ok') {
        // Auto-focus next scan
      } else if (result.status === 'duplicate') {
        Alert.alert('重复扫码', result.message || '该条码已入库')
      } else if (result.status === 'pending_review') {
        Alert.alert('需确认', result.message)
      }
    } catch (e: any) {
      Alert.alert('入库失败', e?.response?.data?.detail || '请重试')
    } finally {
      setIsLoading(false)
    }
  }

  // Confirm with selected material
  const handleConfirmWithSelection = async () => {
    if (!preview) return
    const qty = parseFloat(manualQty) || preview.quantity
    if (confirmMode === 'select_material' && selectedMaterialId) {
      await doConfirmScan(preview.barcode, selectedMaterialId, undefined, false, qty)
    } else if (confirmMode === 'new_material') {
      await doConfirmScan(preview.barcode, undefined, undefined, true, qty)
    }
  }

  // Start screen
  if (step === 'start') {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>收料入库</Text>
          <Text style={styles.headerSub}>扫描客户条码 → 自动识别 → 确认 → 打印标签</Text>
        </View>
        <View style={styles.form}>
          <Text style={styles.label}>操作员</Text>
          <TextInput
            style={styles.input}
            placeholder="操作员姓名"
            value={operator}
            onChangeText={setOperator}
          />
          <TouchableOpacity
            style={[styles.button, !operator.trim() && styles.buttonDisabled]}
            onPress={startReceipt}
            disabled={!operator.trim() || isLoading}
          >
            {isLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>开始入库</Text>}
          </TouchableOpacity>
        </View>
      </View>
    )
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>收料入库</Text>
        <Text style={styles.headerSub}>入库单: {receiptNo || `#${receiptId}`}</Text>
      </View>

      <ScrollView style={styles.scrollArea} contentContainerStyle={styles.scrollContent}>
        {/* Scan Input */}
        <View style={styles.scanSection}>
          <TextInput
            style={styles.input}
            placeholder="扫描客户条码"
            value={barcode}
            onChangeText={setBarcode}
            autoFocus
            onSubmitEditing={handleBarcodeSubmit}
          />
          <TouchableOpacity
            style={[styles.button, !barcode.trim() && styles.buttonDisabled]}
            onPress={handleBarcodeSubmit}
            disabled={!barcode.trim() || isLoading}
          >
            {isLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>扫描识别</Text>}
          </TouchableOpacity>
        </View>

        {/* Preview Card */}
        {preview && (
          <View style={[styles.previewCard, preview.status === 'ok' ? styles.previewOk : styles.previewWarn]}>
            <Text style={styles.previewTitle}>
              {preview.status === 'ok' ? '✅ 匹配成功' :
               preview.status === 'new_material' ? '🆕 新料号' : '⚠️ 需确认'}
            </Text>
            <View style={styles.previewRow}>
              <Text style={styles.previewLabel}>条码</Text>
              <Text style={styles.previewValue}>{preview.barcode}</Text>
            </View>
            <View style={styles.previewRow}>
              <Text style={styles.previewLabel}>物料编码</Text>
              <Text style={styles.previewValueBold}>{preview.material_code || '--'}</Text>
            </View>
            <View style={styles.previewRow}>
              <Text style={styles.previewLabel}>物料名称</Text>
              <Text style={styles.previewValue}>{preview.material_name || '--'}</Text>
            </View>
            <View style={styles.previewRow}>
              <Text style={styles.previewLabel}>数量</Text>
              <Text style={styles.previewValue}>{preview.quantity} {preview.unit}</Text>
            </View>
            {preview.batch_no ? (
              <View style={styles.previewRow}>
                <Text style={styles.previewLabel}>批次</Text>
                <Text style={styles.previewValue}>{preview.batch_no}</Text>
              </View>
            ) : null}
            {preview.date_code ? (
              <View style={styles.previewRow}>
                <Text style={styles.previewLabel}>生产周期</Text>
                <Text style={styles.previewValue}>{preview.date_code}</Text>
              </View>
            ) : null}
            {preview.spec ? (
              <View style={styles.previewRow}>
                <Text style={styles.previewLabel}>规格</Text>
                <Text style={styles.previewValue}>{preview.spec}</Text>
              </View>
            ) : null}
            {preview.confidence > 0 && preview.confidence < 1 && (
              <View style={styles.previewRow}>
                <Text style={styles.previewLabel}>置信度</Text>
                <Text style={styles.previewValue}>{(preview.confidence * 100).toFixed(0)}%</Text>
              </View>
            )}

            {/* Candidate selection */}
            {confirmMode === 'select_material' && preview.candidates && preview.candidates.length > 0 && (
              <View style={styles.candidateSection}>
                <Text style={styles.candidateTitle}>请选择匹配的物料：</Text>
                {preview.candidates.map((c: MaterialCandidate) => (
                  <TouchableOpacity
                    key={c.material_id}
                    style={[styles.candidateItem, selectedMaterialId === c.material_id && styles.candidateSelected]}
                    onPress={() => setSelectedMaterialId(c.material_id)}
                  >
                    <Text style={styles.candidateCode}>{c.code}</Text>
                    <Text style={styles.candidateName}>{c.name}</Text>
                    <Text style={styles.candidateConf}>匹配度: {(c.confidence * 100).toFixed(0)}%</Text>
                  </TouchableOpacity>
                ))}
                <View style={styles.qtyRow}>
                  <Text style={styles.previewLabel}>数量</Text>
                  <TextInput
                    style={styles.qtyInput}
                    value={manualQty}
                    onChangeText={setManualQty}
                    keyboardType="numeric"
                    placeholder="1"
                  />
                  <Text style={styles.previewLabel}>盘</Text>
                </View>
                <TouchableOpacity
                  style={[styles.button, styles.confirmButton, !selectedMaterialId && styles.buttonDisabled]}
                  onPress={handleConfirmWithSelection}
                  disabled={!selectedMaterialId || isLoading}
                >
                  {isLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>确认入库</Text>}
                </TouchableOpacity>
              </View>
            )}

            {/* New material form */}
            {confirmMode === 'new_material' && (
              <View style={styles.candidateSection}>
                <Text style={styles.candidateTitle}>确认为新料号：</Text>
                <Text style={styles.previewLabel}>料号编码</Text>
                <TextInput
                  style={styles.input}
                  value={newMaterialCode}
                  onChangeText={setNewMaterialCode}
                  placeholder="输入料号编码"
                />
                <Text style={styles.previewLabel}>料号名称</Text>
                <TextInput
                  style={styles.input}
                  value={newMaterialName}
                  onChangeText={setNewMaterialName}
                  placeholder="输入物料名称"
                />
                <View style={styles.qtyRow}>
                  <Text style={styles.previewLabel}>数量</Text>
                  <TextInput
                    style={styles.qtyInput}
                    value={manualQty}
                    onChangeText={setManualQty}
                    keyboardType="numeric"
                    placeholder="1"
                  />
                  <Text style={styles.previewLabel}>盘</Text>
                </View>
                <TouchableOpacity
                  style={[styles.button, styles.confirmButton, (!newMaterialCode.trim()) && styles.buttonDisabled]}
                  onPress={handleConfirmWithSelection}
                  disabled={!newMaterialCode.trim() || isLoading}
                >
                  {isLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>确认新料入库</Text>}
                </TouchableOpacity>
              </View>
            )}
          </View>
        )}

        {/* Scan History */}
        {history.length > 0 && (
          <>
            <Text style={styles.sectionTitle}>扫描记录 ({history.length})</Text>
            {history.map((item, i) => (
              <View key={i} style={styles.historyItem}>
                <View style={styles.historyDot}>
                  <View style={[
                    styles.dot,
                    item.status === 'ok' ? styles.dotSuccess :
                    item.status === 'duplicate' ? styles.dotWarn : styles.dotError,
                  ]} />
                </View>
                <View style={styles.historyContent}>
                  <Text style={styles.historyCode}>{item.material_code || '--'} × {item.quantity}</Text>
                  <Text style={styles.historyMsg}>{item.message}</Text>
                  {item.assigned_slot ? <Text style={styles.historySlot}>储位: {item.assigned_slot}</Text> : null}
                </View>
              </View>
            ))}
          </>
        )}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg },
  header: { backgroundColor: Colors.primary, paddingHorizontal: 16, paddingTop: 12, paddingBottom: 12 },
  headerTitle: { fontSize: 20, fontWeight: 'bold', color: '#fff' },
  headerSub: { fontSize: 13, color: 'rgba(255,255,255,0.85)', marginTop: 2 },
  form: { padding: 24, justifyContent: 'center', flex: 1 },
  scanSection: { padding: 16, backgroundColor: Colors.card, borderRadius: 12, margin: 12, elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 4 },
  scrollArea: { flex: 1 },
  scrollContent: { paddingBottom: 40 },
  label: { fontSize: 16, color: Colors.text, fontWeight: '600', marginBottom: 6 },
  input: { backgroundColor: '#fff', padding: 14, borderRadius: 8, marginBottom: 12, fontSize: 18, borderWidth: 1, borderColor: '#ddd' },
  button: { backgroundColor: Colors.primary, padding: 16, borderRadius: 8, alignItems: 'center', marginBottom: 12 },
  confirmButton: { backgroundColor: Colors.success, marginTop: 8 },
  buttonDisabled: { opacity: 0.5 },
  buttonText: { color: '#fff', fontSize: 18, fontWeight: '600' },
  previewCard: { padding: 16, borderRadius: 12, marginHorizontal: 12, marginBottom: 12, borderWidth: 1 },
  previewOk: { backgroundColor: '#f0fff4', borderColor: Colors.success },
  previewWarn: { backgroundColor: '#fffbe6', borderColor: Colors.warning },
  previewTitle: { fontSize: 18, fontWeight: 'bold', color: Colors.text, marginBottom: 12 },
  previewRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginVertical: 3 },
  previewLabel: { fontSize: 15, color: Colors.textSecondary, flex: 1 },
  previewValue: { fontSize: 15, color: Colors.text, flex: 2, textAlign: 'right' },
  previewValueBold: { fontSize: 16, color: Colors.text, fontWeight: 'bold', flex: 2, textAlign: 'right' },
  candidateSection: { marginTop: 12, borderTopWidth: 1, borderTopColor: '#eee', paddingTop: 12 },
  candidateTitle: { fontSize: 16, fontWeight: '600', color: Colors.text, marginBottom: 8 },
  candidateItem: { padding: 12, borderRadius: 8, borderWidth: 1, borderColor: '#ddd', marginBottom: 8, backgroundColor: '#fff' },
  candidateSelected: { borderColor: Colors.primary, backgroundColor: '#e6f0ff' },
  candidateCode: { fontSize: 16, fontWeight: 'bold', color: Colors.text },
  candidateName: { fontSize: 14, color: Colors.textSecondary, marginTop: 2 },
  candidateConf: { fontSize: 13, color: Colors.primary, marginTop: 2 },
  qtyRow: { flexDirection: 'row', alignItems: 'center', marginVertical: 8 },
  qtyInput: { backgroundColor: '#fff', padding: 10, borderRadius: 8, fontSize: 18, borderWidth: 1, borderColor: '#ddd', width: 80, textAlign: 'center', marginHorizontal: 8 },
  sectionTitle: { fontSize: 16, fontWeight: 'bold', color: Colors.text, marginHorizontal: 12, marginTop: 8, marginBottom: 8 },
  historyItem: { flexDirection: 'row', backgroundColor: Colors.card, padding: 12, borderRadius: 8, marginHorizontal: 12, marginBottom: 6, borderWidth: 1, borderColor: '#eee' },
  historyDot: { justifyContent: 'center', marginRight: 10 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  dotSuccess: { backgroundColor: Colors.success },
  dotWarn: { backgroundColor: Colors.warning },
  dotError: { backgroundColor: Colors.danger },
  historyContent: { flex: 1 },
  historyCode: { fontSize: 15, fontWeight: '600', color: Colors.text },
  historyMsg: { fontSize: 13, color: Colors.textSecondary, marginTop: 2 },
  historySlot: { fontSize: 13, color: Colors.primary, marginTop: 2 },
})
