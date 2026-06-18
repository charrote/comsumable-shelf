import React, { useState, useCallback } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, Alert,
  ScrollView, ActivityIndicator,
} from 'react-native'
import { scanShelvingReelApi, bindShelvingSlotApi, getShelvesApi, getShelfSlotsApi, getSlotStatesApi } from '../api'
import type { ShelfResponse, ShelfSlotResponse, SlotSensorState } from '../types/api'
import { useAuthStore } from '../store/authStore'

const Colors = {
  primary: '#0066CC', success: '#00AA55', warning: '#FF9900', danger: '#DD3333',
  info: '#3399CC', card: '#FFFFFF', bg: '#F5F7FA', text: '#1A1A1A', textSecondary: '#666666',
}

type Mode = 'smart' | 'manual'
type Step = 'scan_reel' | 'waiting_slot' | 'select_slot' | 'done'

export default function ShelvingScreen() {
  const user = useAuthStore((s) => s.user)
  const [mode, setMode] = useState<Mode>('smart')
  const [step, setStep] = useState<Step>('scan_reel')
  const [barcode, setBarcode] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [operator] = useState(user?.username || '')

  // Reel info after scan
  const [reelId, setReelId] = useState<number | null>(null)
  const [materialCode, setMaterialCode] = useState('')
  const [materialName, setMaterialName] = useState('')
  const [reelQty, setReelQty] = useState(0)

  // Shelf/Slot selection (manual mode)
  const [shelves, setShelves] = useState<ShelfResponse[]>([])
  const [selectedShelf, setSelectedShelf] = useState<ShelfResponse | null>(null)
  const [slots, setSlots] = useState<ShelfSlotResponse[]>([])
  const [selectedSlot, setSelectedSlot] = useState<ShelfSlotResponse | null>(null)
  const [slotStates, setSlotStates] = useState<SlotSensorState[]>([])

  // Result
  const [resultMsg, setResultMsg] = useState('')

  // ── Step 1: Scan Reel ──
  const handleScanReel = useCallback(async () => {
    if (!barcode.trim()) return
    setIsLoading(true)
    setResultMsg('')
    try {
      const res = await scanShelvingReelApi(barcode.trim())
      setReelId(res.reel_id)
      setMaterialCode(res.material_code)
      setMaterialName(res.material_name || '')
      setReelQty(res.quantity)

      if (res.status === 'already_bound') {
        setResultMsg(`该料盘已上架: ${res.shelf_code || ''} / ${res.slot_code || ''}`)
        setStep('done')
      } else if (mode === 'smart') {
        setStep('waiting_slot')
        setResultMsg('料盘已识别，请放入料架空储位...')
        // In production, we'd poll sensor state; here we show manual fallback
        setTimeout(() => {
          Alert.alert(
            '智能上架',
            '请将料盘放入任意空储位。\n\n传感器将自动检测并绑定。\n\n如无传感器，请使用手动模式。',
            [{ text: '使用手动模式', onPress: () => switchToManual() }]
          )
        }, 500)
      } else {
        // Manual mode: load shelf list
        await loadShelves()
        setStep('select_slot')
      }
    } catch (e: any) {
      Alert.alert('扫描失败', e?.response?.data?.detail || '请检查条码')
    } finally {
      setIsLoading(false)
    }
  }, [barcode, mode])

  // ── Smart: Poll Slot Sensor ──
  const handleCheckSensor = useCallback(async () => {
    if (!selectedShelf) {
      Alert.alert('提示', '请先选择料架')
      return
    }
    setIsLoading(true)
    try {
      const stateRes = await getSlotStatesApi(selectedShelf.id)
      const occupiedSlots = stateRes.slots.filter(s => s.has_material && !s.bound_reel_id)
      if (occupiedSlots.length > 0) {
        // Found a newly occupied slot
        const slot = occupiedSlots[0]
        const bindRes = await bindShelvingSlotApi({
          reel_id: reelId!,
          shelf_id: selectedShelf.id,
          shelf_slot_id: slot.slot_id,
          operator,
        })
        setResultMsg(`✅ 上架成功!\n料架: ${bindRes.shelf_code}\n储位: ${bindRes.slot_code}`)
        setStep('done')
      } else {
        Alert.alert('未检测到', '暂未检测到新放入的料盘，请确认料盘已放入储位')
      }
    } catch (e: any) {
      Alert.alert('检测失败', e?.response?.data?.detail || '传感器检测失败')
    } finally {
      setIsLoading(false)
    }
  }, [selectedShelf, reelId, operator])

  // ── Manual: Load shelves & slots ──
  const loadShelves = useCallback(async () => {
    try {
      const shelfList = await getShelvesApi()
      setShelves(shelfList.filter(s => s.active === 1))
    } catch { /* ignore */ }
  }, [])

  const loadSlots = useCallback(async (shelfId: number) => {
    try {
      const slotList = await getShelfSlotsApi(shelfId)
      const stateRes = await getSlotStatesApi(shelfId)
      setSlots(slotList)
      setSlotStates(stateRes.slots || [])
    } catch { /* ignore */ }
  }, [])

  const handleSelectShelf = useCallback(async (shelf: ShelfResponse) => {
    setSelectedShelf(shelf)
    setSelectedSlot(null)
    await loadSlots(shelf.id)
  }, [loadSlots])

  const handleManualBind = useCallback(async () => {
    if (!selectedShelf || !selectedSlot || reelId == null) return
    setIsLoading(true)
    try {
      const res = await bindShelvingSlotApi({
        reel_id: reelId,
        shelf_id: selectedShelf.id,
        shelf_slot_id: selectedSlot.id,
        operator,
      })
      setResultMsg(`✅ 上架成功!\n料架: ${res.shelf_code}\n储位: ${res.slot_code}`)
      setStep('done')
    } catch (e: any) {
      Alert.alert('绑定失败', e?.response?.data?.detail || '请重试')
    } finally {
      setIsLoading(false)
    }
  }, [selectedShelf, selectedSlot, reelId, operator])

  const switchToManual = () => {
    setMode('manual')
    loadShelves()
    setStep('select_slot')
  }

  // Reset
  const handleReset = () => {
    setStep('scan_reel')
    setBarcode('')
    setReelId(null)
    setMaterialCode('')
    setMaterialName('')
    setReelQty(0)
    setSelectedShelf(null)
    setSelectedSlot(null)
    setSlots([])
    setResultMsg('')
  }

  // Check if a slot is available (not occupied)
  const isSlotAvailable = (slotId: number) => {
    const state = slotStates.find(s => s.slot_id === slotId)
    return !state?.has_material
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>料盘上架</Text>
        <Text style={styles.headerSub}>
          {mode === 'smart' ? '智能料架上架（传感器感应）' : '手动上架（选择储位）'}
        </Text>
      </View>

      {/* Mode Switch */}
      <View style={styles.modeSwitch}>
        <TouchableOpacity
          style={[styles.modeTab, mode === 'smart' && styles.modeTabActive]}
          onPress={() => { setMode('smart'); if (step === 'select_slot') switchToManual() }}
        >
          <Text style={[styles.modeTabText, mode === 'smart' && styles.modeTabTextActive]}>智能上架</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.modeTab, mode === 'manual' && styles.modeTabActive]}
          onPress={() => { setMode('manual'); handleReset() }}
        >
          <Text style={[styles.modeTabText, mode === 'manual' && styles.modeTabTextActive]}>手动上架</Text>
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.scrollArea} contentContainerStyle={styles.scrollContent}>
        {/* Step: Scan Reel */}
        {step === 'scan_reel' && (
          <View style={styles.card}>
            <Text style={styles.stepTitle}>步骤 1：扫描料盘条码</Text>
            <Text style={styles.hint}>扫描已收料入库的料盘内部标签</Text>
            <TextInput
              style={styles.input}
              placeholder="扫描料盘条码"
              value={barcode}
              onChangeText={setBarcode}
              autoFocus
              onSubmitEditing={handleScanReel}
            />
            <TouchableOpacity
              style={[styles.button, !barcode.trim() && styles.buttonDisabled]}
              onPress={handleScanReel}
              disabled={!barcode.trim() || isLoading}
            >
              {isLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>识别料盘</Text>}
            </TouchableOpacity>
          </View>
        )}

        {/* Step: Waiting for sensor (smart mode) */}
        {step === 'waiting_slot' && (
          <View style={styles.card}>
            <Text style={styles.stepTitle}>步骤 2：放入料架储位</Text>
            {reelId && (
              <View style={styles.reelInfo}>
                <Text style={styles.infoLabel}>Reel: #{reelId}</Text>
                <Text style={styles.infoValue}>物料: {materialCode}</Text>
                <Text style={styles.infoValue}>{materialName}</Text>
                <Text style={styles.infoValue}>数量: {reelQty} 盘</Text>
              </View>
            )}
            <View style={styles.waitingBox}>
              <ActivityIndicator size="large" color={Colors.primary} />
              <Text style={styles.waitingText}>等待放入料架...</Text>
              <Text style={styles.hint}>请将料盘放入料架任意空储位</Text>
            </View>

            {/* Shelf selector for sensor check */}
            <Text style={styles.sectionLabel}>选择料架（用于传感器检测）</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.shelfRow}>
              {shelves.length === 0 ? (
                <TouchableOpacity style={styles.loadBtn} onPress={loadShelves}>
                  <Text style={styles.loadBtnText}>加载料架列表</Text>
                </TouchableOpacity>
              ) : (
                shelves.map(s => (
                  <TouchableOpacity
                    key={s.id}
                    style={[styles.shelfChip, selectedShelf?.id === s.id && styles.shelfChipActive]}
                    onPress={() => setSelectedShelf(s)}
                  >
                    <Text style={[styles.shelfChipText, selectedShelf?.id === s.id && styles.shelfChipTextActive]}>
                      {s.code}
                    </Text>
                  </TouchableOpacity>
                ))
              )}
            </ScrollView>

            <TouchableOpacity
              style={[styles.button, styles.checkButton, !selectedShelf && styles.buttonDisabled]}
              onPress={handleCheckSensor}
              disabled={!selectedShelf || isLoading}
            >
              {isLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>检测传感器</Text>}
            </TouchableOpacity>

            <TouchableOpacity style={styles.linkBtn} onPress={switchToManual}>
              <Text style={styles.linkText}>传感器未响应？切换到手动上架</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Step: Select slot (manual mode) */}
        {step === 'select_slot' && (
          <View style={styles.card}>
            <Text style={styles.stepTitle}>步骤 2：选择目标储位</Text>
            {reelId && (
              <View style={styles.reelInfo}>
                <Text style={styles.infoLabel}>Reel: #{reelId}</Text>
                <Text style={styles.infoValue}>物料: {materialCode}</Text>
                <Text style={styles.infoValue}>{materialName}</Text>
                <Text style={styles.infoValue}>数量: {reelQty} 盘</Text>
              </View>
            )}

            {/* Shelf selection */}
            <Text style={styles.sectionLabel}>1. 选择料架</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.shelfRow}>
              {shelves.map(s => (
                <TouchableOpacity
                  key={s.id}
                  style={[styles.shelfChip, selectedShelf?.id === s.id && styles.shelfChipActive]}
                  onPress={() => handleSelectShelf(s)}
                >
                  <Text style={[styles.shelfChipText, selectedShelf?.id === s.id && styles.shelfChipTextActive]}>
                    {s.code}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            {/* Slot selection */}
            {selectedShelf && (
              <>
                <Text style={styles.sectionLabel}>2. 选择储位</Text>
                <View style={styles.slotGrid}>
                  {slots.map(slot => {
                    const available = isSlotAvailable(slot.id)
                    return (
                      <TouchableOpacity
                        key={slot.id}
                        style={[
                          styles.slotBtn,
                          selectedSlot?.id === slot.id && styles.slotBtnSelected,
                          !available && styles.slotBtnOccupied,
                        ]}
                        onPress={() => available && setSelectedSlot(slot)}
                        disabled={!available}
                      >
                        <Text style={[
                          styles.slotBtnText,
                          selectedSlot?.id === slot.id && styles.slotBtnTextSelected,
                          !available && styles.slotBtnTextOccupied,
                        ]}>
                          {slot.side}{slot.slot_on_board}
                        </Text>
                      </TouchableOpacity>
                    )
                  })}
                </View>
              </>
            )}

            {selectedSlot && (
              <View style={styles.selectedInfo}>
                <Text style={styles.selectedInfoText}>
                  已选: {selectedShelf?.code} / {selectedSlot.side}{selectedSlot.slot_on_board}
                </Text>
              </View>
            )}

            <TouchableOpacity
              style={[styles.button, styles.confirmButton, (!selectedShelf || !selectedSlot) && styles.buttonDisabled]}
              onPress={handleManualBind}
              disabled={!selectedShelf || !selectedSlot || isLoading}
            >
              {isLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>确认上架</Text>}
            </TouchableOpacity>
          </View>
        )}

        {/* Step: Done */}
        {step === 'done' && (
          <View style={styles.card}>
            <Text style={styles.stepTitle}>
              {resultMsg.includes('✅') ? '上架成功' : resultMsg.includes('已上架') ? '已上架' : '结果'}
            </Text>
            <Text style={styles.resultText}>{resultMsg}</Text>
            {reelId && (
              <View style={styles.reelInfo}>
                <Text style={styles.infoLabel}>Reel: #{reelId}</Text>
                <Text style={styles.infoValue}>物料: {materialCode}</Text>
              </View>
            )}
            <TouchableOpacity style={[styles.button, styles.nextButton]} onPress={handleReset}>
              <Text style={styles.buttonText}>继续上架</Text>
            </TouchableOpacity>
          </View>
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
  modeSwitch: { flexDirection: 'row', marginHorizontal: 12, marginTop: 10, borderRadius: 8, overflow: 'hidden', borderWidth: 1, borderColor: Colors.primary },
  modeTab: { flex: 1, paddingVertical: 10, alignItems: 'center', backgroundColor: '#fff' },
  modeTabActive: { backgroundColor: Colors.primary },
  modeTabText: { fontSize: 16, color: Colors.primary, fontWeight: '600' },
  modeTabTextActive: { color: '#fff' },
  scrollArea: { flex: 1 },
  scrollContent: { padding: 12, paddingBottom: 40 },
  card: { backgroundColor: Colors.card, borderRadius: 12, padding: 16, marginBottom: 12, elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 4 },
  stepTitle: { fontSize: 18, fontWeight: 'bold', color: Colors.text, marginBottom: 8 },
  hint: { fontSize: 14, color: Colors.textSecondary, marginBottom: 12 },
  input: { backgroundColor: '#fff', padding: 14, borderRadius: 8, marginBottom: 12, fontSize: 18, borderWidth: 1, borderColor: '#ddd' },
  button: { backgroundColor: Colors.primary, padding: 16, borderRadius: 8, alignItems: 'center', marginBottom: 8 },
  confirmButton: { backgroundColor: Colors.success },
  checkButton: { backgroundColor: Colors.info },
  nextButton: { backgroundColor: Colors.success },
  buttonDisabled: { opacity: 0.5 },
  buttonText: { color: '#fff', fontSize: 18, fontWeight: '600' },
  linkBtn: { alignItems: 'center', marginTop: 4 },
  linkText: { color: Colors.primary, fontSize: 14 },
  reelInfo: { backgroundColor: '#f0f5ff', borderRadius: 8, padding: 12, marginBottom: 8 },
  infoLabel: { fontSize: 18, fontWeight: 'bold', color: Colors.text },
  infoValue: { fontSize: 15, color: Colors.textSecondary, marginTop: 2 },
  waitingBox: { alignItems: 'center', padding: 24 },
  waitingText: { fontSize: 18, fontWeight: '600', color: Colors.text, marginTop: 12 },
  sectionLabel: { fontSize: 15, fontWeight: '600', color: Colors.text, marginTop: 8, marginBottom: 6 },
  shelfRow: { marginBottom: 8 },
  shelfChip: { paddingHorizontal: 16, paddingVertical: 10, borderRadius: 20, borderWidth: 1, borderColor: Colors.primary, marginRight: 8, backgroundColor: '#fff' },
  shelfChipActive: { backgroundColor: Colors.primary },
  shelfChipText: { fontSize: 15, color: Colors.primary, fontWeight: '600' },
  shelfChipTextActive: { color: '#fff' },
  loadBtn: { padding: 10, borderRadius: 8, backgroundColor: Colors.primary },
  loadBtnText: { color: '#fff', fontSize: 14 },
  slotGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  slotBtn: { width: 56, height: 44, borderRadius: 6, borderWidth: 1, borderColor: '#ddd', alignItems: 'center', justifyContent: 'center', backgroundColor: '#fff' },
  slotBtnSelected: { borderColor: Colors.primary, backgroundColor: '#e6f0ff' },
  slotBtnOccupied: { backgroundColor: '#f5f5f5', borderColor: '#eee' },
  slotBtnText: { fontSize: 13, fontWeight: '600', color: Colors.text },
  slotBtnTextSelected: { color: Colors.primary },
  slotBtnTextOccupied: { color: '#ccc' },
  selectedInfo: { backgroundColor: '#e6f7ff', borderRadius: 8, padding: 10, marginVertical: 8 },
  selectedInfoText: { fontSize: 15, color: Colors.primary, fontWeight: '600', textAlign: 'center' },
  resultText: { fontSize: 16, color: Colors.text, marginBottom: 12, lineHeight: 22 },
})
