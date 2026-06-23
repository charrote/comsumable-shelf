import React, { useState, useCallback, useRef } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, Alert,
  ActivityIndicator, ScrollView, Modal,
} from 'react-native'
import { createReceiptApi, scanPreviewApi, scanInboundApi, manualEntryApi } from '../api'
import type { ReceiptScanResponse, BarcodePreviewResponse, MaterialCandidate } from '../types/api'
import { useAuthStore } from '../store/authStore'

const Colors = {
  primary: '#0066CC', success: '#00AA55', warning: '#FF9900', danger: '#DD3333',
  info: '#3399CC', card: '#FFFFFF', bg: '#F5F7FA', text: '#1A1A1A', textSecondary: '#666666',
}

type Step = 'start' | 'scanning'

export default function InboundScreen() {
  const user = useAuthStore((s) => s.user)
  const [step, setStep] = useState<Step>('start')
  const [operator, setOperator] = useState(user?.username || '')
  const [barcode, setBarcode] = useState('')
  const [receiptId, setReceiptId] = useState<number | null>(null)
  const [receiptNo, setReceiptNo] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [history, setHistory] = useState<ReceiptScanResponse[]>([])
  const barcodeRef = useRef<TextInput>(null)

  // ── 手工录入模式（无条码标签） ──
  const [manualMode, setManualMode] = useState(false)
  const [manualMaterialCode, setManualMaterialCode] = useState('')
  const [manualMaterialName, setManualMaterialName] = useState('')
  const [manualSpec, setManualSpec] = useState('')
  const [manualQty, setManualQty] = useState('1')
  const [manualBatch, setManualBatch] = useState('')
  const [manualDateCode, setManualDateCode] = useState('')

  // ── 扫码预览结果（来自 scanPreviewApi，仅查询不保存） ──
  const [preview, setPreview] = useState<BarcodePreviewResponse | null>(null)
  const [confirmQty, setConfirmQty] = useState('')
  const [confirmError, setConfirmError] = useState('')

  // 候选物料选择（低置信度时）
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null)
  const [newMaterialCode, setNewMaterialCode] = useState('')
  const [newMaterialName, setNewMaterialName] = useState('')

  // ── 开始入库 ──
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
      setBarcode('')  // 进入扫码页前清空条码框
      setManualMode(false)
      setStep('scanning')
      // 自动聚焦扫码输入框
      setTimeout(() => barcodeRef.current?.focus(), 300)
    } catch (e: any) {
      Alert.alert('错误', e?.response?.data?.detail || '创建入库单失败')
    } finally {
      setIsLoading(false)
    }
  }, [operator])

  // ── 扫码：仅预览，不保存 ──
  const handleBarcodeSubmit = useCallback(async () => {
    if (!barcode.trim() || receiptId == null) return
    setIsLoading(true)
    setPreview(null)
    setConfirmQty('')
    setConfirmError('')
    setSelectedMaterialId(null)
    setNewMaterialCode('')
    setNewMaterialName('')
    try {
      const res = await scanPreviewApi(receiptId, {
        barcode: barcode.trim(),
        operator,
      })
      setPreview(res)
      setConfirmQty(String(res.quantity || 1))
      // 有候选物料时预填第一个
      if (res.candidates && res.candidates.length > 0) {
        setSelectedMaterialId(res.candidates[0].material_id)
      }
      setBarcode('')
      // 始终弹出确认框，无论置信度高低（不自动调 scanInboundApi）
    } catch (e: any) {
      // 扫码失败也要清空条码框，方便下一次扫码
      setBarcode('')
      Alert.alert('扫描失败', e?.response?.data?.detail || '条码解析失败，请重试')
    } finally {
      setIsLoading(false)
    }
  }, [barcode, receiptId, operator])

  // ── 用户点「确认入库」后才真正调 API 保存 ──
  const doConfirmScan = useCallback(async () => {
    if (receiptId == null || !preview) return
    const qty = parseFloat(confirmQty)
    if (isNaN(qty) || qty <= 0) {
      setConfirmError('请输入有效数量')
      return
    }

    setIsLoading(true)
    setConfirmError('')
    try {
      const hasCandidates = preview.candidates && preview.candidates.length > 0
      const isNewMaterial = preview.status === 'new_material'
      const matId = selectedMaterialId || preview.material_id

      const result = await scanInboundApi(receiptId, {
        barcode: preview.barcode,
        operator,
        qty,
        manual_material_id: (hasCandidates && matId) ? matId : undefined,
        is_new_material: isNewMaterial || false,
        new_material_code: isNewMaterial ? newMaterialCode : undefined,
        new_material_name: isNewMaterial ? newMaterialName : undefined,
      })

      // 成功 → 加入历史记录，关闭弹框，清空扫码框
      setHistory((prev) => [result, ...prev])
      setPreview(null)
      setConfirmQty('')
      setConfirmError('')
      setSelectedMaterialId(null)
      setNewMaterialCode('')
      setNewMaterialName('')
      setBarcode('')

      // 自动聚焦下一个扫码
      setTimeout(() => barcodeRef.current?.focus(), 300)

      if (result.status === 'duplicate') {
        Alert.alert('重复扫码', result.message || '该条码已入库')
      }
    } catch (e: any) {
      setConfirmError(e?.response?.data?.detail || '入库失败，请重试')
    } finally {
      setIsLoading(false)
    }
  }, [receiptId, preview, confirmQty, operator, selectedMaterialId, newMaterialCode, newMaterialName])

  // ── 手工录入提交 ──
  const handleManualSubmit = useCallback(async () => {
    if (receiptId == null) return
    const code = manualMaterialCode.trim()
    if (!code) {
      Alert.alert('提示', '请输入物料编码')
      return
    }
    const qty = parseFloat(manualQty)
    if (isNaN(qty) || qty <= 0) {
      Alert.alert('提示', '请输入有效数量')
      return
    }
    setIsLoading(true)
    try {
      const result = await manualEntryApi(receiptId, {
        operator,
        material_code: code,
        material_name: manualMaterialName.trim(),
        spec: manualSpec.trim() || undefined,
        quantity: qty,
        batch_no: manualBatch.trim() || undefined,
        date_code: manualDateCode.trim() || undefined,
      })
      // 成功 → 加入历史记录，清空表单
      setHistory((prev) => [result, ...prev])
      setManualMaterialCode('')
      setManualMaterialName('')
      setManualSpec('')
      setManualQty('1')
      setManualBatch('')
      setManualDateCode('')
      Alert.alert('成功', `入库成功！${result.material_code || code} × ${qty} 盘`)
    } catch (e: any) {
      Alert.alert('入库失败', e?.response?.data?.detail || '手工录入失败，请重试')
    } finally {
      setIsLoading(false)
    }
  }, [receiptId, operator, manualMaterialCode, manualMaterialName, manualSpec, manualQty, manualBatch, manualDateCode])

  // ── 取消确认 ──
  const handleCancelConfirm = useCallback(() => {
    setPreview(null)
    setConfirmQty('')
    setConfirmError('')
    setSelectedMaterialId(null)
    setNewMaterialCode('')
    setNewMaterialName('')
    setTimeout(() => barcodeRef.current?.focus(), 300)
  }, [])

  // 根据 status 判断预览卡片风格
  const isAutoMatch = preview?.status === 'ok' && (!preview.candidates || preview.candidates.length === 0)
  const isPendingReview = preview?.status === 'pending_review' || (preview?.candidates && preview.candidates.length > 0)
  const isNewMaterial = preview?.status === 'new_material'

  // ═══════════════════════════════════════════
  //  开始页
  // ═══════════════════════════════════════════
  if (step === 'start') {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>收料入库</Text>
          <Text style={styles.headerSub}>扫描客户条码 → 确认数量 → 入库</Text>
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

  // ═══════════════════════════════════════════
  //  扫码页
  // ═══════════════════════════════════════════
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>收料入库</Text>
        <Text style={styles.headerSub}>入库单: {receiptNo || `#${receiptId}`}</Text>
      </View>

      <ScrollView style={styles.scrollArea} contentContainerStyle={styles.scrollContent}>
        {/* ── 模式切换：扫码 / 手工 ── */}
        <View style={styles.modeToggle}>
          <TouchableOpacity
            style={[styles.modeButton, !manualMode && styles.modeButtonActive]}
            onPress={() => { setManualMode(false); setTimeout(() => barcodeRef.current?.focus(), 200) }}
          >
            <Text style={[styles.modeButtonText, !manualMode && styles.modeButtonTextActive]}>📷 扫码</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.modeButton, manualMode && styles.modeButtonActive]}
            onPress={() => { setManualMode(true); setBarcode('') }}
          >
            <Text style={[styles.modeButtonText, manualMode && styles.modeButtonTextActive]}>✏️ 手工</Text>
          </TouchableOpacity>
        </View>

        {/* ── 扫码模式 ── */}
        {!manualMode && (
          <View style={styles.scanSection}>
            <TextInput
              ref={barcodeRef}
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
        )}

        {/* ── 手工录入模式 ── */}
        {manualMode && (
          <View style={styles.scanSection}>
            <Text style={styles.sectionLabel}>物料编码 *</Text>
            <TextInput
              style={styles.input}
              placeholder="输入物料编码"
              value={manualMaterialCode}
              onChangeText={setManualMaterialCode}
            />
            <Text style={styles.sectionLabel}>物料名称</Text>
            <TextInput
              style={styles.input}
              placeholder="输入物料名称"
              value={manualMaterialName}
              onChangeText={setManualMaterialName}
            />
            <Text style={styles.sectionLabel}>规格</Text>
            <TextInput
              style={styles.input}
              placeholder="如：0805"
              value={manualSpec}
              onChangeText={setManualSpec}
            />
            <View style={styles.qtyRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.sectionLabel}>数量 *</Text>
                <TextInput
                  style={styles.input}
                  placeholder="1"
                  value={manualQty}
                  onChangeText={setManualQty}
                  keyboardType="numeric"
                />
              </View>
            </View>
            <Text style={styles.sectionLabel}>批次号</Text>
            <TextInput
              style={styles.input}
              placeholder="选填"
              value={manualBatch}
              onChangeText={setManualBatch}
            />
            <Text style={styles.sectionLabel}>生产周期</Text>
            <TextInput
              style={styles.input}
              placeholder="如：2401"
              value={manualDateCode}
              onChangeText={setManualDateCode}
            />
            <TouchableOpacity
              style={[styles.button, !manualMaterialCode.trim() && styles.buttonDisabled]}
              onPress={handleManualSubmit}
              disabled={!manualMaterialCode.trim() || isLoading}
            >
              {isLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>确认手工入库</Text>}
            </TouchableOpacity>
          </View>
        )}

        {/* 历史记录 */}
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

      {/* ═══════════════════════════════════════════
          确认弹框：扫码后无论置信度高低都弹出
          ═══════════════════════════════════════════ */}
      <Modal
        visible={preview != null}
        transparent
        animationType="fade"
        onRequestClose={handleCancelConfirm}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            {preview && (
              <>
                {/* 标题 */}
                <Text style={styles.modalTitle}>
                  {isAutoMatch ? '✅ 确认入库' :
                   isNewMaterial ? '🆕 确认新料入库' : '⚠️ 确认物料'}
                </Text>

                {/* 物料信息 */}
                <View style={styles.modalInfo}>
                  {/* 匹配度 + 状态 — 合并成一行醒目展示 */}
                  <View style={styles.confidenceRow}>
                    <View style={styles.confidenceBadge}>
                      <Text style={styles.confidenceLabel}>匹配度</Text>
                      <Text style={[
                        styles.confidenceValue,
                        { color: preview.confidence >= 0.8 ? Colors.success : preview.confidence >= 0.5 ? Colors.warning : Colors.danger }
                      ]}>
                        {(preview.confidence * 100).toFixed(0)}%
                      </Text>
                    </View>
                    <View style={[
                      styles.statusBadge,
                      { backgroundColor: isAutoMatch ? Colors.success : isNewMaterial ? Colors.info : Colors.warning }
                    ]}>
                      <Text style={styles.statusBadgeText}>
                        {isAutoMatch ? '自动匹配' : isNewMaterial ? '新料号' : '待确认'}
                      </Text>
                    </View>
                  </View>

                  {/* 进度条 */}
                  {preview.confidence > 0 && (
                    <View style={styles.confidenceBarOuter}>
                      <View style={[styles.confidenceBarInner, {
                        width: `${Math.min(preview.confidence * 100, 100)}%`,
                        backgroundColor: preview.confidence >= 0.8 ? Colors.success : preview.confidence >= 0.5 ? Colors.warning : Colors.danger,
                      }]} />
                    </View>
                  )}

                  {/* 字段列表 — 2 列网格 */}
                  <View style={styles.fieldsGrid}>
                    <View style={styles.fieldItem}>
                      <Text style={styles.fieldItemLabel}>条形码</Text>
                      <Text style={styles.fieldItemValue} numberOfLines={1}>{preview.barcode}</Text>
                    </View>
                    <View style={styles.fieldItem}>
                      <Text style={styles.fieldItemLabel}>供应商代码</Text>
                      <Text style={styles.fieldItemValue}>{preview.supplier_code || '--'}</Text>
                    </View>
                    <View style={[styles.fieldItem, styles.fieldItemFull]}>
                      <Text style={styles.fieldItemLabel}>物料编码</Text>
                      <Text style={styles.fieldItemValueBold}>{preview.material_code || '--'}</Text>
                    </View>
                    <View style={[styles.fieldItem, styles.fieldItemFull]}>
                      <Text style={styles.fieldItemLabel}>物料名称</Text>
                      <Text style={styles.fieldItemValue}>{preview.material_name || '--'}</Text>
                    </View>
                    <View style={styles.fieldItem}>
                      <Text style={styles.fieldItemLabel}>规格</Text>
                      <Text style={styles.fieldItemValue}>{preview.spec || '--'}</Text>
                    </View>
                    <View style={styles.fieldItem}>
                      <Text style={styles.fieldItemLabel}>批次号</Text>
                      <Text style={styles.fieldItemValue}>{preview.batch_no || '--'}</Text>
                    </View>
                    <View style={styles.fieldItem}>
                      <Text style={styles.fieldItemLabel}>生产周期</Text>
                      <Text style={styles.fieldItemValue}>{preview.date_code || '--'}</Text>
                    </View>
                    <View style={styles.fieldItem}>
                      <Text style={styles.fieldItemLabel}>数量</Text>
                      <Text style={styles.fieldItemValue}>{preview.quantity ?? '--'} 盘</Text>
                    </View>
                  </View>
                </View>

                {/* 候选物料选择（低置信度时） */}
                {isPendingReview && preview.candidates && preview.candidates.length > 0 && (
                  <View style={styles.candidateSection}>
                    <Text style={styles.candidateTitle}>请选择匹配的物料：</Text>
                    {preview.candidates.map((c: MaterialCandidate) => (
                      <TouchableOpacity
                        key={c.material_id}
                        style={[styles.candidateItem, selectedMaterialId === c.material_id && styles.candidateSelected]}
                        onPress={() => setSelectedMaterialId(c.material_id)}
                      >
                        <View style={styles.candidateRow}>
                          <View style={styles.candidateInfo}>
                            <Text style={styles.candidateCode}>{c.code}</Text>
                            <Text style={styles.candidateName}>{c.name}</Text>
                          </View>
                          <View style={[
                            styles.candidateConfBadge,
                            { backgroundColor: c.confidence >= 0.8 ? Colors.success : c.confidence >= 0.5 ? Colors.warning : Colors.danger }
                          ]}>
                            <Text style={styles.candidateConfText}>
                              {(c.confidence * 100).toFixed(0)}%
                            </Text>
                          </View>
                        </View>
                      </TouchableOpacity>
                    ))}
                  </View>
                )}

                {/* 新料号输入 */}
                {isNewMaterial && (
                  <View style={styles.candidateSection}>
                    <Text style={styles.candidateTitle}>确认为新料号：</Text>
                    <Text style={styles.fieldLabel}>料号编码</Text>
                    <TextInput
                      style={styles.input}
                      value={newMaterialCode}
                      onChangeText={setNewMaterialCode}
                      placeholder="输入料号编码"
                    />
                    <Text style={styles.fieldLabel}>料号名称</Text>
                    <TextInput
                      style={styles.input}
                      value={newMaterialName}
                      onChangeText={setNewMaterialName}
                      placeholder="输入物料名称"
                    />
                  </View>
                )}

                {/* 数量输入 */}
                <View style={styles.qtySection}>
                  <Text style={styles.qtyLabel}>入库数量</Text>
                  <View style={styles.qtyRow}>
                    <TextInput
                      style={styles.qtyInput}
                      value={confirmQty}
                      onChangeText={(v) => { setConfirmQty(v); setConfirmError('') }}
                      keyboardType="numeric"
                      editable={!isLoading}
                    />
                    <Text style={styles.qtyUnit}>盘</Text>
                  </View>
                </View>

                {/* 错误提示 */}
                {confirmError ? (
                  <Text style={styles.errorText}>{confirmError}</Text>
                ) : null}

                {/* 按钮 */}
                <View style={styles.modalButtons}>
                  <TouchableOpacity
                    style={[styles.modalButton, styles.cancelButton]}
                    onPress={handleCancelConfirm}
                    disabled={isLoading}
                  >
                    <Text style={styles.cancelButtonText}>取消</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[
                      styles.modalButton, styles.confirmButton,
                      (isLoading || (isPendingReview && !selectedMaterialId)) && styles.buttonDisabled
                    ]}
                    onPress={doConfirmScan}
                    disabled={isLoading || (isPendingReview && !selectedMaterialId)}
                  >
                    {isLoading ? (
                      <ActivityIndicator color="#fff" size="small" />
                    ) : (
                      <Text style={styles.confirmButtonText}>确认入库</Text>
                    )}
                  </TouchableOpacity>
                </View>
              </>
            )}
          </View>
        </View>
      </Modal>
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
  buttonDisabled: { opacity: 0.5 },
  buttonText: { color: '#fff', fontSize: 18, fontWeight: '600' },
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

  // ── 模式切换 ──
  modeToggle: { flexDirection: 'row', backgroundColor: Colors.card, borderRadius: 8, margin: 12, marginBottom: 0, padding: 4, borderWidth: 1, borderColor: '#ddd' },
  modeButton: { flex: 1, paddingVertical: 10, borderRadius: 6, alignItems: 'center' },
  modeButtonActive: { backgroundColor: Colors.primary },
  modeButtonText: { fontSize: 15, fontWeight: '600', color: Colors.textSecondary },
  modeButtonTextActive: { color: '#fff' },
  sectionLabel: { fontSize: 14, color: Colors.textSecondary, fontWeight: '600', marginBottom: 4, marginTop: 4 },

  // ── Modal ──
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  modalContent: { backgroundColor: '#fff', borderRadius: 16, padding: 20, width: '100%', maxWidth: 500, maxHeight: '90%' },
  modalTitle: { fontSize: 22, fontWeight: 'bold', color: Colors.text, marginBottom: 16, textAlign: 'center' },
  modalInfo: { marginBottom: 12 },
  // ── 置信度与状态 ──
  confidenceRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  confidenceBadge: { flexDirection: 'row', alignItems: 'baseline' },
  confidenceLabel: { fontSize: 14, color: Colors.textSecondary, marginRight: 6 },
  confidenceValue: { fontSize: 24, fontWeight: 'bold' },
  statusBadge: { paddingHorizontal: 12, paddingVertical: 4, borderRadius: 12 },
  statusBadgeText: { color: '#fff', fontSize: 13, fontWeight: '600' },
  // ── 置信度进度条 ──
  confidenceBarOuter: { height: 6, backgroundColor: '#e8e8e8', borderRadius: 3, marginBottom: 14, overflow: 'hidden' },
  confidenceBarInner: { height: 6, borderRadius: 3 },
  // ── 字段网格 ──
  fieldsGrid: { flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -6 },
  fieldItem: { width: '50%', paddingHorizontal: 6, marginBottom: 10 },
  fieldItemFull: { width: '100%' },
  fieldItemLabel: { fontSize: 12, color: Colors.textSecondary, marginBottom: 2 },
  fieldItemValue: { fontSize: 15, color: Colors.text },
  fieldItemValueBold: { fontSize: 17, color: Colors.text, fontWeight: 'bold' },

  // 候选物料
  candidateSection: { marginTop: 8, marginBottom: 12, borderTopWidth: 1, borderTopColor: '#eee', paddingTop: 12 },
  candidateTitle: { fontSize: 16, fontWeight: '600', color: Colors.text, marginBottom: 8 },
  candidateItem: { padding: 12, borderRadius: 8, borderWidth: 1, borderColor: '#ddd', marginBottom: 8, backgroundColor: '#fff' },
  candidateSelected: { borderColor: Colors.primary, backgroundColor: '#e6f0ff' },
  candidateRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  candidateInfo: { flex: 1, marginRight: 12 },
  candidateCode: { fontSize: 16, fontWeight: 'bold', color: Colors.text },
  candidateName: { fontSize: 14, color: Colors.textSecondary, marginTop: 2 },
  candidateConfBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, minWidth: 50, alignItems: 'center' },
  candidateConfText: { color: '#fff', fontSize: 13, fontWeight: 'bold' },
  fieldLabel: { fontSize: 14, color: Colors.textSecondary, fontWeight: '600', marginTop: 8, marginBottom: 4 },

  // 数量
  qtySection: { marginVertical: 12 },
  qtyLabel: { fontSize: 16, color: Colors.text, fontWeight: '600', marginBottom: 6 },
  qtyRow: { flexDirection: 'row', alignItems: 'center' },
  qtyInput: { backgroundColor: '#fff', padding: 12, borderRadius: 8, fontSize: 22, fontWeight: 'bold', borderWidth: 1, borderColor: '#ddd', width: 120, textAlign: 'center' },
  qtyUnit: { fontSize: 18, color: Colors.text, marginLeft: 8, fontWeight: '600' },
  errorText: { color: Colors.danger, fontSize: 15, textAlign: 'center', marginBottom: 8 },

  // 按钮
  modalButtons: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 },
  modalButton: { flex: 1, padding: 16, borderRadius: 8, alignItems: 'center', justifyContent: 'center', minHeight: 52 },
  cancelButton: { backgroundColor: '#f0f0f0', marginRight: 8 },
  confirmButton: { backgroundColor: Colors.success, marginLeft: 8 },
  cancelButtonText: { fontSize: 18, color: Colors.textSecondary, fontWeight: '600' },
  confirmButtonText: { fontSize: 18, color: '#fff', fontWeight: 'bold' },
})
