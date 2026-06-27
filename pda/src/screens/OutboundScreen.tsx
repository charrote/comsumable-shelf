import React, { useState, useCallback } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, Alert,
  ActivityIndicator, ScrollView,
} from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import {
  listIssuesApi, getIssueDetailApi, calculateIssueApi, assignIssueApi,
  confirmPickApi, directOutboundApi, scanReelForDirectOutApi,
} from '../api'
import type {
  IssueOrderResponse, IssueDetailResponse, IssueCalculateResponse,
  IssueConfirmPickResponse, DirectOutResponse,
} from '../types/api'
import { useOperator } from '../hooks/useOperator'
import BarcodeScanner from '../components/BarcodeScanner'
import { DocumentIcon, PackageIcon, CameraIcon, CrossIcon, CheckCircleIcon } from '../components/Icons'

const Colors = {
  primary: '#0066CC', success: '#00AA55', warning: '#FF9900', danger: '#DD3333',
  info: '#3399CC', card: '#FFFFFF', bg: '#F5F7FA', text: '#1A1A1A', textSecondary: '#666666',
}

type Mode = 'bom' | 'direct'
type Step = 'select_mode' | 'bom_pick' | 'direct_scan'

export default function OutboundScreen() {
  const { operator } = useOperator()
  const insets = useSafeAreaInsets()
  const [mode, setMode] = useState<Mode>('bom')
  const [step, setStep] = useState<Step>('select_mode')
  const [isLoading, setIsLoading] = useState(false)
  const [showPickScanner, setShowPickScanner] = useState(false)
  const [showDirectScanner, setShowDirectScanner] = useState(false)

  // ── BOM Pick Flow ──
  const [issues, setIssues] = useState<IssueOrderResponse[]>([])
  const [selectedIssue, setSelectedIssue] = useState<IssueOrderResponse | null>(null)
  const [issueDetails, setIssueDetails] = useState<IssueDetailResponse[]>([])
  const [calcResult, setCalcResult] = useState<IssueCalculateResponse | null>(null)
  const [assignResult, setAssignResult] = useState<string>('')
  const [pickBarcode, setPickBarcode] = useState('')
  const [pickResult, setPickResult] = useState<IssueConfirmPickResponse | null>(null)

  // ── Direct Outbound Flow (whole-reel mode) ──
  const [directBarcode, setDirectBarcode] = useState('')
  const [directReelInfo, setDirectReelInfo] = useState<{
    reel_id: number; material_code: string; material_name?: string; quantity: number; shelf_code?: string
  } | null>(null)
  const [directResult, setDirectResult] = useState<DirectOutResponse | null>(null)

  // ── BOM: Load issue orders ──
  const loadIssues = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await listIssuesApi()
      setIssues(res?.data || [])
    } catch {
      // ignore
    } finally {
      setIsLoading(false)
    }
  }, [])

  // ── BOM: Select issue order ──
  const selectIssue = useCallback(async (issue: IssueOrderResponse) => {
    setIsLoading(true)
    try {
      const detail = await getIssueDetailApi(issue.id)
      setSelectedIssue(issue)
      setIssueDetails(detail.details || [])
      setCalcResult(null)
      setAssignResult('')
      setPickResult(null)

      // If already assigned/picking, the details already contain reel_assignments
      // from getIssueDetailApi — no need to re-calculate
      if (issue.status === 'assigned') {
        // Build a synthetic calc result from existing detail data
        const mats = issueDetails.map(d => ({
          material_id: d.material_id,
          material_code: d.material_code || '',
          material_name: d.material_name || '',
          required_qty: d.required_qty,
          available_qty: d.assigned_qty || 0,
          strategy: 'cached',
          reels_selected: (d.reel_assignments || []).map(ra => ({
            reel_id: ra.reel_id,
            quantity: ra.pick_quantity,
            last_in_time: new Date().toISOString(),
            shelf_slot_id: ra.shelf_slot_id || 0,
          })),
          total_selected: d.assigned_qty || 0,
          shortage: d.shortage || 0,
        }))
        setCalcResult({ issue_order_id: issue.id, calculated_at: new Date().toISOString(), strategy_used: 'cached', materials: mats })
      }
      setStep('bom_pick')
    } catch (e: any) {
      Alert.alert('错误', e?.response?.data?.detail || '加载出库单失败')
    } finally {
      setIsLoading(false)
    }
  }, [])

  // ── BOM: FIFO Calculate ──
  const handleCalculate = useCallback(async () => {
    if (!selectedIssue) return
    setIsLoading(true)
    try {
      const res = await calculateIssueApi(selectedIssue.id)
      setCalcResult(res)
      setIssueDetails(prev => prev.map(d => {
        const mat = res.materials.find(m => m.material_id === d.material_id)
        return mat ? { ...d, assigned_qty: mat.total_selected, shortage: mat.shortage } : d
      }))
      Alert.alert('计算完成', `策略: ${res.strategy_used}\n共 ${res.materials.length} 种物料`)
    } catch (e: any) {
      Alert.alert('计算失败', e?.response?.data?.detail || 'FIFO计算失败')
    } finally {
      setIsLoading(false)
    }
  }, [selectedIssue])

  // ── BOM: LED Assign ──
  const handleAssignLED = useCallback(async () => {
    if (!selectedIssue) return
    setIsLoading(true)
    try {
      const res = await assignIssueApi(selectedIssue.id)
      setAssignResult(`已生成 ${res.led_commands_created} 个亮灯指令`)
      Alert.alert('亮灯分配', `${res.message}\n共 ${res.led_commands_created} 个储位亮灯`)
    } catch (e: any) {
      Alert.alert('亮灯失败', e?.response?.data?.detail || 'LED分配失败')
    } finally {
      setIsLoading(false)
    }
  }, [selectedIssue])

  // ── BOM: Confirm Pick ──
  const handleConfirmPick = useCallback(async () => {
    if (!pickBarcode.trim() || !selectedIssue || !calcResult) return
    setIsLoading(true)
    try {
      // 由后端通过 barcode 匹配正确的 reel，前端不再传固定 reel_id
      const res = await confirmPickApi(selectedIssue.id, {
        barcode: pickBarcode.trim(),
        operator,
      })
      setPickResult(res)
      setPickBarcode('')

      if (res.all_picked) {
        Alert.alert('完成', '本出库单已全部拣料完成')
      }
    } catch (e: any) {
      Alert.alert('拣料失败', e?.response?.data?.detail || '请重试')
    } finally {
      setIsLoading(false)
    }
  }, [pickBarcode, selectedIssue, operator])

  // ── Direct Outbound: Scan Reel ──
  const handleDirectScan = useCallback(async () => {
    if (!directBarcode.trim()) return
    setIsLoading(true)
    try {
      const info = await scanReelForDirectOutApi(directBarcode.trim())
      setDirectReelInfo(info)
      setDirectResult(null)
    } catch (e: any) {
      Alert.alert('扫描失败', e?.response?.data?.detail || '未找到该料盘')
    } finally {
      setIsLoading(false)
    }
  }, [directBarcode])

  // ── Direct Outbound: Confirm (whole-reel) ──
  const handleDirectConfirm = useCallback(async () => {
    if (!directReelInfo) return
    setIsLoading(true)
    try {
      const res = await directOutboundApi(directReelInfo.reel_id, {
        operator,
        release_slot: true,
      })
      setDirectResult(res)
      Alert.alert('出库成功', `整盘出库完成\n盘 #${directReelInfo.reel_id}（数量 ${directReelInfo.quantity}）已全部出库`)
    } catch (e: any) {
      Alert.alert('出库失败', e?.response?.data?.detail || '请重试')
    } finally {
      setIsLoading(false)
    }
  }, [directReelInfo, operator])

  // ── BOM Pick: 摄像头扫码回调 ──
  const handlePickCameraScan = useCallback((barcodeValue: string) => {
    setPickBarcode(barcodeValue)
    setShowPickScanner(false)
    // 自动触发确认出库
    setTimeout(async () => {
      if (!barcodeValue.trim() || !selectedIssue) return
      setIsLoading(true)
      try {
        const res = await confirmPickApi(selectedIssue.id, {
          barcode: barcodeValue.trim(),
          operator,
        })
        setPickResult(res)
        if (res.all_picked) {
          Alert.alert('完成', '本出库单已全部拣料完成')
        }
      } catch (e: any) {
        Alert.alert('拣料失败', e?.response?.data?.detail || '请重试')
      } finally {
        setIsLoading(false)
      }
    }, 100)
  }, [selectedIssue, operator])

  // ── Direct Outbound: 摄像头扫码回调 ──
  const handleDirectCameraScan = useCallback((barcodeValue: string) => {
    setDirectBarcode(barcodeValue)
    setShowDirectScanner(false)
    // 自动触发查询料盘信息
    setTimeout(async () => {
      if (!barcodeValue.trim()) return
      setIsLoading(true)
      try {
        const info = await scanReelForDirectOutApi(barcodeValue.trim())
        setDirectReelInfo(info)
        setDirectResult(null)
      } catch (e: any) {
        Alert.alert('扫描失败', e?.response?.data?.detail || '未找到该料盘')
      } finally {
        setIsLoading(false)
      }
    }, 100)
  }, [])

  // Reset all
  const handleReset = () => {
    setStep('select_mode')
    setSelectedIssue(null)
    setIssueDetails([])
    setCalcResult(null)
    setAssignResult('')
    setPickResult(null)
    setPickBarcode('')
    setDirectReelInfo(null)
    setDirectBarcode('')
    setDirectResult(null)
  }

  // ── Mode Selection ──
  if (step === 'select_mode') {
    return (
      <View style={styles.container}>
        <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
          <Text style={styles.headerTitle}>扫码出库</Text>
          <Text style={styles.headerSub}>选择出库方式</Text>
        </View>
        <View style={styles.modeContainer}>
          <TouchableOpacity
            style={styles.modeCard}
            onPress={() => { setMode('bom'); setStep('bom_pick'); loadIssues() }}
          >
            <DocumentIcon size={36} color={Colors.primary} />
            <Text style={styles.modeTitle}>按料单出库</Text>
            <Text style={styles.modeDesc}>选择发料单 → FIFO计算 → LED亮灯 → 扫码取料</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.modeCard}
            onPress={() => { setMode('direct'); setStep('direct_scan') }}
          >
            <PackageIcon size={36} color={Colors.primary} />
            <Text style={styles.modeTitle}>单独出料</Text>
            <Text style={styles.modeDesc}>扫描料盘条码 → 直接出库（退料/废料/紧急）</Text>
          </TouchableOpacity>
        </View>
      </View>
    )
  }

  // ── BOM Pick ──
  if (step === 'bom_pick') {
    return (
      <View style={styles.container}>
        <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
          <TouchableOpacity onPress={handleReset}>
            <Text style={styles.backBtn}>← 返回</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle}>按料单出库</Text>
          <Text style={styles.headerSub}>
            {selectedIssue ? `单号: ${selectedIssue.order_no}` : '选择发料单'}
          </Text>
        </View>

        <ScrollView style={styles.scrollArea} contentContainerStyle={styles.scrollContent}>
          {/* Issue Orders List */}
          {!selectedIssue && (
            <View style={styles.card}>
              <Text style={styles.stepTitle}>选择发料单</Text>
              <TouchableOpacity style={styles.linkBtn} onPress={loadIssues}>
                <Text style={styles.linkText}>刷新发料单列表</Text>
              </TouchableOpacity>
              {isLoading ? <ActivityIndicator style={{ marginVertical: 16 }} /> : null}
              {issues.length === 0 && !isLoading ? (
                <Text style={styles.emptyText}>暂无待处理的发料单</Text>
              ) : (
                issues.map(issue => (
                  <TouchableOpacity key={issue.id} style={styles.issueCard} onPress={() => selectIssue(issue)}>
                    <View style={styles.issueHeader}>
                      <Text style={styles.issueNo}>#{issue.order_no}</Text>
                      <View style={[styles.statusBadge, {
                        backgroundColor: 
                          issue.status === 'completed' ? Colors.success :
                          issue.status === 'picking' ? Colors.warning : Colors.info
                      }]}>
                        <Text style={styles.statusText}>{issue.status}</Text>
                      </View>
                    </View>
                    <Text style={styles.issueProduct}>{issue.product_name || issue.product_code || ''}</Text>
                    <Text style={styles.issueMeta}>
                      {issue.detail_count ?? 0} 项物料
                      {issue.production_quantity ? ` × ${issue.production_quantity} 套` : ''}
                    </Text>
                  </TouchableOpacity>
                ))
              )}
            </View>
          )}

          {/* Issue Detail & Operations */}
          {selectedIssue && (
            <>
              {/* Issue Info */}
              <View style={styles.card}>
                <Text style={styles.stepTitle}>发料单: {selectedIssue.order_no}</Text>
                <Text style={styles.issueStatusText}>状态: {selectedIssue.status}</Text>
                <Text style={styles.issueProduct}>{selectedIssue.product_name || ''}</Text>

                {/* Calculate & Assign */}
                <View style={styles.actionRow}>
                  <TouchableOpacity
                    style={[styles.actionBtn, { backgroundColor: Colors.info }]}
                    onPress={handleCalculate}
                    disabled={isLoading}
                  >
                    {isLoading && !calcResult ? <ActivityIndicator color="#fff" size="small" /> : null}
                    <Text style={styles.actionBtnText}>FIFO 计算</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.actionBtn, { backgroundColor: Colors.warning }]}
                    onPress={handleAssignLED}
                    disabled={isLoading || !calcResult}
                  >
                    {isLoading && !assignResult ? <ActivityIndicator color="#fff" size="small" /> : null}
                    <Text style={styles.actionBtnText}>LED 亮灯</Text>
                  </TouchableOpacity>
                </View>
                {assignResult ? <Text style={styles.assignText}>{assignResult}</Text> : null}
              </View>

              {/* Calculation Results */}
              {calcResult && (
                <View style={styles.card}>
                  <Text style={styles.stepTitle}>FIFO 计算结果</Text>
                  <Text style={styles.hint}>策略: {calcResult.strategy_used}</Text>
                  {calcResult.materials.map((mat, i) => (
                    <View key={i} style={styles.calcItem}>
                      <View style={styles.calcHeader}>
                        <Text style={styles.calcCode}>{mat.material_code}</Text>
                        <Text style={styles.calcName}>{mat.material_name}</Text>
                      </View>
                      <View style={styles.calcRow}>
                        <Text style={styles.calcLabel}>需求: {mat.required_qty}</Text>
                        <Text style={styles.calcLabel}>可用: {mat.available_qty}</Text>
                        <Text style={[styles.calcLabel, mat.shortage > 0 && { color: Colors.danger }]}>
                          {mat.shortage > 0 ? `短缺: ${mat.shortage}` : `已分配: ${mat.total_selected}`}
                        </Text>
                      </View>
                      {mat.reels_selected.map((reel, j) => (
                        <View key={j} style={styles.reelRow}>
                          <Text style={styles.reelText}>盘 #{reel.reel_id}</Text>
                          <Text style={styles.reelText}>取 {reel.quantity}</Text>
                          <Text style={styles.reelText}>储位 {reel.shelf_slot_id}</Text>
                        </View>
                      ))}
                    </View>
                  ))}
                </View>
              )}

              {/* Scanning for Pick */}
              {calcResult && (
                <View style={styles.card}>
                  <Text style={styles.stepTitle}>扫码取料</Text>
                  <Text style={styles.hint}>扫描亮灯储位上的料盘条码</Text>
                  <View style={styles.scanInputRow}>
                    <TextInput
                      style={[styles.input, styles.scanInputFlex]}
                      placeholder="扫描料盘条码"
                      value={pickBarcode}
                      onChangeText={setPickBarcode}
                      autoFocus
                      showSoftInputOnFocus={false}
                    />
                    <TouchableOpacity
                    style={styles.cameraBtn}
                    onPress={() => setShowPickScanner(true)}
                  >
                    <CameraIcon size={24} color="#fff" />
                    </TouchableOpacity>
                  </View>
                  <TouchableOpacity
                    style={[styles.button, styles.confirmButton, !pickBarcode.trim() && styles.buttonDisabled]}
                    onPress={handleConfirmPick}
                    disabled={!pickBarcode.trim() || isLoading}
                  >
                    {isLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>确认出库</Text>}
                  </TouchableOpacity>

                  {pickResult && (
                    <View style={[styles.resultBox, pickResult.all_picked ? styles.resultSuccess : styles.resultInfo]}>
                      <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 4 }}>
                        {pickResult.all_picked
                          ? <CheckCircleIcon size={18} color="#00AA55" />
                          : <PackageIcon size={18} color="#0066CC" />}
                        <Text style={[styles.resultTitle, { marginBottom: 0, marginLeft: 6 }]}>
                          {pickResult.all_picked ? '已完成' : '已拣料'}
                        </Text>
                      </View>
                      <Text>已拣: {pickResult.picked_qty} / 剩余: {pickResult.remaining_qty}</Text>
                      {pickResult.cleared_leds.length > 0 && (
                        <Text>已清除 {pickResult.cleared_leds.length} 个亮灯</Text>
                      )}
                    </View>
                  )}
                </View>
              )}
            </>
          )}
        </ScrollView>
      </View>
    )
  }

  // ── Direct Outbound ──
  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <TouchableOpacity onPress={handleReset}>
          <Text style={styles.backBtn}>← 返回</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>单独出料</Text>
        <Text style={styles.headerSub}>扫描料盘 → 确认出库</Text>
      </View>

      <ScrollView style={styles.scrollArea} contentContainerStyle={styles.scrollContent}>
        <View style={styles.card}>
          <Text style={styles.stepTitle}>扫描料盘</Text>
          <View style={styles.scanInputRow}>
            <TextInput
              style={[styles.input, styles.scanInputFlex]}
              placeholder="扫描料盘条码"
              value={directBarcode}
              onChangeText={setDirectBarcode}
              autoFocus
              showSoftInputOnFocus={false}
              onSubmitEditing={handleDirectScan}
            />
            <TouchableOpacity
                    style={styles.cameraBtn}
                    onPress={() => setShowDirectScanner(true)}
                  >
                    <CameraIcon size={24} color="#fff" />
            </TouchableOpacity>
          </View>
          <TouchableOpacity
            style={[styles.button, !directBarcode.trim() && styles.buttonDisabled]}
            onPress={handleDirectScan}
            disabled={!directBarcode.trim() || isLoading}
          >
            {isLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>扫描识别</Text>}
          </TouchableOpacity>
        </View>

        {directReelInfo && (
          <View style={styles.card}>
            <Text style={styles.stepTitle}>料盘信息（整盘出库）</Text>
            <View style={styles.reelInfoCard}>
              <Text style={styles.reelInfoLabel}>Reel #: {directReelInfo.reel_id}</Text>
              <Text style={styles.reelInfoText}>物料: {directReelInfo.material_code}</Text>
              <Text style={styles.reelInfoText}>{directReelInfo.material_name}</Text>
              <Text style={styles.reelInfoText}>数量: {directReelInfo.quantity}</Text>
              {directReelInfo.shelf_code && (
                <Text style={styles.reelInfoText}>储位: {directReelInfo.shelf_code}</Text>
              )}
            </View>

            <Text style={{ color: '#FF9900', fontSize: 14, marginBottom: 12, textAlign: 'center' }}>
              出库以整盘为单位，确认后将整盘出库
            </Text>

            <TouchableOpacity
              style={[styles.button, styles.confirmButton]}
              onPress={handleDirectConfirm}
              disabled={isLoading}
            >
              {isLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>确认整盘出库</Text>}
            </TouchableOpacity>

              {directResult && (
                  <View style={[styles.resultBox, directResult.status === 'ok' ? styles.resultSuccess : styles.resultError]}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 4 }}>
                      {directResult.status === 'ok'
                        ? <CheckCircleIcon size={18} color="#00AA55" />
                        : <CrossIcon size={18} color="#DD3333" />}
                      <Text style={[styles.resultTitle, { marginBottom: 0, marginLeft: 6 }]}>
                        {directResult.status === 'ok' ? '出库成功' : '出库失败'}
                      </Text>
                    </View>
                <Text>出库前: {directResult.quantity_before} → 出库后: {directResult.quantity_after}</Text>
                <Text>储位释放: {directResult.slot_released ? '是' : '否'}</Text>
                <Text>{directResult.message}</Text>
              </View>
            )}
          </View>
        )}
      </ScrollView>

      {/* 摄像头扫码 - BOM 取料 */}
      <BarcodeScanner
        visible={showPickScanner}
        onScan={handlePickCameraScan}
        onClose={() => setShowPickScanner(false)}
        title="扫码取料"
      />
      {/* 摄像头扫码 - 单独出料 */}
      <BarcodeScanner
        visible={showDirectScanner}
        onScan={handleDirectCameraScan}
        onClose={() => setShowDirectScanner(false)}
        title="扫码出料"
      />
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg },
  header: { backgroundColor: Colors.primary, paddingHorizontal: 16, paddingTop: 12, paddingBottom: 12 },
  backBtn: { color: '#fff', fontSize: 16, marginBottom: 4 },
  headerTitle: { fontSize: 20, fontWeight: 'bold', color: '#fff' },
  headerSub: { fontSize: 13, color: 'rgba(255,255,255,0.85)', marginTop: 2 },
  modeContainer: { padding: 16, gap: 12 },
  modeCard: { backgroundColor: Colors.card, borderRadius: 12, padding: 20, elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 4 },
  modeTitle: { fontSize: 20, fontWeight: 'bold', color: Colors.text },
  modeDesc: { fontSize: 14, color: Colors.textSecondary, marginTop: 4 },
  scrollArea: { flex: 1 },
  scrollContent: { padding: 12, paddingBottom: 40 },
  card: { backgroundColor: Colors.card, borderRadius: 12, padding: 16, marginBottom: 12, elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 4 },
  stepTitle: { fontSize: 18, fontWeight: 'bold', color: Colors.text, marginBottom: 8 },
  hint: { fontSize: 14, color: Colors.textSecondary, marginBottom: 8 },
  input: { backgroundColor: '#fff', padding: 14, borderRadius: 8, marginBottom: 12, fontSize: 18, borderWidth: 1, borderColor: '#ddd' },
  button: { backgroundColor: Colors.primary, padding: 16, borderRadius: 8, alignItems: 'center', marginBottom: 8 },
  confirmButton: { backgroundColor: Colors.success },
  buttonDisabled: { opacity: 0.5 },
  buttonText: { color: '#fff', fontSize: 18, fontWeight: '600' },
  linkBtn: { alignItems: 'center', marginVertical: 4 },
  linkText: { color: Colors.primary, fontSize: 15 },
  emptyText: { textAlign: 'center', color: Colors.textSecondary, fontSize: 16, marginVertical: 20 },
  scanInputRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  scanInputFlex: { flex: 1, marginBottom: 0 },
  cameraBtn: { width: 50, height: 50, borderRadius: 8, backgroundColor: Colors.info, alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
  previewLabel: { fontSize: 15, color: Colors.textSecondary, fontWeight: '600', marginBottom: 4, marginTop: 8 },
  issueCard: { padding: 14, borderRadius: 8, borderWidth: 1, borderColor: '#eee', marginBottom: 8 },
  issueHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  issueNo: { fontSize: 16, fontWeight: 'bold', color: Colors.text },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4 },
  statusText: { fontSize: 12, color: '#fff', fontWeight: '600' },
  issueProduct: { fontSize: 14, color: Colors.textSecondary, marginTop: 4 },
  issueMeta: { fontSize: 13, color: Colors.textSecondary, marginTop: 2 },
  issueStatusText: { fontSize: 14, color: Colors.textSecondary, marginBottom: 8 },
  actionRow: { flexDirection: 'row', gap: 8, marginTop: 8 },
  actionBtn: { flex: 1, paddingVertical: 12, borderRadius: 8, alignItems: 'center', flexDirection: 'row', justifyContent: 'center' },
  actionBtnText: { color: '#fff', fontSize: 15, fontWeight: '600', marginLeft: 4 },
  assignText: { textAlign: 'center', color: Colors.info, fontSize: 14, marginTop: 6 },
  calcItem: { borderTopWidth: 1, borderTopColor: '#eee', paddingTop: 8, marginTop: 8 },
  calcHeader: { marginBottom: 4 },
  calcCode: { fontSize: 15, fontWeight: 'bold', color: Colors.text },
  calcName: { fontSize: 13, color: Colors.textSecondary },
  calcRow: { flexDirection: 'row', gap: 12, marginBottom: 4 },
  calcLabel: { fontSize: 13, color: Colors.textSecondary },
  reelRow: { flexDirection: 'row', gap: 8, marginVertical: 2, paddingLeft: 8 },
  reelText: { fontSize: 13, color: Colors.text },
  resultBox: { borderRadius: 8, padding: 12, marginTop: 8 },
  resultSuccess: { backgroundColor: '#f0fff4', borderWidth: 1, borderColor: Colors.success },
  resultInfo: { backgroundColor: '#e6f0ff', borderWidth: 1, borderColor: Colors.primary },
  resultError: { backgroundColor: '#fff1f0', borderWidth: 1, borderColor: Colors.danger },
  resultTitle: { fontSize: 16, fontWeight: 'bold', color: Colors.text, marginBottom: 4 },
  reelInfoCard: { backgroundColor: '#f0f5ff', borderRadius: 8, padding: 12, marginBottom: 8 },
  reelInfoLabel: { fontSize: 16, fontWeight: 'bold', color: Colors.text },
  reelInfoText: { fontSize: 15, color: Colors.textSecondary, marginTop: 2 },
})
