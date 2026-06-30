import React, { useState, useCallback } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, Alert,
  ScrollView, ActivityIndicator, Linking,
} from 'react-native'
import AsyncStorage from '@react-native-async-storage/async-storage'
import { useAuthStore } from '../store/authStore'
import { useOperator, OPERATOR_KEY } from '../hooks/useOperator'
import api, { updateBaseUrl, loadBaseUrl, checkAppVersionApi } from '../api'
import type { AppVersionInfo } from '../api'
import { PersonIcon, GlobeIcon, PrinterIcon, UpdateIcon } from '../components/Icons'
import { APP_VERSION, APP_BUILD } from '../constants/version'

const Colors = {
  primary: '#0066CC', success: '#00AA55', warning: '#FF9900', danger: '#DD3333',
  info: '#3399CC', card: '#FFFFFF', bg: '#F5F7FA', text: '#1A1A1A', textSecondary: '#666666',
}

const SETTINGS_KEYS = {
  API_URL: 'pda_api_url',
  PRINTER_IP: 'pda_printer_ip',
  PRINTER_PORT: 'pda_printer_port',
  OPERATOR: OPERATOR_KEY,
}

/**
 * Simple semver compare: returns >0 if v1>v2, <0 if v1<v2, 0 if equal.
 * Supports "x.y.z" format only (no pre-release).
 */
function cmpVer(v1: string, v2: string): number {
  const p1 = v1.split('.').map(Number)
  const p2 = v2.split('.').map(Number)
  for (let i = 0; i < Math.max(p1.length, p2.length); i++) {
    const a = p1[i] || 0
    const b = p2[i] || 0
    if (a !== b) return a - b
  }
  return 0
}

function showUpdateAlert(info: AppVersionInfo, isForce: boolean) {
  const notes = info.release_notes
    ? `更新说明:\n${info.release_notes}`
    : ''

  const buttons: any[] = [
    { text: '取消', style: 'cancel' },
  ]

  // 如果有下载链接则显示「立即更新」
  if (info.download_url) {
    buttons.push({
      text: '立即更新',
      onPress: () => {
        Linking.openURL(info.download_url).catch(() =>
          Alert.alert('无法打开下载链接', info.download_url)
        )
      },
    })
  }

  if (isForce) {
    // 强制更新 — 只有「立即更新」按钮
    buttons.length = 0
    if (info.download_url) {
      buttons.push({
        text: '立即更新',
        onPress: () => {
          Linking.openURL(info.download_url).catch(() =>
            Alert.alert('无法打开下载链接', info.download_url)
          )
        },
      })
    }
  }

  Alert.alert(
    isForce ? '需要强制更新' : '发现新版本',
    `当前版本: v${APP_VERSION}\n最新版本: v${info.latest_version}\n\n${notes}`.trim(),
    buttons,
    { cancelable: !isForce },
  )
}

