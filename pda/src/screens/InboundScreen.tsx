import React, { useState, useCallback, useRef, useEffect } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, Alert,
  ActivityIndicator, ScrollView, Modal, FlatList,
} from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { listReceiptsApi, createReceiptApi, scanPreviewApi, scanInboundApi, manualEntryApi, getReceiptDetailApi, cancelReceiptItemsApi } from '../api'
import type {
  BarcodePreviewResponse, MaterialCandidate,
  ReceiptListItem, ReceiptItem,
} from '../types/api'
import { useOperator } from '../hooks/useOperator'
import BarcodeScanner from '../components/BarcodeScanner'
import {
  PlusIcon, RefreshIcon, ListIcon, CheckIcon, CrossIcon,
  CameraIcon, PencilIcon, ScanIcon, WarningIcon, NewIcon,
  DocumentIcon,
} from '../components/Icons'

const Colors = {
  primary: '#0066CC', success: '#00AA55', warning: '#FF9900', danger: '#DD3333',
  info: '#3399CC', card: '#FFFFFF', bg: '#F5F7FA', text: '#1A1A1A', textSecondary: '#666666',
}

type Step = 'select' | 'scanning'

export default function InboundScreen() {
  const { operator } = useOperator()
  const insets = useSafeAreaInsets()
  const [step, setStep] = useState<Step>('select')
  const [barcode, setBarcode] = useState('')
  const [receiptId, setReceiptId] = useState<number | null>(null)
  const [receiptNo, setReceiptNo] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [receiptItems, setReceiptItems] = useState<ReceiptItem[]>([])
  const [showScanner, setShowScanner] = useState(false)
  const barcodeRef = useRef<TextInput>(null)

  // ── 收料单列表 ──
  const [receipts, setReceipts] = useState<ReceiptListItem[]>([])
  const [loadingList, setLoadingList] = useState(false)

  // ── 手工录入模式 ──
  const [manualMode, setManualMode] = useState(false)
  const [manualMaterialCode, setManualMaterialCode] = useState('')
  const [manualMaterialName, setManualMaterialName] = useState('')
  const [manualSpec, setManualSpec] = useState('')
  const [manualQty, setManualQty] = useState('1')
  const [manualBatch, setManualBatch] = useState('')
  const [manualDateCode, setManualDateCode] = useState('')

  // ── 扫码预览结果 ──
  const [preview, setPreview] = useState<BarcodePreviewResponse | null>(null)
  const [confirmQty, setConfirmQty] = useState('')
  const [confirmError, setConfirmError] = useState('')
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null)
  const [newMaterialCode, setNewMaterialCode] = useState('')
  const [newMaterialName, setNewMaterialName] = useState('')
  // ── 可手工修正的字段（初始化自 preview） ──
  const [editMaterialName, setEditMaterialName] = useState('')
  const [editSpec, setEditSpec] = useState('')
  const [editBatchNo, setEditBatchNo] = useState('')
  const [editDateCode, setEditDateCode] = useState('')

  // ── 加载收料单列表 ──
  const loadReceipts = useCallback(async () => {
    setLoadingList(true)
    try {
      const res = await listReceiptsApi({ status: 'draft' })
      setReceipts(res.data || [])
    } catch (e: any) {
      console.warn('加载收料单失败', e)
    } finally {
      setLoadingList(false)
    }
  }, [])

  // ── 加载收料单详情（已扫描的物料明细） ──
  const loadReceiptItems = useCallback(async (id: number) => {
    try {
      const detail = await getReceiptDetailApi(id)
      setReceiptItems(detail.items || [])
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => { loadReceipts() }, [loadReceipts])

  // ── 选择已有收料单 ──
  const selectReceipt = useCallback(async (receipt: ReceiptListItem) => {
    setReceiptId(receipt.id)
    setReceiptNo(receipt.receipt_no)
    setBarcode('')
    setManualMode(false)
    loadReceiptItems(receipt.id)
    setStep('scanning')
    setTimeout(() => barcodeRef.current?.focus(), 300)
  }, [])

  // ── 创建新收料单 ──
  const createNewReceipt = useCallback(async () => {
    if (!operator.trim()) {
      Alert.alert('提示', '请在设置页配置操作员姓名')
      return
    }
    setIsLoading(true)
    try {
      const receipt = await createReceiptApi({ operator: operator.trim() })
      setReceiptId(receipt.id)
      setReceiptNo(receipt.receipt_no)
      setBarcode('')
      setManualMode(false)
      setStep('scanning')
      setTimeout(() => barcodeRef.current?.focus(), 300)
    } catch (e: any) {
      Alert.alert('错误', e?.response?.data?.detail || '创建收料单失败')
    } finally {
      setIsLoading(false)
    }
  }, [operator])

  // ── 扫码：仅预览 ──
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
      setEditMaterialName(res.material_name || '')
      setEditSpec(res.spec || '')
      setEditBatchNo(res.batch_no || '')
      setEditDateCode(res.date_code || '')
      if (res.candidates && res.candidates.length > 0) {
        setSelectedMaterialId(res.candidates[0].material_id)
      }
      setBarcode('')
    } catch (e: any) {
      setBarcode('')
      Alert.alert('扫描失败', e?.response?.data?.detail || '条码解析失败，请重试')
    } finally {
      setIsLoading(false)
    }
  }, [barcode, receiptId, operator])

  // ── 确认入库 ──
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
        material_name: editMaterialName || undefined,
        spec: editSpec || undefined,
        batch_no: editBatchNo || undefined,
        date_code: editDateCode || undefined,
      })
      loadReceiptItems(receiptId)
      setPreview(null)
      setConfirmQty('')
      setConfirmError('')
      setSelectedMaterialId(null)
      setNewMaterialCode('')
      setNewMaterialName('')
      setEditMaterialName('')
      setEditSpec('')
      setEditBatchNo('')
      setEditDateCode('')
      setBarcode('')
      setTimeout(() => barcodeRef.current?.focus(), 300)
      if (result.status === 'duplicate') {
        Alert.alert('重复扫码', result.message || '该条码已入库')
      }
    } catch (e: any) {
      setConfirmError(e?.response?.data?.detail || '入库失败，请重试')
    } finally {
      setIsLoading(false)
    }
  }, [receiptId, preview, confirmQty, operator, selectedMaterialId, newMaterialCode, newMaterialName, editMaterialName, editSpec, editBatchNo, editDateCode])

  // ── 手工录入 ──
  const handleManualSubmit = useCallback(async () => {
    if (receiptId == null) return
    const code = manualMaterialCode.trim()
    if (!code) { Alert.alert('提示', '请输入物料编码'); return }
    const qty = parseFloat(manualQty)
    if (isNaN(qty) || qty <= 0) { Alert.alert('提示', '请输入有效数量'); return }
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
      setHistory((prev) => [result, ...prev])
      setManualMaterialCode('')
      setManualMaterialName('')
      setManualSpec('')
      setManualQty('1')
      setManualBatch('')
      setManualDateCode('')
      Alert.alert('成功', `入库成功！${result.material_code || code} x ${qty} 盘`)
    } catch (e: any) {
      Alert.alert('入库失败', e?.response?.data?.detail || '手工录入失败，请重试')
    } finally {
      setIsLoading(false)
    }
  }, [receiptId, operator, manualMaterialCode, manualMaterialName, manualSpec, manualQty, manualBatch, manualDateCode])

  // ── 摄像头扫码回调 ──
  const handleCameraScan = useCallback((barcodeValue: string) => {
    setBarcode(barcodeValue)
    setShowScanner(false)
    setTimeout(async () => {
      if (receiptId != null && barcodeValue.trim()) {
        setIsLoading(true)
        setPreview(null)
        setConfirmQty('')
        setConfirmError('')
        setSelectedMaterialId(null)
        setNewMaterialCode('')
        setNewMaterialName('')
        try {
          const res = await scanPreviewApi(receiptId, {
            barcode: barcodeValue.trim(),
            operator,
          })
          setPreview(res)
          setConfirmQty(String(res.quantity || 1))
          setEditMaterialName(res.material_name || '')
          setEditSpec(res.spec || '')
          setEditBatchNo(res.batch_no || '')
          setEditDateCode(res.date_code || '')
          if (res.candidates && res.candidates.length > 0) {
            setSelectedMaterialId(res.candidates[0].material_id)
          }
        } catch (e: any) {
          Alert.alert('扫描失败', e?.response?.data?.detail || '条码解析失败，请重试')
        } finally {
          setIsLoading(false)
        }
      }
    }, 100)
  }, [receiptId, operator])

  // ── 取消确认 ──
  const handleCancelConfirm = useCallback(() => {
    setPreview(null)
    setConfirmQty('')
    setConfirmError('')
    setSelectedMaterialId(null)
    setNewMaterialCode('')
    setNewMaterialName('')
    setEditMaterialName('')
    setEditSpec('')
    setEditBatchNo('')
    setEditDateCode('')
    setTimeout(() => barcodeRef.current?.focus(), 300)
  }, [])

  // ── 返回选择收料单 ──
  const goBackToList = useCallback(() => {
    setStep('select')
    setReceiptId(null)
    setReceiptNo('')
    setReceiptItems([])
    setPreview(null)
    loadReceipts()
  }, [loadReceipts])

  // ── 取消入库某项明细 ──
  const handleCancelItem = useCallback(async (item: ReceiptItem) => {
    if (receiptId == null) return
    Alert.alert(
      '取消入库',
      `确定取消 ${item.material_code || '--'} x ${item.quantity} 的入库吗？`,
      [
        { text: '取消', style: 'cancel' },
        {
          text: '确定取消',
          style: 'destructive',
          onPress: async () => {
            setIsLoading(true)
            try {
              const res = await cancelReceiptItemsApi(receiptId, {
                receipt_reel_ids: [item.id],
              })
              Alert.alert('已取消', res.message)
              loadReceiptItems(receiptId)
            } catch (e: any) {
              Alert.alert('取消失败', e?.response?.data?.detail || '请重试')
            } finally {
              setIsLoading(false)
            }
          },
        },
      ]
    )
  }, [receiptId, loadReceiptItems])

  const isAutoMatch = preview?.status === 'ok' && (!preview.candidates || preview.candidates.length === 0)
  const isPendingReview = preview?.status === 'pending_review' || (preview?.candidates && preview.candidates.length > 0)
  const isNewMaterial = preview?.status === 'new_material'

  // ═══════════════════════════════════════════
  //  选择收料单页
  // ═══════════════════════════════════════════
  if (step === 'select') {
    return (
      <View style={styles.container}>
        <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
          <Text style={styles.headerTitle}>收料入库</Text>
          <Text style={styles.headerSub}>选择或创建收料单，开始扫码入库</Text>
        </View>

        <View style={styles.operatorBadge}>
          <Text style={styles.operatorLabel}>操作员：</Text>
          <Text style={[styles.operatorValue, !operator.trim() && { color: Colors.danger }]}>
            {operator.trim() || '未设置'}
          </Text>
        </View>

        {/* 创建新收料单 */}
        <TouchableOpacity
          style={[styles.newReceiptBtn, !operator.trim() && styles.buttonDisabled]}
          onPress={createNewReceipt}
          disabled={!operator.trim() || isLoading}
        >
          {isLoading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <>
              <PlusIcon size={22} color="#fff" />
              <Text style={styles.newReceiptBtnText}>创建新收料单</Text>
            </>
          )}
        </TouchableOpacity>

        {/* 收料单列表 */}
        <View style={styles.listHeader}>
          <View style={styles.listHeaderLeft}>
            <ListIcon size={18} color={Colors.textSecondary} />
            <Text style={styles.listHeaderTitle}>草稿收料单</Text>
          </View>
          <TouchableOpacity onPress={loadReceipts} style={styles.refreshBtn}>
            <RefreshIcon size={18} color={Colors.primary} />
          </TouchableOpacity>
        </View>

        {loadingList ? (
          <ActivityIndicator style={{ marginTop: 40 }} size="large" color={Colors.primary} />
        ) : receipts.length === 0 ? (
          <View style={styles.emptyState}>
            <DocumentIcon size={48} color="#ccc" />
            <Text style={styles.emptyText}>暂无草稿收料单</Text>
            <Text style={styles.emptySubText}>点击上方按钮创建新收料单</Text>
          </View>
        ) : (
          <FlatList
            data={receipts}
            keyExtractor={(item) => String(item.id)}
            contentContainerStyle={{ padding: 12, paddingTop: 4 }}
            renderItem={({ item }) => (
              <TouchableOpacity style={styles.receiptCard} onPress={() => selectReceipt(item)}>
                <View style={styles.receiptCardLeft}>
                  <Text style={styles.receiptNo}>{item.receipt_no}</Text>
                  <Text style={styles.receiptMeta}>
                    制单人: {item.operator}  |  单号: #{item.id}
                  </Text>
                  {item.purchase_order_no ? (
                    <Text style={styles.receiptMeta}>采购单号: {item.purchase_order_no}</Text>
                  ) : null}
                </View>
                <View style={styles.receiptCardRight}>
                  <Text style={styles.receiptCount}>{item.items_count || 0}</Text>
                  <Text style={styles.receiptCountLabel}>项</Text>
                </View>
              </TouchableOpacity>
            )}
          />
        )}
      </View>
    )
  }

  // ═══════════════════════════════════════════
  //  扫码页
  // ═══════════════════════════════════════════
  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <View style={styles.headerRow}>
          <TouchableOpacity onPress={goBackToList} style={styles.backBtn}>
            <Text style={styles.backBtnText}>{'< '}</Text>
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={styles.headerTitle}>收料入库</Text>
            <Text style={styles.headerSub}>{receiptNo || `#${receiptId}`}</Text>
          </View>
        </View>
      </View>

      <ScrollView style={styles.scrollArea} contentContainerStyle={styles.scrollContent}>
        {/* 模式切换 */}
        <View style={styles.modeToggle}>
          <TouchableOpacity
            style={[styles.modeButton, !manualMode && styles.modeButtonActive]}
            onPress={() => { setManualMode(false); setTimeout(() => barcodeRef.current?.focus(), 200) }}
          >
            <ScanIcon size={18} color={!manualMode ? '#fff' : Colors.textSecondary} />
            <Text style={[styles.modeButtonText, !manualMode && styles.modeButtonTextActive]}> 扫码</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.modeButton, manualMode && styles.modeButtonActive]}
            onPress={() => { setManualMode(true); setBarcode('') }}
          >
            <PencilIcon size={18} color={manualMode ? '#fff' : Colors.textSecondary} />
            <Text style={[styles.modeButtonText, manualMode && styles.modeButtonTextActive]}> 手工</Text>
          </TouchableOpacity>
        </View>

        {/* 扫码模式 */}
        {!manualMode && (
          <View style={styles.scanSection}>
            <View style={styles.scanInputRow}>
              <TextInput
                ref={barcodeRef}
                style={[styles.input, styles.scanInputFlex]}
                placeholder="扫描客户条码"
                value={barcode}
                onChangeText={setBarcode}
                autoFocus
                onSubmitEditing={handleBarcodeSubmit}
              />
              <TouchableOpacity
                style={styles.cameraBtn}
                onPress={() => setShowScanner(true)}
              >
                <CameraIcon size={24} color="#fff" />
              </TouchableOpacity>
            </View>
            <TouchableOpacity
              style={[styles.button, !barcode.trim() && styles.buttonDisabled]}
              onPress={handleBarcodeSubmit}
              disabled={!barcode.trim() || isLoading}
            >
              {isLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>扫描识别</Text>}
            </TouchableOpacity>
          </View>
        )}

        {/* 手工录入模式 */}
        {manualMode && (
          <View style={styles.scanSection}>
            <Text style={styles.sectionLabel}>物料编码 *</Text>
            <TextInput style={styles.input} placeholder="输入物料编码" value={manualMaterialCode} onChangeText={setManualMaterialCode} />
            <Text style={styles.sectionLabel}>物料名称</Text>
            <TextInput style={styles.input} placeholder="输入物料名称" value={manualMaterialName} onChangeText={setManualMaterialName} />
            <Text style={styles.sectionLabel}>规格</Text>
            <TextInput style={styles.input} placeholder="如：0805" value={manualSpec} onChangeText={setManualSpec} />
            <View style={styles.qtyRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.sectionLabel}>数量 *</Text>
                <TextInput style={styles.input} placeholder="1" value={manualQty} onChangeText={setManualQty} keyboardType="numeric" />
              </View>
            </View>
            <Text style={styles.sectionLabel}>批次号</Text>
            <TextInput style={styles.input} placeholder="选填" value={manualBatch} onChangeText={setManualBatch} />
            <Text style={styles.sectionLabel}>生产周期</Text>
            <TextInput style={styles.input} placeholder="如：2401" value={manualDateCode} onChangeText={setManualDateCode} />
            <TouchableOpacity
              style={[styles.button, !manualMaterialCode.trim() && styles.buttonDisabled]}
              onPress={handleManualSubmit}
              disabled={!manualMaterialCode.trim() || isLoading}
            >
              {isLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>确认手工入库</Text>}
            </TouchableOpacity>
          </View>
        )}

        {/* 收料单详情列表 */}
        {receiptItems.length > 0 && (
          <>
            <Text style={styles.sectionTitle}>收料单明细 ({receiptItems.length})</Text>
            {receiptItems.map((item) => (
              <View key={item.id} style={styles.receiptItemCard}>
                <View style={styles.receiptItemRow}>
                  <View style={styles.receiptItemInfo}>
                    <Text style={styles.receiptItemCode}>{item.material_code || '--'}</Text>
                    <Text style={styles.receiptItemName} numberOfLines={1}>{item.material_name || ''}</Text>
                    <Text style={styles.receiptItemMeta}>
                      数量: {item.quantity} 盘
                      {item.barcode ? ` | ${item.barcode}` : ''}
                    </Text>
                  </View>
                  <TouchableOpacity
                    style={styles.cancelItemBtn}
                    onPress={() => handleCancelItem(item)}
                    disabled={isLoading}
                  >
                    <Text style={styles.cancelItemBtnText}>取消</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ))}
          </>
        )}
      </ScrollView>

      {/* 确认弹框 */}
      <Modal visible={preview != null} transparent animationType="fade" onRequestClose={handleCancelConfirm}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            {preview && (
              <>
                <Text style={styles.modalTitle}>
                  {isAutoMatch ? (
                    <><CheckIcon size={22} color={Colors.success} /> 确认入库</>
                  ) : isNewMaterial ? (
                    <><NewIcon size={22} color={Colors.info} /> 确认新料入库</>
                  ) : (
                    <><WarningIcon size={22} color={Colors.warning} /> 确认物料</>
                  )}
                </Text>

                <ScrollView style={styles.modalScroll} showsVerticalScrollIndicator={true}>
                  <View style={styles.modalInfo}>
                    <View style={styles.confidenceRow}>
                      <View style={styles.confidenceBadge}>
                        <Text style={styles.confidenceLabel}>匹配度</Text>
                        <Text style={[styles.confidenceValue, {
                          color: preview.confidence >= 0.8 ? Colors.success : preview.confidence >= 0.5 ? Colors.warning : Colors.danger
                        }]}>
                          {(preview.confidence * 100).toFixed(0)}%
                        </Text>
                      </View>
                      <View style={[styles.statusBadge, { backgroundColor: isAutoMatch ? Colors.success : isNewMaterial ? Colors.info : Colors.warning }]}>
                        <Text style={styles.statusBadgeText}>
                          {isAutoMatch ? '自动匹配' : isNewMaterial ? '新料号' : '待确认'}
                        </Text>
                      </View>
                    </View>

                    {preview.confidence > 0 && (
                      <View style={styles.confidenceBarOuter}>
                        <View style={[styles.confidenceBarInner, {
                          width: `${Math.min(preview.confidence * 100, 100)}%`,
                          backgroundColor: preview.confidence >= 0.8 ? Colors.success : preview.confidence >= 0.5 ? Colors.warning : Colors.danger,
                        }]} />
                      </View>
                    )}

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
                        <Text style={styles.fieldItemLabel}>物料名称 *</Text>
                        <TextInput
                          style={styles.fieldInput}
                          value={editMaterialName}
                          onChangeText={setEditMaterialName}
                          placeholder="输入物料名称"
                        />
                      </View>
                      <View style={styles.fieldItem}>
                        <Text style={styles.fieldItemLabel}>规格</Text>
                        <TextInput
                          style={styles.fieldInput}
                          value={editSpec}
                          onChangeText={setEditSpec}
                          placeholder="如：0805"
                        />
                      </View>
                      <View style={styles.fieldItem}>
                        <Text style={styles.fieldItemLabel}>批次号</Text>
                        <TextInput
                          style={styles.fieldInput}
                          value={editBatchNo}
                          onChangeText={setEditBatchNo}
                          placeholder="批次号"
                        />
                      </View>
                      <View style={styles.fieldItem}>
                        <Text style={styles.fieldItemLabel}>生产周期</Text>
                        <TextInput
                          style={styles.fieldInput}
                          value={editDateCode}
                          onChangeText={setEditDateCode}
                          placeholder="如：2401"
                        />
                      </View>
                      <View style={styles.fieldItem}>
                        <Text style={styles.fieldItemLabel}>数量</Text>
                        <Text style={styles.fieldItemValue}>{preview.quantity ?? '--'} 盘</Text>
                      </View>
                    </View>
                  </View>

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
                            <View style={[styles.candidateConfBadge, { backgroundColor: c.confidence >= 0.8 ? Colors.success : c.confidence >= 0.5 ? Colors.warning : Colors.danger }]}>
                              <Text style={styles.candidateConfText}>{(c.confidence * 100).toFixed(0)}%</Text>
                            </View>
                          </View>
                        </TouchableOpacity>
                      ))}
                    </View>
                  )}

                  {isNewMaterial && (
                    <View style={styles.candidateSection}>
                      <Text style={styles.candidateTitle}>确认为新料号：</Text>
                      <Text style={styles.fieldLabel}>料号编码</Text>
                      <TextInput style={styles.input} value={newMaterialCode} onChangeText={setNewMaterialCode} placeholder="输入料号编码" />
                      <Text style={styles.fieldLabel}>料号名称</Text>
                      <TextInput style={styles.input} value={newMaterialName} onChangeText={setNewMaterialName} placeholder="输入物料名称" />
                    </View>
                  )}

                  <View style={styles.qtySection}>
                    <Text style={styles.qtyLabel}>入库数量</Text>
                    <View style={styles.qtyRow}>
                      <TextInput style={styles.qtyInput} value={confirmQty} onChangeText={(v) => { setConfirmQty(v); setConfirmError('') }} keyboardType="numeric" editable={!isLoading} />
                      <Text style={styles.qtyUnit}>盘</Text>
                    </View>
                  </View>

                  {confirmError ? <Text style={styles.errorText}>{confirmError}</Text> : null}
                </ScrollView>

                <View style={styles.modalButtons}>
                  <TouchableOpacity style={[styles.modalButton, styles.cancelButton]} onPress={handleCancelConfirm} disabled={isLoading}>
                    <Text style={styles.cancelButtonText}>取消</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.modalButton, styles.confirmButton, (isLoading || (isPendingReview && !selectedMaterialId)) && styles.buttonDisabled]}
                    onPress={doConfirmScan}
                    disabled={isLoading || (isPendingReview && !selectedMaterialId)}
                  >
                    {isLoading ? <ActivityIndicator color="#fff" size="small" /> : <Text style={styles.confirmButtonText}>确认入库</Text>}
                  </TouchableOpacity>
                </View>
              </>
            )}
          </View>
        </View>
      </Modal>

      <BarcodeScanner visible={showScanner} onScan={handleCameraScan} onClose={() => setShowScanner(false)} title="扫码入库" />
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg },
  header: { backgroundColor: Colors.primary, paddingHorizontal: 16, paddingTop: 12, paddingBottom: 12 },
  headerRow: { flexDirection: 'row', alignItems: 'center' },
  backBtn: { marginRight: 8, paddingVertical: 4 },
  backBtnText: { color: '#fff', fontSize: 22, fontWeight: 'bold' },
  headerTitle: { fontSize: 20, fontWeight: 'bold', color: '#fff' },
  headerSub: { fontSize: 13, color: 'rgba(255,255,255,0.85)', marginTop: 2 },

  // 选择页
  operatorBadge: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 12, backgroundColor: Colors.card, marginHorizontal: 12, marginTop: 12, borderRadius: 8, elevation: 1, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.05, shadowRadius: 2 },
  operatorLabel: { fontSize: 15, color: Colors.textSecondary },
  operatorValue: { fontSize: 16, fontWeight: 'bold', color: Colors.primary },
  newReceiptBtn: { flexDirection: 'row', backgroundColor: Colors.primary, marginHorizontal: 12, marginTop: 12, padding: 16, borderRadius: 10, alignItems: 'center', justifyContent: 'center', elevation: 2, shadowColor: Colors.primary, shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.3, shadowRadius: 4 },
  newReceiptBtnText: { color: '#fff', fontSize: 17, fontWeight: 'bold', marginLeft: 8 },
  listHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingTop: 20, paddingBottom: 8 },
  listHeaderLeft: { flexDirection: 'row', alignItems: 'center' },
  listHeaderTitle: { fontSize: 16, fontWeight: '600', color: Colors.text, marginLeft: 6 },
  refreshBtn: { padding: 6 },
  emptyState: { alignItems: 'center', paddingTop: 60 },
  emptyText: { fontSize: 16, color: Colors.textSecondary, marginTop: 12 },
  emptySubText: { fontSize: 13, color: '#aaa', marginTop: 4 },
  receiptCard: { flexDirection: 'row', backgroundColor: Colors.card, padding: 14, borderRadius: 10, marginBottom: 8, elevation: 1, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.08, shadowRadius: 3, alignItems: 'center' },
  receiptCardLeft: { flex: 1 },
  receiptNo: { fontSize: 16, fontWeight: 'bold', color: Colors.text },
  receiptMeta: { fontSize: 13, color: Colors.textSecondary, marginTop: 2 },
  receiptCardRight: { alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.bg, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 8, marginLeft: 8 },
  receiptCount: { fontSize: 22, fontWeight: 'bold', color: Colors.primary },
  receiptCountLabel: { fontSize: 11, color: Colors.textSecondary, marginTop: -2 },

  // 扫码页
  scanSection: { padding: 16, backgroundColor: Colors.card, borderRadius: 12, margin: 12, elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 4 },
  scrollArea: { flex: 1 },
  scrollContent: { paddingBottom: 40 },
  input: { backgroundColor: '#fff', padding: 14, borderRadius: 8, marginBottom: 12, fontSize: 18, borderWidth: 1, borderColor: '#ddd' },
  button: { backgroundColor: Colors.primary, padding: 16, borderRadius: 8, alignItems: 'center', marginBottom: 12 },
  buttonDisabled: { opacity: 0.5 },
  buttonText: { color: '#fff', fontSize: 18, fontWeight: '600' },
  sectionTitle: { fontSize: 16, fontWeight: 'bold', color: Colors.text, marginHorizontal: 12, marginTop: 8, marginBottom: 8 },
  // 收料单明细
  receiptItemCard: { backgroundColor: Colors.card, borderRadius: 10, marginHorizontal: 12, marginBottom: 6, borderWidth: 1, borderColor: '#eee', overflow: 'hidden' },
  receiptItemRow: { flexDirection: 'row', alignItems: 'center', padding: 12 },
  receiptItemInfo: { flex: 1, marginRight: 8 },
  receiptItemCode: { fontSize: 15, fontWeight: 'bold', color: Colors.text },
  receiptItemName: { fontSize: 13, color: Colors.textSecondary, marginTop: 1 },
  receiptItemMeta: { fontSize: 12, color: Colors.textSecondary, marginTop: 2 },
  receiptItemSlot: { fontSize: 12, color: Colors.primary, marginTop: 1 },
  cancelItemBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 6, backgroundColor: '#fff1f0', borderWidth: 1, borderColor: '#ffa39e' },
  cancelItemBtnText: { fontSize: 13, fontWeight: '600', color: '#cf1322' },
  scanInputRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  scanInputFlex: { flex: 1, marginBottom: 0 },
  cameraBtn: { width: 50, height: 50, borderRadius: 8, backgroundColor: Colors.info, alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
  modeToggle: { flexDirection: 'row', backgroundColor: Colors.card, borderRadius: 8, margin: 12, marginBottom: 0, padding: 4, borderWidth: 1, borderColor: '#ddd' },
  modeButton: { flex: 1, paddingVertical: 10, borderRadius: 6, alignItems: 'center', flexDirection: 'row', justifyContent: 'center' },
  modeButtonActive: { backgroundColor: Colors.primary },
  modeButtonText: { fontSize: 15, fontWeight: '600', color: Colors.textSecondary },
  modeButtonTextActive: { color: '#fff' },
  sectionLabel: { fontSize: 14, color: Colors.textSecondary, fontWeight: '600', marginBottom: 4, marginTop: 4 },

  // Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  modalContent: { backgroundColor: '#fff', borderRadius: 16, padding: 20, width: '100%', maxWidth: 500, maxHeight: '90%' },
  modalScroll: { flexGrow: 0, maxHeight: '100%' },
  modalTitle: { fontSize: 22, fontWeight: 'bold', color: Colors.text, marginBottom: 16, textAlign: 'center' },
  modalInfo: { marginBottom: 12 },
  confidenceRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  confidenceBadge: { flexDirection: 'row', alignItems: 'baseline' },
  confidenceLabel: { fontSize: 14, color: Colors.textSecondary, marginRight: 6 },
  confidenceValue: { fontSize: 24, fontWeight: 'bold' },
  statusBadge: { paddingHorizontal: 12, paddingVertical: 4, borderRadius: 12 },
  statusBadgeText: { color: '#fff', fontSize: 13, fontWeight: '600' },
  confidenceBarOuter: { height: 6, backgroundColor: '#e8e8e8', borderRadius: 3, marginBottom: 14, overflow: 'hidden' },
  confidenceBarInner: { height: 6, borderRadius: 3 },
  fieldsGrid: { flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -6 },
  fieldItem: { width: '50%', paddingHorizontal: 6, marginBottom: 10 },
  fieldItemFull: { width: '100%' },
  fieldItemLabel: { fontSize: 12, color: Colors.textSecondary, marginBottom: 2 },
  fieldItemValue: { fontSize: 15, color: Colors.text },
  fieldItemValueBold: { fontSize: 17, color: Colors.text, fontWeight: 'bold' },
  fieldInput: { backgroundColor: '#fff', padding: 8, borderRadius: 6, fontSize: 15, color: Colors.text, borderWidth: 1, borderColor: '#ddd', marginTop: 2 },
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
  qtySection: { marginVertical: 12 },
  qtyLabel: { fontSize: 16, color: Colors.text, fontWeight: '600', marginBottom: 6 },
  qtyRow: { flexDirection: 'row', alignItems: 'center' },
  qtyInput: { backgroundColor: '#fff', padding: 12, borderRadius: 8, fontSize: 22, fontWeight: 'bold', borderWidth: 1, borderColor: '#ddd', width: 120, textAlign: 'center' },
  qtyUnit: { fontSize: 18, color: Colors.text, marginLeft: 8, fontWeight: '600' },
  errorText: { color: Colors.danger, fontSize: 15, textAlign: 'center', marginBottom: 8 },
  modalButtons: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 },
  modalButton: { flex: 1, padding: 16, borderRadius: 8, alignItems: 'center', justifyContent: 'center', minHeight: 52 },
  cancelButton: { backgroundColor: '#f0f0f0', marginRight: 8 },
  confirmButton: { backgroundColor: Colors.success, marginLeft: 8 },
  cancelButtonText: { fontSize: 18, color: Colors.textSecondary, fontWeight: '600' },
  confirmButtonText: { fontSize: 18, color: '#fff', fontWeight: 'bold' },
})
