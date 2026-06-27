import React, { useState, useCallback, useRef, useEffect } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, Alert,
  ScrollView, ActivityIndicator,
} from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import {
  scanShelvingReelApi, bindShelvingSlotApi,
  scanShelvingSlotApi, loadBaseUrl,
} from '../api'
import type { ShelvingScanSlotResponse } from '../types/api'
import { WebSocketHelper, type ReelBoundEvent } from '../utils/websocket'
import BarcodeScanner from '../components/BarcodeScanner'
import { CameraIcon } from '../components/Icons'

const C = {
  primary: '#0066CC', success: '#00AA55', warning: '#FF9900', danger: '#DD3333',
  info: '#3399CC', card: '#FFFFFF', bg: '#F5F7FA', text: '#1A1A1A', textSecondary: '#666666',
}

type Mode = 'smart' | 'manual'
type SmartPhase = 'scan' | 'waiting' | 'bound' | 'timeout'

export default function ShelvingScreen() {
  const insets = useSafeAreaInsets()

  // ── Mode ──
  const [mode, setMode] = useState<Mode>('smart')

  // ── Reel Info (both modes) ──
  const [barcode, setBarcode] = useState('')
  const [reelId, setReelId] = useState<number | null>(null)
  const [materialCode, setMaterialCode] = useState('')
  const [materialName, setMaterialName] = useState('')
  const [reelQty, setReelQty] = useState(0)
  const [isScanned, setIsScanned] = useState(false)
  const [isAlreadyBound, setIsAlreadyBound] = useState(false)

  // ── Smart: callback-driven binding ──
  const [smartPhase, setSmartPhase] = useState<SmartPhase>('scan')
  const [boundInfo, setBoundInfo] = useState<ReelBoundEvent | null>(null)
  const wsRef = useRef<WebSocketHelper | null>(null)
  const reelIdRef = useRef<number | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const baseUrlRef = useRef<string>('')

  // ── Manual: slot barcode ──
  const [slotBarcode, setSlotBarcode] = useState('')
  const [scannedSlot, setScannedSlot] = useState<ShelvingScanSlotResponse | null>(null)

  // ── UI state ──
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [resultMsg, setResultMsg] = useState('')
  const [showScanner, setShowScanner] = useState(false)
  const [scannerMode, setScannerMode] = useState<'reel' | 'slot'>('reel')

  // Sync refs
  useEffect(() => { reelIdRef.current = reelId }, [reelId])

  // Load base URL for WebSocket
  useEffect(() => {
    loadBaseUrl().then(url => { baseUrlRef.current = url })
  }, [])

  // Cleanup WS on unmount
  useEffect(() => () => {
    wsRef.current?.disconnect()
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
  }, [])

  // ── WS connect for smart mode ──
  const connectWs = useCallback(() => {
    if (!baseUrlRef.current) return
    wsRef.current?.disconnect()

    const ws = new WebSocketHelper(baseUrlRef.current, {
      onReelBound: (data) => {
        // 只处理当前扫描的 reel（避免多个 PDA 串）
        if (data.reel_id === reelIdRef.current) {
          setBoundInfo(data)
          setSmartPhase('bound')
          if (timeoutRef.current) clearTimeout(timeoutRef.current)
        }
      },
      onConnected: () => {
        // WS 已连接，静默等待回调
      },
    })
    ws.connect()
    wsRef.current = ws
  }, [])

  // ── Scan Reel (both modes) ──
  const handleScanReel = useCallback(async (code?: string) => {
    const sc = (code || barcode).trim()
    if (!sc) return
    setIsLoading(true)
    setResultMsg('')
    try {
      const res = await scanShelvingReelApi(sc)
      setReelId(res.reel_id)
      setMaterialCode(res.material_code)
      setMaterialName(res.material_name || '')
      setReelQty(res.quantity)
      setIsScanned(true)

      if (res.status === 'already_bound') {
        setIsAlreadyBound(true)
        setResultMsg(`该料盘已上架至 ${res.shelf_code || ''}/${res.slot_code || ''}`)
        setSmartPhase('bound')
      } else {
        setIsAlreadyBound(false)
        if (mode === 'smart') {
          // 智能模式：连接 WS 等待回调自动绑定
          setSmartPhase('waiting')
          setBoundInfo(null)
          connectWs()
          // 60 秒超时兜底
          timeoutRef.current = setTimeout(() => {
            setSmartPhase('timeout')
          }, 60000)
        }
      }
    } catch (e: any) {
      Alert.alert('扫描失败', e?.response?.data?.detail || '请检查条码')
    } finally {
      setIsLoading(false)
    }
  }, [barcode, mode, connectWs])

  const handleCamReel = useCallback((v: string) => {
    setBarcode(v)
    setShowScanner(false)
    handleScanReel(v)
  }, [handleScanReel])

  // ── Manual: Scan Slot Barcode ──
  const handleScanSlot = useCallback(async (code?: string) => {
    const sc = (code || slotBarcode).trim()
    if (!sc) return
    setIsLoading(true)
    try {
      const res = await scanShelvingSlotApi(sc)
      if (res.status === 'occupied') {
        Alert.alert('储位被占用', res.message)
        return
      }
      setScannedSlot(res)
    } catch (e: any) {
      Alert.alert('扫描失败', e?.response?.data?.detail || '请检查储位条码')
    } finally {
      setIsLoading(false)
    }
  }, [slotBarcode])

  const handleCamSlot = useCallback((v: string) => {
    setSlotBarcode(v)
    setShowScanner(false)
    handleScanSlot(v)
  }, [handleScanSlot])

  const openCam = useCallback((mode: 'reel' | 'slot') => {
    setScannerMode(mode)
    setShowScanner(true)
  }, [])

  const handleCamScan = useCallback((v: string) => {
    scannerMode === 'reel' ? handleCamReel(v) : handleCamSlot(v)
  }, [scannerMode, handleCamReel, handleCamSlot])

  // ── Manual: Save ──
  const handleSave = useCallback(async () => {
    if (reelId == null || scannedSlot == null) return
    setIsSaving(true)
    try {
      const res = await bindShelvingSlotApi({
        reel_id: reelId,
        shelf_id: scannedSlot.shelf_id,
        shelf_slot_id: scannedSlot.shelf_slot_id,
      })
      setResultMsg(`上架成功!\n料架: ${res.shelf_code}\n储位: ${res.slot_code}`)
      setSmartPhase('bound')
    } catch (e: any) {
      Alert.alert('上架失败', e?.response?.data?.detail || '请重试')
    } finally {
      setIsSaving(false)
    }
  }, [reelId, scannedSlot])

  // ── Reset ──
  const handleReset = useCallback(() => {
    wsRef.current?.disconnect()
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    setBarcode('')
    setReelId(null)
    setMaterialCode('')
    setMaterialName('')
    setReelQty(0)
    setIsScanned(false)
    setIsAlreadyBound(false)
    setSmartPhase('scan')
    setBoundInfo(null)
    setScannedSlot(null)
    setSlotBarcode('')
    setResultMsg('')
  }, [])

  const switchMode = useCallback((m: Mode) => {
    handleReset()
    setMode(m)
  }, [handleReset])

  // ── Computed ──
  const showSuccess = smartPhase === 'bound' || isAlreadyBound

  // ── Render ──
  return (
    <View style={styles.container}>
      {/* ──── Header ──── */}
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <Text style={styles.headerTitle}>料盘上架</Text>
        <Text style={styles.headerSub}>
          {mode === 'smart' ? '智能料架 · 放入即自动绑定' : '手动上架 · 扫码绑储位'}
        </Text>
      </View>

      {/* ──── Mode Switch ──── */}
      <View style={styles.modeBar}>
        {(['smart', 'manual'] as Mode[]).map(m => (
          <TouchableOpacity
            key={m}
            style={[styles.modeTab, mode === m && styles.modeTabActive]}
            onPress={() => switchMode(m)}
          >
            <Text style={[styles.modeTabText, mode === m && styles.modeTabTextActive]}>
              {m === 'smart' ? '智能料架' : '手动上架'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollInner}>
        {/* ═══════════ Panel I ═══════════ */}
        <View style={[styles.panel, isScanned && !showSuccess && styles.panelActive]}>
          <PanelHeader
            num="I" title="扫描料盘"
            done={isScanned && !showSuccess}
            right={isScanned ? (
              <TouchableOpacity onPress={handleReset}>
                <Text style={styles.link}>重新扫描</Text>
              </TouchableOpacity>
            ) : undefined}
          />
          {!isScanned ? (
            <>
              <Text style={styles.hint}>扫描收料后打印的内部标签条码</Text>
              <ScanRow
                placeholder="扫描料盘条码"
                value={barcode}
                onChange={setBarcode}
                onSubmit={() => handleScanReel()}
                onCamera={() => openCam('reel')}
              />
            </>
          ) : (
            <View style={styles.reelCard}>
              <View style={styles.reelHd}>
                <Text style={styles.reelId}>Reel #{reelId}</Text>
                {!showSuccess && <Text style={styles.reelTag}>待上架</Text>}
              </View>
              <InfoRow label="物料编码" value={materialCode} />
              {materialName ? <InfoRow label="物料名称" value={materialName} /> : null}
              <InfoRow label="数量" value={`${reelQty}`} />
            </View>
          )}
        </View>

        {/* ═══════════ Panel II ═══════════ */}
        {mode === 'smart' ? (
          /* ── Smart Mode: Callback-driven ── */
          <View style={[styles.panel, showSuccess && styles.panelDone]}>
            <PanelHeader
              num="II" title="储位识别"
              done={showSuccess}
              right={<Text style={styles.modeTag}>等待回调</Text>}
            />
            {!isScanned ? (
              <Placeholder icon="①" text="请先扫描料盘" />
            ) : isAlreadyBound ? (
              <Placeholder icon="✓" text="料盘已上架，无需重复操作" />
            ) : smartPhase === 'waiting' ? (
              <View style={styles.waitBox}>
                <ActivityIndicator size="large" color={C.primary} />
                <Text style={styles.waitTitle}>等待放入料架...</Text>
                <Text style={styles.waitHint}>
                  请将料盘放入任意料架的空储位
                </Text>
                <Text style={styles.waitSub}>
                  传感器检测到放入后将自动绑定
                </Text>
                {wsRef.current?.connected ? (
                  <Text style={styles.wsStatus}>● 已连接</Text>
                ) : (
                  <Text style={[styles.wsStatus, { color: C.warning }]}>⟳ 连接中...</Text>
                )}
              </View>
            ) : smartPhase === 'timeout' ? (
              <Placeholder icon="⏱" text="检测超时">
                <Text style={styles.timeoutHint}>
                  传感器未检测到放入，请确认料架通信正常
                </Text>
                <View style={styles.timeoutActions}>
                  <TouchableOpacity style={styles.retry} onPress={() => {
                    setSmartPhase('waiting')
                    connectWs()
                    timeoutRef.current = setTimeout(() => setSmartPhase('timeout'), 60000)
                  }}>
                    <Text style={styles.retryText}>重试</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.retryOutline} onPress={() => switchMode('manual')}>
                    <Text style={styles.retryOutlineText}>切换手动模式</Text>
                  </TouchableOpacity>
                </View>
              </Placeholder>
            ) : smartPhase === 'bound' && boundInfo ? (
              <SlotCard
                shelfCode={boundInfo.shelf_code}
                slotCode={boundInfo.slot_code}
              />
            ) : (
              <Placeholder icon="⟳" text="准备就绪" />
            )}
          </View>
        ) : (
          /* ── Manual Mode: Slot barcode scan ── */
          <View style={[styles.panel, scannedSlot != null && styles.panelDone]}>
            <PanelHeader
              num="II" title="扫描储位"
              done={scannedSlot != null}
              right={<Text style={styles.modeTag}>扫码</Text>}
            />
            {!isScanned ? (
              <Placeholder icon="①" text="请先扫描料盘" />
            ) : isAlreadyBound ? (
              <Placeholder icon="✓" text="料盘已上架，无需重复操作" />
            ) : scannedSlot ? (
              <SlotCard
                shelfCode={scannedSlot.shelf_code}
                slotCode={scannedSlot.slot_code}
              />
            ) : (
              <>
                <Text style={styles.hint}>扫描料架储位上粘贴的条码标签</Text>
                <ScanRow
                  placeholder="扫描储位条码 (如 A1A05)"
                  value={slotBarcode}
                  onChange={setSlotBarcode}
                  onSubmit={() => handleScanSlot()}
                  onCamera={() => openCam('slot')}
                />
              </>
            )}
          </View>
        )}

        {/* ═══════════ Panel III ═══════════ */}
        <View style={[styles.panel, showSuccess && styles.panelDone]}>
          <PanelHeader
            num="III" title="确认上架"
            right={showSuccess ? <Text style={styles.tagDone}>完成</Text> : undefined}
          />
          {showSuccess ? (
            <View style={styles.doneBox}>
              <Text style={styles.doneIcon}>{isAlreadyBound ? 'ℹ️' : '✅'}</Text>
              <Text style={styles.doneTitle}>
                {isAlreadyBound ? '料盘已上架' : '上架完成'}
              </Text>
              <Text style={styles.doneMsg}>{resultMsg || (
                boundInfo
                  ? `料架: ${boundInfo.shelf_code}\n储位: ${boundInfo.slot_code}`
                  : ''
              )}</Text>
              <TouchableOpacity
                style={[styles.btn, { backgroundColor: C.success, paddingHorizontal: 40 }]}
                onPress={handleReset}
              >
                <Text style={styles.btnText}>继续上架</Text>
              </TouchableOpacity>
            </View>
          ) : mode === 'manual' ? (
            <>
              <TouchableOpacity
                style={[
                  styles.btn,
                  (!isScanned || scannedSlot == null) && styles.btnDisabled,
                  (isScanned && scannedSlot != null) && { backgroundColor: C.success },
                ]}
                onPress={handleSave}
                disabled={!isScanned || scannedSlot == null || isSaving}
              >
                {isSaving ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={[styles.btnText, (isScanned && scannedSlot != null) && { fontWeight: '700', fontSize: 18 }]}>
                    {!isScanned ? '请先扫描料盘'
                    : scannedSlot == null ? '请扫描储位条码'
                    : '保存'}
                  </Text>
                )}
              </TouchableOpacity>
              <StepHint
                text={
                  !isScanned ? '步骤 1/2: 扫描料盘条码'
                  : scannedSlot == null ? '步骤 2/2: 扫描储位条码'
                  : '✓ 点击「保存」完成上架'
                }
                done={isScanned && scannedSlot != null}
              />
            </>
          ) : (
            /* Smart mode waiting */
            <View style={styles.waitBox}>
              <Text style={styles.waitSub}>
                {smartPhase === 'scan' ? '扫描料盘后放入料架即可自动完成'
                : smartPhase === 'waiting' ? '放入后请稍候，系统自动绑定'
                : ''}
              </Text>
            </View>
          )}
        </View>
        <View style={{ height: 40 }} />
      </ScrollView>

      <BarcodeScanner
        visible={showScanner}
        onScan={handleCamScan}
        onClose={() => setShowScanner(false)}
        title={scannerMode === 'reel' ? '扫码料盘' : '扫码储位'}
      />
    </View>
  )
}

// ── Helper Components ──

function PanelHeader({ num, title, done, right }: {
  num: string; title: string; done?: boolean; right?: React.ReactNode
}) {
  return (
    <View style={styles.ph}>
      <View style={styles.phRow}>
        <View style={[styles.badge, done ? styles.badgeDone : styles.badgePending]}>
          <Text style={styles.badgeText}>{num}</Text>
        </View>
        <Text style={styles.panelTitle}>{title}</Text>
      </View>
      {right}
    </View>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.irow}>
      <Text style={styles.ik}>{label}</Text>
      <Text style={styles.iv}>{value}</Text>
    </View>
  )
}

