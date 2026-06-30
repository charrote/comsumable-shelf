import React, { useState, useEffect } from 'react'
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ActivityIndicator, ScrollView } from 'react-native'
import { useAuthStore } from '../store/authStore'
import { loadBaseUrl, updateBaseUrl } from '../api'
import { APP_VERSION, APP_BUILD } from '../constants/version'

export default function LoginScreen() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [apiUrl, setApiUrl] = useState('')
  const [showServerConfig, setShowServerConfig] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [testResult, setTestResult] = useState<string | null>(null)
  const { login, isLoading, error, clearError } = useAuthStore()

  useEffect(() => {
    loadBaseUrl().then(setApiUrl)
  }, [])

  const handleLogin = async () => {
    if (!username || !password) return
    clearError()
    try {
      await login(username, password)
    } catch {
      // error is set in store
    }
  }

  const handleTestConnection = async () => {
    setIsTesting(true)
    setTestResult(null)
    try {
        // Save current URL first, then test
      await updateBaseUrl(apiUrl)
      const start = Date.now()
      // Use the api module (it will have the new baseURL)
      const { default: api } = await import('../api')
      await api.get('/auth/me', {
        timeout: 5000,
        validateStatus: (status) => status < 500, // 401/403 也算连接成功
      })
      const ms = Date.now() - start
      setTestResult(`连接成功 (${ms}ms)`)
    } catch (e: any) {
      if (e?.response) {
        setTestResult(`服务器返回错误: HTTP ${e.response.status}`)
      } else if (e?.code === 'ECONNABORTED') {
        setTestResult('连接超时，请检查IP和端口是否正确')
      } else if (e?.message?.includes('Network Error')) {
        setTestResult('无法连接，请检查网络和IP地址')
      } else {
        setTestResult(`连接失败: ${e?.message || '网络错误'}`)
      }
    } finally {
      setIsTesting(false)
    }
  }

  return (
    <ScrollView
      style={styles.scrollView}
      contentContainerStyle={styles.container}
      keyboardShouldPersistTaps="handled"
    >
      <Text style={styles.title}>智能料架 PDA</Text>
      <Text style={styles.subtitle}>SMT 物料管理系统</Text>

      {error ? (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <TextInput
        style={styles.input}
        placeholder="用户名"
        value={username}
        onChangeText={setUsername}
        autoCapitalize="none"
        editable={!isLoading}
      />
      <TextInput
        style={styles.input}
        placeholder="密码"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
        editable={!isLoading}
      />
      <TouchableOpacity
        style={[styles.button, isLoading && styles.buttonDisabled]}
        onPress={handleLogin}
        disabled={isLoading}
      >
        {isLoading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>登录</Text>
        )}
      </TouchableOpacity>

      {/* Server Config Toggle */}
      <TouchableOpacity
        style={styles.configToggle}
        onPress={() => setShowServerConfig(!showServerConfig)}
      >
        <Text style={styles.configToggleText}>
          {showServerConfig ? '▲' : '▼'} 服务器设置
        </Text>
      </TouchableOpacity>

      {showServerConfig && (
        <View style={styles.serverConfigCard}>
          <Text style={styles.configLabel}>API 地址</Text>
          <TextInput
            style={styles.configInput}
            value={apiUrl}
            onChangeText={setApiUrl}
            placeholder="http://101.34.63.68:8080/api"
            autoCapitalize="none"
            autoCorrect={false}
          />
          <TouchableOpacity
            style={[styles.testButton, isTesting && styles.buttonDisabled]}
            onPress={handleTestConnection}
            disabled={isTesting}
          >
            {isTesting ? (
              <ActivityIndicator color="#fff" size="small" />
            ) : (
              <Text style={styles.testButtonText}>测试连接</Text>
            )}
          </TouchableOpacity>
          {testResult && (
            <Text style={[styles.testResult, testResult.startsWith('连接成功') ? styles.testSuccess : styles.testFail]}>
              {testResult}
            </Text>
          )}
        </View>
      )}

      <Text style={styles.version}>版本 {APP_VERSION} (Build {APP_BUILD})</Text>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  scrollView: { flex: 1, backgroundColor: '#f5f5f5' },
  container: { flexGrow: 1, justifyContent: 'center', padding: 24 },
  title: { fontSize: 28, fontWeight: 'bold', textAlign: 'center', marginBottom: 4, color: '#1890ff' },
  subtitle: { fontSize: 14, textAlign: 'center', marginBottom: 32, color: '#666' },
  errorBox: { backgroundColor: '#fff1f0', padding: 12, borderRadius: 8, marginBottom: 16, borderWidth: 1, borderColor: '#ffa39e' },
  errorText: { color: '#cf1322', fontSize: 14 },
  input: { backgroundColor: '#fff', padding: 14, borderRadius: 8, marginBottom: 16, fontSize: 16, borderWidth: 1, borderColor: '#ddd' },
  button: { backgroundColor: '#1890ff', padding: 16, borderRadius: 8, alignItems: 'center' },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: '#fff', fontSize: 18, fontWeight: '600' },

  // Server config styles
  configToggle: { marginTop: 20, alignItems: 'center', paddingVertical: 8 },
  configToggleText: { color: '#1890ff', fontSize: 14 },
  serverConfigCard: { backgroundColor: '#fff', borderRadius: 12, padding: 16, marginTop: 8, elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 4 },
  configLabel: { fontSize: 14, color: '#666', fontWeight: '600', marginBottom: 4 },
  configInput: { backgroundColor: '#f5f5f5', padding: 12, borderRadius: 8, marginBottom: 10, fontSize: 15, borderWidth: 1, borderColor: '#ddd' },
  testButton: { backgroundColor: '#52c41a', padding: 12, borderRadius: 8, alignItems: 'center' },
  testButtonText: { color: '#fff', fontSize: 15, fontWeight: '600' },
  testResult: { textAlign: 'center', fontSize: 14, marginTop: 8 },
  testSuccess: { color: '#52c41a' },
  testFail: { color: '#ff4d4f' },
  version: { textAlign: 'center', fontSize: 13, color: '#999', marginTop: 24 },
})
