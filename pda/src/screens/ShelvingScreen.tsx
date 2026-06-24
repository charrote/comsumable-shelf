import React, { useState, useCallback, useRef, useEffect } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, Alert,
  ScrollView, ActivityIndicator,
} from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import {
  scanShelvingReelApi, bindShelvingSlotApi,
  getShelvesApi, getSlotStatesApi,
  scanShelvingSlotApi,
} from '../api'
import type { ShelfResponse, SlotSensorState, ShelvingScanSlotResponse } from '../types/api'
import { useOperator } from '../hooks/useOperator'
import BarcodeScanner from '../components/BarcodeScanner'
import { CameraIcon } from '../components/Icons'

const C = {
  primary: '#0066CC', success: '#00AA55', warning: '#FF9900', danger: '#DD3333',
  info: '#3399CC', card: '#FFFFFF', bg: '#F5F7FA', text: '#1A1A1A', textSecondary: '#666666',
}

type Mode = 'smart' | 'manual'

export default function ShelvingScreen() {
  const { operator } = useOperator()
  const insets = useSafeAreaInsets()

  // Mode
  const [mode, setMode] = useState<Mode>('smart')

  // Panel I: Reel Info
  const [barcode, setBarcode] = useState('')
  const [reelId, setReelId] = useState<number | null>(null)
  const [materialCode, setMaterialCode] = useState('')
  const [materialName, setMaterialName] = useState('')
  const [reelQty, setReelQty] = useState(0)
  const [isScanned, setIsScanned] = useState(false)
  const [isAlreadyBound, setIsAlreadyBound] = useState(false)

  // Panel II - Smart: Sensor
  const [shelves, setShelves] = useState<ShelfResponse[]>([])
  const [selectedShelf, setSelectedShelf] = useState<ShelfResponse | null>(null)
  const [detectedSlot, setDetectedSlot] = useState<SlotSensorState | null>(null)
  const [isPolling, setIsPolling] = useState(false)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const prevStatesRef = useRef<Map<number, boolean>>(new Map())

  // Panel II - Manual: Slot barcode
  const [slotBarcode, setSlotBarcode] = useState('')
  const [scannedSlot, setScannedSlot] = useState<ShelvingScanSlotResponse | null>(null)

  // Panel III: Save
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [resultMsg, setResultMsg] = useState('')
  const [isDone, setIsDone] = useState(false)
  const [showScanner, setShowScanner] = useState(false)
  const [scannerMode, setScannerMode] = useState<'reel' | 'slot'>('reel')

  // Refs
  const reelIdRef = useRef<number | null>(null)
  const selectedShelfRef = useRef<ShelfResponse | null>(null)
  const detectedSlotRef = useRef<SlotSensorState | null>(null)
  const modeRef = useRef<Mode>(mode)
  useEffect(() => { reelIdRef.current = reelId }, [reelId])
  useEffect(() => { selectedShelfRef.current = selectedShelf }, [selectedShelf])
  useEffect(() => { detectedSlotRef.current = detectedSlot }, [detectedSlot])
  useEffect(() => { modeRef.current = mode }, [mode])

  // Init
  useEffect(() => { loadShelves() }, [])
  useEffect(() => () => stopPolling(), [])

  const loadShelves = useCallback(async () => {
    try { setShelves((await getShelvesApi()).filter(s => s.active === 1)) } catch {}
  }, [])

  // ── Smart: Polling ──

  const stopPolling = useCallback(() => {
    if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null }
    setIsPolling(false)
  }, [])

  const startPolling = useCallback((shelfId: number) => {
    stopPolling()
    setIsPolling(true)
    setDetectedSlot(null)
    prevStatesRef.current = new Map()

    pollingRef.current = setInterval(async () => {
      const rid = reelIdRef.current
      if (rid == null) return
      try {
        const sr = await getSlotStatesApi(shelfId)
        const cur = new Map<number, boolean>()
        sr.slots.forEach(s => cur.set(s.slot_id, s.has_material))
        const prev = prevStatesRef.current
        if (prev.size === 0) { prevStatesRef.current = cur; return }
        for (const s of sr.slots) {
          const was = prev.get(s.slot_id)
          if (was === false && s.has_material && (s.bound_reel_id == null || s.bound_reel_id === rid)) {
            setDetectedSlot(s); break
          }
        }
        const curDetect = detectedSlotRef.current
        if (curDetect && cur.get(curDetect.slot_id) === false) setDetectedSlot(null)
        prevStatesRef.current = cur
      } catch {}
    }, 1500)
  }, [stopPolling])

  const handleSelectShelf = useCallback((s: ShelfResponse) => {
    setSelectedShelf(s); setDetectedSlot(null)
    if (reelIdRef.current != null && !isDone && modeRef.current === 'smart') {
      stopPolling(); startPolling(s.id)
    }
  }, [isDone, startPolling, stopPolling])

  // ── Scan Reel ──

  const handleScanReel = useCallback(async (code?: string) => {
    const sc = (code || barcode).trim()
    if (!sc) return
    setIsLoading(true); setResultMsg('')
    try {
      const res = await scanShelvingReelApi(sc)
      setReelId(res.reel_id); setMaterialCode(res.material_code)
      setMaterialName(res.material_name || ''); setReelQty(res.quantity)
      setIsScanned(true)
      if (res.status === 'already_bound') {
        setIsAlreadyBound(true)
        setResultMsg(`该料盘已上架至 ${res.shelf_code || ''}/${res.slot_code || ''}`)
        setIsDone(true)
      } else {
        setIsAlreadyBound(false)
        if (mode === 'smart' && selectedShelfRef.current) startPolling(selectedShelfRef.current.id)
      }
    } catch (e: any) { Alert.alert('扫描失败', e?.response?.data?.detail || '请检查条码') }
    finally { setIsLoading(false) }
  }, [barcode, mode, startPolling])

  const handleCamReel = useCallback((v: string) => { setBarcode(v); setShowScanner(false); handleScanReel(v) }, [handleScanReel])

  // ── Manual: Scan Slot Barcode ──

  const handleScanSlot = useCallback(async (code?: string) => {
    const sc = (code || slotBarcode).trim()
    if (!sc) return
    setIsLoading(true)
    try {
      const res = await scanShelvingSlotApi(sc)
      if (res.status === 'occupied') { Alert.alert('储位被占用', res.message); return }
      setScannedSlot(res)
      // Auto-select the shelf from the scanned slot barcode
      const shelf = shelves.find(s => s.id === res.shelf_id)
      if (shelf) setSelectedShelf(shelf)
    } catch (e: any) { Alert.alert('扫描失败', e?.response?.data?.detail || '请检查储位条码') }
    finally { setIsLoading(false) }
  }, [slotBarcode, shelves])

  const handleCamSlot = useCallback((v: string) => { setSlotBarcode(v); setShowScanner(false); handleScanSlot(v) }, [handleScanSlot])

  const openCam = useCallback((mode: 'reel' | 'slot') => { setScannerMode(mode); setShowScanner(true) }, [])

  const handleCamScan = useCallback((v: string) => {
    scannerMode === 'reel' ? handleCamReel(v) : handleCamSlot(v)
  }, [scannerMode, handleCamReel, handleCamSlot])

  // ── Save ──

  const handleSave = useCallback(async () => {
    if (reelId == null) return
    // Smart mode needs selectedShelf; manual mode gets shelf from scannedSlot
    const shelfId = mode === 'smart' ? selectedShelf?.id : scannedSlot?.shelf_id
    const slotId = mode === 'smart' ? detectedSlot?.slot_id : scannedSlot?.shelf_slot_id
    if (shelfId == null || slotId == null) return
    setIsSaving(true)
    try {
      const res = await bindShelvingSlotApi({ reel_id: reelId, shelf_id: shelfId, shelf_slot_id: slotId, operator })
      setResultMsg(`上架成功!\n料架: ${res.shelf_code}\n储位: ${res.slot_code}`)
      setIsDone(true); stopPolling()
    } catch (e: any) { Alert.alert('上架失败', e?.response?.data?.detail || '请重试') }
    finally { setIsSaving(false) }
  }, [reelId, selectedShelf, mode, detectedSlot, scannedSlot, operator, stopPolling])

  // ── Reset ──

  const handleReset = useCallback(() => {
    stopPolling()
    setBarcode(''); setReelId(null); setMaterialCode(''); setMaterialName(''); setReelQty(0)
    setIsScanned(false); setIsAlreadyBound(false)
    setDetectedSlot(null); setScannedSlot(null); setSlotBarcode('')
    setResultMsg(''); setIsDone(false)
    prevStatesRef.current = new Map()
  }, [stopPolling])

  const switchMode = useCallback((m: Mode) => { handleReset(); setMode(m) }, [handleReset])

  // Derived
  const slotIdentified = mode === 'smart' ? detectedSlot != null : scannedSlot != null
  // Smart: needs selectedShelf. Manual: shelf comes from scannedSlot barcode.
  const canSave = isScanned && !isAlreadyBound && slotIdentified && !isSaving && !isDone
    && (mode === 'smart' ? selectedShelf != null : scannedSlot != null)

  return (
    <View style={styles.container}>
      {/* ──── Header ──── */}
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <Text style={styles.headerTitle}>料盘上架</Text>
        <Text style={styles.headerSub}>
          {mode === 'smart' ? '智能料架 · 放入即识别' : '手动上架 · 扫储位标签'}
        </Text>
      </View>

      {/* ──── Mode Switch ──── */}
      <View style={styles.modeBar}>
        {(['smart', 'manual'] as Mode[]).map(m => (
          <TouchableOpacity key={m} style={[styles.modeTab, mode === m && styles.modeTabActive]}
            onPress={() => switchMode(m)}>
            <Text style={[styles.modeTabText, mode === m && styles.modeTabTextActive]}>
              {m === 'smart' ? '智能料架' : '手动上架'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* ──── Shelf Selector ──── */}
      <View style={styles.shelfBar}>
        <Text style={styles.shelfBarLabel}>料架:</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.shelfBarScroll}>
          {shelves.length === 0 ? (
            <TouchableOpacity style={styles.shelfChip} onPress={loadShelves}>
              <Text style={styles.shelfChipText}>加载</Text>
            </TouchableOpacity>
          ) : shelves.map(s => (
            <TouchableOpacity key={s.id}
              style={[styles.shelfChip, selectedShelf?.id === s.id && styles.shelfChipActive]}
              onPress={() => handleSelectShelf(s)}>
              <Text style={[styles.shelfChipText, selectedShelf?.id === s.id && styles.shelfChipTextActive]}>{s.code}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
        {mode === 'smart' && isPolling && <ActivityIndicator size="small" color={C.primary} style={{ marginLeft: 6 }} />}
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollInner}>
        {/* ═══════════ Panel I ═══════════ */}
        <View style={[styles.panel, isScanned && !isAlreadyBound && styles.panelDone]}>
          <PanelHeader num="I" title="扫描料盘" done={isScanned && !isAlreadyBound}
            right={isScanned && !isAlreadyBound ? <TouchableOpacity onPress={handleReset}><Text style={styles.link}>重新扫描</Text></TouchableOpacity> : undefined}
          />
          {!isScanned ? (
            <>
              <Text style={styles.hint}>扫描收料后打印的内部标签条码</Text>
              <ScanRow placeholder="扫描料盘条码" value={barcode} onChange={setBarcode}
                onSubmit={() => handleScanReel()} onCamera={() => openCam('reel')} />
            </>
          ) : (
            <View style={styles.reelCard}>
              <View style={styles.reelHd}>
                <Text style={styles.reelId}>Reel #{reelId}</Text>
                {!isAlreadyBound && <Text style={styles.reelTag}>待上架</Text>}
              </View>
              <InfoRow label="物料编码" value={materialCode} />
              {materialName ? <InfoRow label="物料名称" value={materialName} /> : null}
              <InfoRow label="数量" value={`${reelQty}`} />
            </View>
          )}
        </View>

        {/* ═══════════ Panel II ═══════════ */}
        <View style={[styles.panel, slotIdentified && styles.panelDone]}>
          <PanelHeader num="II" title="储位识别" done={slotIdentified}
            right={<Text style={styles.modeTag}>{mode === 'smart' ? '传感器' : '扫码'}</Text>}
          />
          {!isScanned ? <Placeholder icon="①" text="请先扫描料盘" />
          : isAlreadyBound ? <Placeholder icon="✓" text="料盘已上架，无需重复操作" />
          : mode === 'smart' && selectedShelf == null ? <Placeholder icon="②" text="请在上方选择目标料架" />
          : mode === 'smart' ? (
            detectedSlot ? (
              <SlotCard shelfCode={selectedShelf!.code} slotCode={`${detectedSlot.side}${detectedSlot.slot_on_board}`} autoBound={detectedSlot.bound_reel_id != null} />
            ) : isPolling ? (
              <View style={styles.waitBox}>
                <ActivityIndicator size="large" color={C.primary} />
                <Text style={styles.waitTitle}>等待放入料架...</Text>
                <Text style={styles.waitHint}>请将料盘放入 {selectedShelf!.code} 的空储位</Text>
                <Text style={styles.waitSub}>传感器检测中 (1.5s/次)</Text>
              </View>
            ) : (
              <Placeholder icon="⟳" text="传感器未启动">
                <TouchableOpacity style={styles.retry} onPress={() => startPolling(selectedShelf!.id)}>
                  <Text style={styles.retryText}>启动检测</Text>
                </TouchableOpacity>
              </Placeholder>
            )
          ) : (
            /* Manual mode — no shelf pre-selection needed */
            scannedSlot ? (
              <SlotCard shelfCode={scannedSlot.shelf_code} slotCode={scannedSlot.slot_code} autoBound={false} />
            ) : (
              <>
                <Text style={styles.hint}>扫描料架储位上粘贴的条码标签</Text>
                <ScanRow placeholder="扫描储位条码 (如 A1A05)" value={slotBarcode} onChange={setSlotBarcode}
                  onSubmit={() => handleScanSlot()} onCamera={() => openCam('slot')} />
              </>
            )
          )}
        </View>

        {/* ═══════════ Panel III ═══════════ */}
        <View style={styles.panel}>
          <PanelHeader num="III" title="确认上架" right={isDone && !isAlreadyBound ? <Text style={styles.tagDone}>完成</Text> : undefined} />
          {isDone ? (
            <View style={styles.doneBox}>
              <Text style={styles.doneIcon}>{isAlreadyBound ? 'ℹ️' : '✅'}</Text>
              <Text style={styles.doneTitle}>{isAlreadyBound ? '料盘已上架' : '上架完成'}</Text>
              <Text style={styles.doneMsg}>{resultMsg}</Text>
              <Btn title="继续上架" onPress={handleReset} style={{ backgroundColor: C.success, paddingHorizontal: 40 }} />
            </View>
          ) : (
            <>
              <Btn title={
                !isScanned ? '请先扫描料盘'
                : isAlreadyBound ? '料盘已上架'
                : mode === 'smart' && selectedShelf == null ? '请选择料架'
                : !slotIdentified ? (mode === 'smart' ? '等待检测储位' : '请扫描储位条码')
                : '保存'
              } onPress={handleSave}
                disabled={!canSave}
                loading={isSaving}
                style={canSave ? { backgroundColor: C.success } : undefined}
                textStyle={canSave ? { fontWeight: '700', fontSize: 18 } : undefined}
              />
              <StepHint text={
                !isScanned ? '步骤 1/3: 扫描料盘条码'
                : mode === 'smart' && selectedShelf == null ? '步骤 1.5/3: 选择目标料架'
                : !slotIdentified ? (mode === 'smart' ? '步骤 2/3: 将料盘放入料架空储位' : '步骤 2/3: 扫描货架储位标签条码')
                : '✓ 步骤 3/3: 点击「保存」完成操作'
              } done={isScanned && slotIdentified && !isDone} />
            </>
          )}
        </View>
        <View style={{ height: 40 }} />
      </ScrollView>

      <BarcodeScanner visible={showScanner} onScan={handleCamScan}
        onClose={() => setShowScanner(false)} title={scannerMode === 'reel' ? '扫码料盘' : '扫码储位'} />
    </View>
  )
}

// ── Helper Components ──

function PanelHeader({ num, title, done, right }: { num: string; title: string; done?: boolean; right?: React.ReactNode }) {
  return (
    <View style={styles.ph}>
      <View style={styles.phRow}>
        <View style={[styles.badge, done ? styles.badgeDone : styles.badgePending]}><Text style={styles.badgeText}>{num}</Text></View>
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

function Placeholder({ icon, text, children }: { icon: string; text: string; children?: React.ReactNode }) {
  return (
    <View style={styles.phBox}>
      <Text style={styles.phIcon}>{icon}</Text>
      <Text style={styles.phText}>{text}</Text>
      {children}
    </View>
  )
}

function SlotCard({ shelfCode, slotCode, autoBound }: { shelfCode: string; slotCode: string; autoBound: boolean }) {
  return (
    <View style={styles.slotCard}>
      <View style={styles.slotIcon}><Text style={{ fontSize: 24 }}>📦</Text></View>
      <View style={styles.slotInfo}>
        <InfoRow label="料架" value={shelfCode} />
        <InfoRow label="储位" value={slotCode} />
        {autoBound && <InfoRow label="状态" value="已自动绑定" />}
      </View>
    </View>
  )
}

function ScanRow({ placeholder, value, onChange, onSubmit, onCamera }: {
  placeholder: string; value: string; onChange: (v: string) => void; onSubmit: () => void; onCamera: () => void
}) {
  return (
    <View style={styles.scanRow}>
      <TextInput style={[styles.input, { flex: 1, marginBottom: 0 }]} placeholder={placeholder}
        value={value} onChangeText={onChange} autoFocus
        showSoftInputOnFocus={false} onSubmitEditing={onSubmit} />
      <TouchableOpacity style={styles.camBtn} onPress={onCamera}>
        <CameraIcon size={22} color="#fff" />
      </TouchableOpacity>
    </View>
  )
}

function Btn({ title, onPress, disabled, loading, style, textStyle }: {
  title: string; onPress: () => void; disabled?: boolean; loading?: boolean; style?: any; textStyle?: any
}) {
  return (
    <TouchableOpacity style={[styles.btn, style, disabled && styles.btnDisabled]} onPress={onPress} disabled={disabled || loading}>
      {loading ? <ActivityIndicator color="#fff" /> : <Text style={[styles.btnText, textStyle]}>{title}</Text>}
    </TouchableOpacity>
  )
}

function StepHint({ text, done }: { text: string; done?: boolean }) {
  return <Text style={[styles.stepHint, done && { color: C.success }]}>{text}</Text>
}

// ── Styles ──

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: C.bg },
  header: { backgroundColor: C.primary, paddingHorizontal: 16, paddingTop: 12, paddingBottom: 12 },
  headerTitle: { fontSize: 20, fontWeight: 'bold', color: '#fff' },
  headerSub: { fontSize: 13, color: 'rgba(255,255,255,0.85)', marginTop: 2 },

  modeBar: { flexDirection: 'row', marginHorizontal: 12, marginTop: 10, borderRadius: 8, overflow: 'hidden', borderWidth: 1, borderColor: C.primary },
  modeTab: { flex: 1, paddingVertical: 9, alignItems: 'center', backgroundColor: '#fff' },
  modeTabActive: { backgroundColor: C.primary },
  modeTabText: { fontSize: 15, color: C.primary, fontWeight: '600' },
  modeTabTextActive: { color: '#fff' },

  shelfBar: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff', paddingHorizontal: 12, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#e8e8e8' },
  shelfBarLabel: { fontSize: 14, fontWeight: '600', color: C.text, marginRight: 8 },
  shelfBarScroll: { flex: 1 },
  shelfChip: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 16, borderWidth: 1, borderColor: C.primary, marginRight: 8, backgroundColor: '#fff' },
  shelfChipActive: { backgroundColor: C.primary },
  shelfChipText: { fontSize: 13, fontWeight: '600', color: C.primary },
  shelfChipTextActive: { color: '#fff' },

  scroll: { flex: 1 },
  scrollInner: { padding: 12, paddingBottom: 20 },

  panel: { backgroundColor: C.card, borderRadius: 12, padding: 14, marginBottom: 10, elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.08, shadowRadius: 4, borderLeftWidth: 3, borderLeftColor: '#ddd' },
  panelDone: { borderLeftColor: C.success },
  ph: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  phRow: { flexDirection: 'row', alignItems: 'center' },
  panelTitle: { fontSize: 17, fontWeight: '700', color: C.text },
  modeTag: { fontSize: 12, color: C.primary, fontWeight: '600' },
  tagDone: { fontSize: 12, color: C.success, fontWeight: '700' },
  hint: { fontSize: 14, color: C.textSecondary, marginBottom: 8 },
  link: { fontSize: 13, color: C.primary, fontWeight: '600' },

  badge: { width: 24, height: 24, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginRight: 8 },
  badgePending: { backgroundColor: '#e0e0e0' },
  badgeDone: { backgroundColor: C.success },
  badgeText: { fontSize: 12, fontWeight: 'bold', color: '#fff' },

  scanRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  input: { backgroundColor: '#fff', padding: 14, borderRadius: 8, fontSize: 18, borderWidth: 1, borderColor: '#ddd' },
  camBtn: { width: 48, height: 48, borderRadius: 8, backgroundColor: C.info, alignItems: 'center', justifyContent: 'center' },

  btn: { paddingVertical: 14, borderRadius: 8, alignItems: 'center', marginBottom: 6, backgroundColor: C.primary },
  btnDisabled: { opacity: 0.4 },
  btnText: { color: '#fff', fontSize: 17, fontWeight: '600' },

  reelCard: { backgroundColor: '#f0f5ff', borderRadius: 8, padding: 12, borderWidth: 1, borderColor: '#d6e4ff' },
  reelHd: { flexDirection: 'row', alignItems: 'center', marginBottom: 6 },
  reelId: { fontSize: 16, fontWeight: 'bold', color: C.text },
  reelTag: { fontSize: 11, color: C.warning, backgroundColor: '#fff3e0', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4, marginLeft: 8, fontWeight: '600' },
  irow: { flexDirection: 'row', paddingVertical: 3 },
  ik: { fontSize: 14, color: C.textSecondary, width: 70 },
  iv: { fontSize: 14, color: C.text, fontWeight: '500', flex: 1 },

  phBox: { alignItems: 'center', paddingVertical: 20 },
  phIcon: { fontSize: 28, marginBottom: 6 },
  phText: { fontSize: 14, color: C.textSecondary },

  slotCard: { flexDirection: 'row', backgroundColor: '#e6fffb', borderRadius: 8, padding: 12, borderWidth: 1, borderColor: '#87e8de' },
  slotIcon: { width: 48, height: 48, borderRadius: 24, backgroundColor: '#b7eb8f', alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  slotInfo: { flex: 1, justifyContent: 'center' },

  waitBox: { alignItems: 'center', paddingVertical: 20 },
  waitTitle: { fontSize: 16, fontWeight: '600', color: C.text, marginTop: 10 },
  waitHint: { fontSize: 14, color: C.textSecondary, marginTop: 6, textAlign: 'center' },
  waitSub: { fontSize: 12, color: C.info, marginTop: 8 },
  retry: { marginTop: 10, paddingHorizontal: 20, paddingVertical: 8, backgroundColor: C.primary, borderRadius: 6 },
  retryText: { color: '#fff', fontSize: 14, fontWeight: '600' },

  stepHint: { fontSize: 13, color: C.textSecondary, textAlign: 'center', marginTop: 2 },

  doneBox: { alignItems: 'center', paddingVertical: 12 },
  doneIcon: { fontSize: 40, marginBottom: 8 },
  doneTitle: { fontSize: 20, fontWeight: 'bold', color: C.text, marginBottom: 6 },
  doneMsg: { fontSize: 15, color: C.textSecondary, textAlign: 'center', marginBottom: 14, lineHeight: 20 },
})