export default function SettingsScreen() {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const { operator, setOperator } = useOperator()

  const [apiUrl, setApiUrl] = useState('')
  const [printerIp, setPrinterIp] = useState('')
  const [printerPort, setPrinterPort] = useState('9100')
  const [operatorInput, setOperatorInput] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [testResult, setTestResult] = useState<string | null>(null)

  // ── 版本更新 ──
  const [isChecking, setIsChecking] = useState(false)
  const [updateMsg, setUpdateMsg] = useState<string | null>(null)

  // Load settings on mount
  React.useEffect(() => {
    loadSettings()
  }, [])

  // Sync operator from hook into local input
  React.useEffect(() => {
    setOperatorInput(operator)
  }, [operator])

  const loadSettings = async () => {
    try {
      const stored = await AsyncStorage.multiGet([
        SETTINGS_KEYS.API_URL,
        SETTINGS_KEYS.PRINTER_IP,
        SETTINGS_KEYS.PRINTER_PORT,
      ])
      const map = Object.fromEntries(stored)
      // API URL: 优先 AsyncStorage 中保存的值，无则从 DEFAULT_BASE_URL 加载
      if (map[SETTINGS_KEYS.API_URL]) {
        setApiUrl(map[SETTINGS_KEYS.API_URL])
      } else {
        const defaultUrl = await loadBaseUrl()
        setApiUrl(defaultUrl)
      }
      if (map[SETTINGS_KEYS.PRINTER_IP]) setPrinterIp(map[SETTINGS_KEYS.PRINTER_IP])
      if (map[SETTINGS_KEYS.PRINTER_PORT]) setPrinterPort(map[SETTINGS_KEYS.PRINTER_PORT])
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
      ])
      // 同步更新 API 实例
      await updateBaseUrl(apiUrl)
      // 同步保存操作员设置（通过 Hook 持久化）
      if (operatorInput.trim()) {
        await setOperator(operatorInput.trim())
      }
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
      // Temporarily set the new URL for testing
      await updateBaseUrl(apiUrl)
      const start = Date.now()
      await api.get('/auth/me', { timeout: 5000 })
      const ms = Date.now() - start
      setTestResult(`连接成功 (${ms}ms)`)
    } catch (e: any) {
      setTestResult(`连接失败: ${e?.message || '网络错误'}`)
    } finally {
      setIsTesting(false)
    }
  }

  // ── 检查更新 ──
  const handleCheckUpdate = useCallback(async () => {
    setIsChecking(true)
    setUpdateMsg(null)
    try {
      const info = await checkAppVersionApi()

      if (!info.latest_version) {
        setUpdateMsg('服务器未配置版本信息')
        return
      }

      const cmp = cmpVer(APP_VERSION, info.latest_version)
      const minCmp = info.min_version ? cmpVer(APP_VERSION, info.min_version) : 0
      const isForce = minCmp < 0  // 当前版本低于最低兼容版本 → 强制更新

      if (cmp >= 0 && !isForce) {
        setUpdateMsg(`已是最新版本 (v${APP_VERSION})`)
        return
      }

      // 有新版本 → 弹出更新提示
      showUpdateAlert(info, isForce)
      setUpdateMsg(`发现新版本 v${info.latest_version}，请在弹窗中操作`)
    } catch (e: any) {
      setUpdateMsg('检查失败: ' + (e?.message || '网络错误'))
    } finally {
      setIsChecking(false)
    }
  }, [])

  return (
    <View style={styles.container}>
      <ScrollView style={styles.scrollArea} contentContainerStyle={styles.scrollContent}>
        {/* User Info */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={{ marginRight: 8 }}><PersonIcon size={22} color={Colors.primary} /></View>
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

        {/* Operator Config */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={{ marginRight: 8 }}><PersonIcon size={22} color={Colors.primary} /></View>
            <Text style={styles.cardTitle}>操作员设置</Text>
          </View>
          <Text style={styles.infoText}>
            此处设置操作员姓名后，所有业务页面（入库、出库、上架等）将自动读取此设置，无需重复输入。
          </Text>
          <Text style={styles.label}>操作员姓名</Text>
          <TextInput
            style={styles.input}
            value={operatorInput}
            onChangeText={setOperatorInput}
            placeholder={user?.username || '输入操作员姓名'}
            autoCapitalize="characters"
          />
          {!operatorInput.trim() && user?.username && (
            <Text style={styles.hint}>留空将使用登录用户名「{user.username}」</Text>
          )}
        </View>

        {/* Server Config */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={{ marginRight: 8 }}><GlobeIcon size={22} color={Colors.primary} /></View>
            <Text style={styles.cardTitle}>服务器设置</Text>
          </View>
          <Text style={styles.label}>API 地址</Text>
          <TextInput
            style={styles.input}
            value={apiUrl}
            onChangeText={setApiUrl}
            placeholder="http://101.34.63.68:8080/api"
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
            <Text style={[styles.testResult, testResult.startsWith('连接成功') ? styles.testSuccess : styles.testFail]}>
              {testResult}
            </Text>
          )}
        </View>

        {/* Printer Config */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={{ marginRight: 8 }}><PrinterIcon size={22} color={Colors.primary} /></View>
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

        {/* App Update */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={{ marginRight: 8 }}><UpdateIcon size={22} color={Colors.primary} /></View>
            <Text style={styles.cardTitle}>App 更新</Text>
          </View>
          <Text style={styles.label}>当前版本</Text>
          <Text style={styles.versionBadge}>v{APP_VERSION} (Build {APP_BUILD})</Text>
          <TouchableOpacity
            style={[styles.button, styles.updateButton]}
            onPress={handleCheckUpdate}
            disabled={isChecking}
          >
            {isChecking ? (
              <ActivityIndicator color="#fff" size="small" />
            ) : (
              <Text style={styles.buttonText}>检查更新</Text>
            )}
          </TouchableOpacity>
          {updateMsg && (
            <Text style={[styles.testResult, updateMsg.includes('最新') ? styles.testSuccess : styles.testFail]}>
              {updateMsg}
            </Text>
          )}
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
          <Text style={styles.saveSuccess}>设置已保存</Text>
        )}

        {/* Logout */}
        <TouchableOpacity style={styles.logoutButton} onPress={logout}>
          <Text style={styles.logoutText}>退出登录</Text>
        </TouchableOpacity>

        {/* Version */}
        <Text style={styles.version}>版本 {APP_VERSION} (Build {APP_BUILD})</Text>
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
  cardTitle: { fontSize: 18, fontWeight: 'bold', color: Colors.text },
  infoRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#f5f5f5' },
  infoLabel: { fontSize: 15, color: Colors.textSecondary },
  infoValue: { fontSize: 15, color: Colors.text, fontWeight: '600' },
  label: { fontSize: 14, color: Colors.textSecondary, fontWeight: '600', marginBottom: 4, marginTop: 4 },
  input: { backgroundColor: '#fff', padding: 12, borderRadius: 8, marginBottom: 10, fontSize: 16, borderWidth: 1, borderColor: '#ddd' },
  button: { padding: 14, borderRadius: 8, alignItems: 'center', marginBottom: 8 },
  testButton: { backgroundColor: Colors.info },
  updateButton: { backgroundColor: Colors.warning },
  versionBadge: { fontSize: 16, fontWeight: '700', color: Colors.text, marginBottom: 8 },
  saveButton: { backgroundColor: Colors.primary, marginBottom: 4 },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  testResult: { textAlign: 'center', fontSize: 14, marginTop: 4 },
  testSuccess: { color: Colors.success },
  testFail: { color: Colors.danger },
  saveSuccess: { textAlign: 'center', color: Colors.success, fontSize: 14, fontWeight: '600' },
  logoutButton: { marginTop: 12, padding: 16, borderRadius: 8, alignItems: 'center', borderWidth: 1, borderColor: Colors.danger, backgroundColor: '#fff' },
  logoutText: { color: Colors.danger, fontSize: 16, fontWeight: '600' },
  version: { textAlign: 'center', color: Colors.textSecondary, fontSize: 13, marginTop: 16 },
  infoText: { fontSize: 13, color: Colors.textSecondary, lineHeight: 18, marginBottom: 10 },
  hint: { fontSize: 13, color: Colors.textSecondary, fontStyle: 'italic', marginTop: -6, marginBottom: 4 },
})