function Placeholder({ icon, text, children }: {
  icon: string; text: string; children?: React.ReactNode
}) {
  return (
    <View style={styles.phBox}>
      <Text style={styles.phIcon}>{icon}</Text>
      <Text style={styles.phText}>{text}</Text>
      {children}
    </View>
  )
}

function SlotCard({ shelfCode, slotCode }: { shelfCode: string; slotCode: string }) {
  return (
    <View style={styles.slotCard}>
      <View style={styles.slotIcon}>
        <Text style={{ fontSize: 24 }}>📦</Text>
      </View>
      <View style={styles.slotInfo}>
        <InfoRow label="料架" value={shelfCode} />
        <InfoRow label="储位" value={slotCode} />
      </View>
    </View>
  )
}

function ScanRow({ placeholder, value, onChange, onSubmit, onCamera }: {
  placeholder: string; value: string; onChange: (v: string) => void;
  onSubmit: () => void; onCamera: () => void
}) {
  return (
    <View style={styles.scanRow}>
      <TextInput
        style={[styles.input, { flex: 1, marginBottom: 0 }]}
        placeholder={placeholder}
        value={value}
        onChangeText={onChange}
        autoFocus
        showSoftInputOnFocus={false}
        onSubmitEditing={onSubmit}
      />
      <TouchableOpacity style={styles.camBtn} onPress={onCamera}>
        <CameraIcon size={22} color="#fff" />
      </TouchableOpacity>
    </View>
  )
}

