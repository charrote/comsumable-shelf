import React, { useState, useCallback } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, Alert,
  ScrollView, ActivityIndicator,
} from 'react-native'
import AsyncStorage from '@react-native-async-storage/async-storage'
import { useAuthStore } from '../store/authStore'
import api from '../api'

const Colors = {
  primary: '#0066CC', success: '#00AA55', warning: '#FF9900', danger: '#DD3333',
  info: '#3399CC', card: '#FFFFFF', bg: '#F5F7FA', text: '#1A1A1A', textSecondary: '#666666',
}

const SETTINGS_KEYS = {
  API_URL: 'pda_api_url',
  PRINTER_IP: 'pda_printer_ip',
  PRINTER_PORT: 'pda_printer_port',
  FIFO_STRATEGY: 'pda_fifo_strategy',
}

export default function SettingsScreen() {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  const [apiUrl, setApiUrl] = useState('http://localhost:8080/api')
  const [printerIp, setPrinterIp] = useState('')
  const [printerPort, setPrinterPort] = useState('9100')
  const [fifoStrategy, setFifoStrategy] = useState('tail_first')
  const [isSaving, setIsSaving] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [testResult, setTestResult] = useState<string | null>(null)

  // Load settings on mount
  React.useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      const stored = await AsyncStorage.multiGet([
        SETTINGS_KEYS.API_URL,
        SETTINGS_KEYS.PRINTER_IP,
        SETTINGS_KEYS.PRINTER_PORT,
        SETTINGS_KEYS.FIFO_STRATEGY,
      ])
      const map = Object.fromEntries(stored)
      if (map[SETTINGS_KEYS.API_URL]) setApiUrl(map[SETTINGS_KEYS.API_URL])
      if (map[SETTINGS_KEYS.PRINTER_IP]) setPrinterIp(map[SETTINGS_KEYS.PRINTER_IP])
      if (map[SETTINGS_KEYS.PRINTER_PORT]) setPrinterPort(map[SETTINGS_KEYS.PRINTER_PORT])
      if (map[SETTINGS_KEYS.FIFO_STRATEGY]) setFifoStrategy(map[SETTINGS_KEYS.FIFO_STRATEGY])
    } catch {
      // ignore
    }
  }

  const handleSave = async () => {
    setIsSaving(true)
    setSaveSuccess(false)
    try {
      await AsyncStorage.multiSet([
        [SETTINGS_KEYS.API_URL, apiUrl],
        [SETTINGS_KEYS.PRINTER_IP, printerIp],
        [SETTINGS_KEYS.PRINTER_PORT, printerPort],
        [SETTINGS_KEYS.FIFO_STRATEGY, fifoStrategy],
      ])
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2000)
    } catch {
      Alert.alert('错误', '保存设置失败')
    } finally {
      setIsSaving(false)
    }
  }

  const handleTestConnection = async () => {
    setIsTesting(true)
    setTestResult(null)
    try {
      const start = Date.now()
      await api.get('/auth/me', { timeout: 5000 })
      const ms = Date.now() - start
      setTestResult(`✅ 连接成功 (${ms}ms)`)
    } catch (e: any) {
      setTestResult(`❌ 连接失败: ${e?.message || '网络错误'}`)
    } finally {
      setIsTesting(false)
    }
  }

  const strategies = [
    { key: 'tail_first', label: '尾数优先（推荐）', desc: '优先出库余量少的盘' },
    { key: 'time_fifo', label: '时间优先（FIFO）', desc: '严格按入库时间先后出库' },
    { key: 'mixed', label: '混合模式', desc: '同尾数时按时间排序' },
  ]

  return (
    <View style={styles.container}>
      <ScrollView style={styles.scrollArea} contentContainerStyle={styles.scrollContent}>
        {/* User Info */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.cardIcon}>👤</Text>
            <Text style={styles.cardTitle}>用户信息</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>用户名</Text>
            <Text style={styles.infoValue}>{user?.username || '--'}</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>角色</Text>
            <Text style={styles.infoValue}>{user?.role || '--'}</Text>
          </View>
          {user?.customer_name && (
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>客户</Text>
              <Text style={styles.infoValue}>{user.customer_name}</Text>
            </View>
          )}
        </View>

        {/* Server Config */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.cardIcon}>🌐</Text>
            <Text style={styles.cardTitle}>服务器设置</Text>
          </View>
          <Text style={styles.label}>API 地址</Text>
          <TextInput
            style={styles.input}
            value={apiUrl}
            onChangeText={setApiUrl}
            placeholder="http://192.168.1.100:8080/api"
            autoCapitalize="none"
          />
          <TouchableOpacity
            style={[styles.button, styles.testButton]}
            onPress={handleTestConnection}
            disabled={isTesting}
          >
            {isTesting ? <ActivityIndicator color="#fff" size="small" /> : <Text style={styles.buttonText}>测试连接</Text>}
          </TouchableOpacity>
          {testResult && (
            <Text style={[styles.testResult, testResult.startsWith('✅') ? styles.testSuccess : styles.testFail]}>
              {testResult}
            </Text>
          )}
        </View>

        {/* Printer Config */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.cardIcon}>🖨️</Text>
            <Text style={styles.cardTitle}>标签打印机</Text>
          </View>
          <Text style={styles.label}>打印机 IP</Text>
          <TextInput
            style={styles.input}
            value={printerIp}
            onChangeText={setPrinterIp}
            placeholder="192.168.1.200"
            autoCapitalize="none"
          />
          <Text style={styles.label}>端口</Text>
          <TextInput
            style={styles.input}
            value={printerPort}
            onChangeText={setPrinterPort}
            placeholder="9100"
            keyboardType="numeric"
          />
        </View>

        {/* FIFO Strategy */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.cardIcon}>📊</Text>
            <Text style={styles.cardTitle}>出库策略</Text>
          </View>
          {strategies.map((s) => (
            <TouchableOpacity
              key={s.key}
              style={[styles.strategyItem, fifoStrategy === s.key && styles.strategyItemActive]}
              onPress={() => setFifoStrategy(s.key)}
            >
              <View style={styles.radioOuter}>
                {fifoStrategy === s.key && <View style={styles.radioInner} />}
              </View>
              <View style={styles.strategyContent}>
                <Text style={[styles.strategyLabel, fifoStrategy === s.key && { color: Colors.primary }]}>
                  {s.label}
                </Text>
                <Text style={styles.strategyDesc}>{s.desc}</Text>
              </View>
            </TouchableOpacity>
          ))}
        </View>

        {/* Save */}
        <TouchableOpacity
          style={[styles.button, styles.saveButton]}
          onPress={handleSave}
          disabled={isSaving}
        >
          {isSaving ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>保存设置</Text>}
        </TouchableOpacity>
        {saveSuccess && (
          <Text style={styles.saveSuccess}>✅ 设置已保存</Text>
        )}

        {/* Logout */}
        <TouchableOpacity style={styles.logoutButton} onPress={logout}>
          <Text style={styles.logoutText}>退出登录</Text>
        </TouchableOpacity>

        {/* Version */}
        <Text style={styles.version}>版本 1.0.0 (Build 2026.06)</Text>
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg },
  scrollArea: { flex: 1 },
  scrollContent: { padding: 12, paddingBottom: 40 },
  card: { backgroundColor: Colors.card, borderRadius: 12, padding: 16, marginBottom: 12, elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 4 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  cardIcon: { fontSize: 22, marginRight: 8 },
  cardTitle: { fontSize: 18, fontWeight: 'bold', color: Colors.text },
  infoRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#f5f5f5' },
  infoLabel: { fontSize: 15, color: Colors.textSecondary },
  infoValue: { fontSize: 15, color: Colors.text, fontWeight: '600' },
  label: { fontSize: 14, color: Colors.textSecondary, fontWeight: '600', marginBottom: 4, marginTop: 4 },
  input: { backgroundColor: '#fff', padding: 12, borderRadius: 8, marginBottom: 10, fontSize: 16, borderWidth: 1, borderColor: '#ddd' },
  button: { padding: 14, borderRadius: 8, alignItems: 'center', marginBottom: 8 },
  testButton: { backgroundColor: Colors.info },
  saveButton: { backgroundColor: Colors.primary, marginBottom: 4 },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  testResult: { textAlign: 'center', fontSize: 14, marginTop: 4 },
  testSuccess: { color: Colors.success },
  testFail: { color: Colors.danger },
  saveSuccess: { textAlign: 'center', color: Colors.success, fontSize: 14, fontWeight: '600' },
  strategyItem: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, paddingHorizontal: 8, borderRadius: 8, marginBottom: 6 },
  strategyItemActive: { backgroundColor: '#e6f0ff' },
  radioOuter: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: Colors.primary, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  radioInner: { width: 10, height: 10, borderRadius: 5, backgroundColor: Colors.primary },
  strategyContent: { flex: 1 },
  strategyLabel: { fontSize: 15, fontWeight: '600', color: Colors.text },
  strategyDesc: { fontSize: 13, color: Colors.textSecondary, marginTop: 1 },
  logoutButton: { marginTop: 12, padding: 16, borderRadius: 8, alignItems: 'center', borderWidth: 1, borderColor: Colors.danger, backgroundColor: '#fff' },
  logoutText: { color: Colors.danger, fontSize: 16, fontWeight: '600' },
  version: { textAlign: 'center', color: Colors.textSecondary, fontSize: 13, marginTop: 16 },
})