function StepHint({ text, done }: { text: string; done?: boolean }) {
  return (
    <Text style={[styles.stepHint, done && { color: C.success }]}>
      {text}
    </Text>
  )
}

// ── Styles ──

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: C.bg },
  header: {
    backgroundColor: C.primary, paddingHorizontal: 16,
    paddingTop: 12, paddingBottom: 12,
  },
  headerTitle: { fontSize: 20, fontWeight: 'bold', color: '#fff' },
  headerSub: { fontSize: 13, color: 'rgba(255,255,255,0.85)', marginTop: 2 },

  modeBar: {
    flexDirection: 'row', marginHorizontal: 12, marginTop: 10,
    borderRadius: 8, overflow: 'hidden',
    borderWidth: 1, borderColor: C.primary,
  },
  modeTab: { flex: 1, paddingVertical: 9, alignItems: 'center', backgroundColor: '#fff' },
  modeTabActive: { backgroundColor: C.primary },
  modeTabText: { fontSize: 15, color: C.primary, fontWeight: '600' },
  modeTabTextActive: { color: '#fff' },

  scroll: { flex: 1 },
  scrollInner: { padding: 12, paddingBottom: 20 },

  panel: {
    backgroundColor: C.card, borderRadius: 12, padding: 14,
    marginBottom: 10, elevation: 2,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08, shadowRadius: 4,
    borderLeftWidth: 3, borderLeftColor: '#ddd',
  },
  panelActive: { borderLeftColor: C.info },
  panelDone: { borderLeftColor: C.success },

  ph: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: 10,
  },
  phRow: { flexDirection: 'row', alignItems: 'center' },
  panelTitle: { fontSize: 17, fontWeight: '700', color: C.text },
  modeTag: { fontSize: 12, color: C.info, fontWeight: '600' },
  tagDone: { fontSize: 12, color: C.success, fontWeight: '700' },
  hint: { fontSize: 14, color: C.textSecondary, marginBottom: 8 },
  link: { fontSize: 13, color: C.primary, fontWeight: '600' },

  badge: {
    width: 24, height: 24, borderRadius: 12,
    alignItems: 'center', justifyContent: 'center', marginRight: 8,
  },
  badgePending: { backgroundColor: '#e0e0e0' },
  badgeDone: { backgroundColor: C.success },
  badgeText: { fontSize: 12, fontWeight: 'bold', color: '#fff' },

  scanRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  input: {
    backgroundColor: '#fff', padding: 14, borderRadius: 8,
    fontSize: 18, borderWidth: 1, borderColor: '#ddd',
  },
  camBtn: {
    width: 48, height: 48, borderRadius: 8, backgroundColor: C.info,
    alignItems: 'center', justifyContent: 'center',
  },

  btn: {
    paddingVertical: 14, borderRadius: 8, alignItems: 'center',
    marginBottom: 6, backgroundColor: C.primary,
  },
  btnDisabled: { opacity: 0.4 },
  btnText: { color: '#fff', fontSize: 17, fontWeight: '600' },

  reelCard: {
    backgroundColor: '#f0f5ff', borderRadius: 8, padding: 12,
    borderWidth: 1, borderColor: '#d6e4ff',
  },
  reelHd: { flexDirection: 'row', alignItems: 'center', marginBottom: 6 },
  reelId: { fontSize: 16, fontWeight: 'bold', color: C.text },
  reelTag: {
    fontSize: 11, color: C.warning, backgroundColor: '#fff3e0',
    paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4,
    marginLeft: 8, fontWeight: '600',
  },
  irow: { flexDirection: 'row', paddingVertical: 3 },
  ik: { fontSize: 14, color: C.textSecondary, width: 70 },
  iv: { fontSize: 14, color: C.text, fontWeight: '500', flex: 1 },

  phBox: { alignItems: 'center', paddingVertical: 20 },
  phIcon: { fontSize: 28, marginBottom: 6 },
  phText: { fontSize: 14, color: C.textSecondary },

  slotCard: {
    flexDirection: 'row', backgroundColor: '#e6fffb', borderRadius: 8,
    padding: 12, borderWidth: 1, borderColor: '#87e8de',
  },
  slotIcon: {
    width: 48, height: 48, borderRadius: 24, backgroundColor: '#b7eb8f',
    alignItems: 'center', justifyContent: 'center', marginRight: 12,
  },
  slotInfo: { flex: 1, justifyContent: 'center' },

  waitBox: { alignItems: 'center', paddingVertical: 20 },
  waitTitle: { fontSize: 16, fontWeight: '600', color: C.text, marginTop: 10 },
  waitHint: { fontSize: 14, color: C.textSecondary, marginTop: 6, textAlign: 'center' },
  waitSub: { fontSize: 12, color: C.info, marginTop: 8, textAlign: 'center' },
  wsStatus: { fontSize: 12, color: C.success, marginTop: 6, fontWeight: '600' },

  timeoutHint: { fontSize: 13, color: C.textSecondary, marginTop: 8, textAlign: 'center' },
  timeoutActions: { flexDirection: 'row', gap: 10, marginTop: 12 },
  retry: {
    paddingHorizontal: 20, paddingVertical: 8,
    backgroundColor: C.primary, borderRadius: 6,
  },
  retryText: { color: '#fff', fontSize: 14, fontWeight: '600' },
  retryOutline: {
    paddingHorizontal: 20, paddingVertical: 8,
    borderWidth: 1, borderColor: C.primary, borderRadius: 6,
  },
  retryOutlineText: { color: C.primary, fontSize: 14, fontWeight: '600' },

  stepHint: { fontSize: 13, color: C.textSecondary, textAlign: 'center', marginTop: 2 },

  doneBox: { alignItems: 'center', paddingVertical: 12 },
  doneIcon: { fontSize: 40, marginBottom: 8 },
  doneTitle: { fontSize: 20, fontWeight: 'bold', color: C.text, marginBottom: 6 },
  doneMsg: {
    fontSize: 15, color: C.textSecondary, textAlign: 'center',
    marginBottom: 14, lineHeight: 20,
  },
})
