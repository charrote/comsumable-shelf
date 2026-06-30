import { useState, useEffect } from 'react'
import { Card, Button, Input, Spin, message, Typography, Tooltip, Space, Divider, Alert, Tag } from 'antd'
import { DownloadOutlined, CheckOutlined, ReloadOutlined, ScanOutlined } from '@ant-design/icons'
import { getSettingsApi, updateSettingApi, appendChangelogApi } from '../api'

const { Text, Title } = Typography
const { TextArea } = Input

/** latest-apk.json 的响应结构 */
interface ApkManifest {
  version: string
  buildNumber: string
  apkPath: string
  updatedAt: string
}

export function AppVersionUpdatePage() {
  const [loading, setLoading] = useState(false)

  // App 版本更新状态
  const [appLatestVersion, setAppLatestVersion] = useState('')
  const [appMinVersion, setAppMinVersion] = useState('')
  const [appDownloadUrl, setAppDownloadUrl] = useState('')
  const [appReleaseNotes, setAppReleaseNotes] = useState('')
  const [appSaving, setAppSaving] = useState(false)

  // 自动检测状态
  const [autoDetectLoading, setAutoDetectLoading] = useState(false)
  const [detectedManifest, setDetectedManifest] = useState<ApkManifest | null>(null)

  const loadSettings = async () => {
    setLoading(true)
    try {
      const res = await getSettingsApi()
      const data = res.data
      const list = Array.isArray(data) ? data : data.settings || []

      const extract = (key: string, fallback = '') =>
        list.find((s: any) => s.key === key)?.value ?? fallback
      setAppLatestVersion(extract('app_latest_version'))
      setAppMinVersion(extract('app_min_version'))
      setAppDownloadUrl(extract('app_download_url'))
      setAppReleaseNotes(extract('app_release_notes'))
    } catch (err: any) {
      message.error(err.response?.data?.detail || '加载设置失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSettings()
  }, [])

  // ── 自动检测最新版本（从 latest-apk.json） ──
  const handleAutoDetect = async () => {
    setAutoDetectLoading(true)
    setDetectedManifest(null)
    try {
      const res = await fetch('/apk/latest-apk.json', { cache: 'no-store' })
      if (!res.ok) throw new Error(`HTTP ${res.status} — 服务器上尚无构建产物`)
      const manifest: ApkManifest = await res.json()
      if (!manifest?.version || !manifest?.apkPath) {
        throw new Error('清单数据不完整')
      }

      // 自动填充版本号
      setAppLatestVersion(manifest.version)

      // 自动拼接 APK 下载地址（基于当前页面 origin + apkPath）
      const autoUrl = `${window.location.origin}${manifest.apkPath}`
      setAppDownloadUrl(autoUrl)

      // 记录检测结果供展示
      setDetectedManifest(manifest)

      message.success({
        content: `检测到最新构建: v${manifest.version}（构建 ${manifest.buildNumber}），已自动填充版本号和下载地址`,
        duration: 5,
      })
    } catch (err: any) {
      message.error({
        content: `自动检测失败: ${err.message || '无法获取 latest-apk.json'}`,
        duration: 5,
      })
    } finally {
      setAutoDetectLoading(false)
    }
  }

  // 保存全部
  const handleSaveAppVersion = async () => {
    setAppSaving(true)
    try {
      await Promise.all([
        updateSettingApi('app_latest_version', appLatestVersion, 'PDA App 最新版本号'),
        updateSettingApi('app_min_version', appMinVersion, 'PDA App 最低兼容版本号'),
        updateSettingApi('app_download_url', appDownloadUrl, 'PDA App APK 下载地址'),
        updateSettingApi('app_release_notes', appReleaseNotes, 'PDA App 更新说明'),
      ])

      // 同步写入 CHANGELOG.md
      if (appLatestVersion && appReleaseNotes) {
        await appendChangelogApi(appLatestVersion, appReleaseNotes)
      }

      message.success('App 版本配置已保存，更新日志已同步')
      await loadSettings()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '保存失败')
    } finally {
      setAppSaving(false)
    }
  }

  // 保存单个字段（行内保存）
  const handleSaveSingleAppField = async (key: string, value: string) => {
    try {
      const descriptions: Record<string, string> = {
        app_latest_version: 'PDA App 最新版本号',
        app_min_version: 'PDA App 最低兼容版本号',
        app_download_url: 'PDA App APK 下载地址',
        app_release_notes: 'PDA App 更新说明',
      }
      await updateSettingApi(key, value, descriptions[key] || '')
      message.success('已更新')
      await loadSettings()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '保存失败')
    }
  }

  return (
    <div>
      <Title level={3}>APP 版本更新</Title>
      <Spin spinning={loading}>
        <Card>
          <div style={{ marginBottom: 16 }}>
            <Text type="secondary">
              配置 PDA App 的版本更新信息，用户端在设置页面点击「检查更新」时将从 <Text code>/api/app/version</Text> 获取以下配置。
            </Text>
          </div>

          {/* 自动检测结果提示 */}
          {detectedManifest && (
            <Alert
              type="success"
              showIcon
              icon={<ScanOutlined />}
              closable
              onClose={() => setDetectedManifest(null)}
              style={{ marginBottom: 16, borderRadius: 8 }}
              message={
                <div>
                  <Text strong>已检测到最新构建产物</Text>
                  <div style={{ marginTop: 4 }}>
                    <Space size={16} wrap>
                      <span>
                        <Text type="secondary">版本: </Text>
                        <Tag color="blue">{detectedManifest.version}</Tag>
                      </span>
                      <span>
                        <Text type="secondary">构建: </Text>
                        <Tag>{detectedManifest.buildNumber}</Tag>
                      </span>
                      <span>
                        <Text type="secondary">APK: </Text>
                        <Text code style={{ fontSize: 12 }}>
                          {detectedManifest.apkPath}
                        </Text>
                      </span>
                      <span>
                        <Text type="secondary">更新于: </Text>
                        <Text>{detectedManifest.updatedAt?.replace('T', ' ').replace('Z', '')}</Text>
                      </span>
                    </Space>
                  </div>
                  <div style={{ marginTop: 6 }}>
                    <Text type="success">
                      版本号和下载地址已自动填充，请确认后保存
                    </Text>
                  </div>
                </div>
              }
            />
          )}

          <Divider orientation="left" plain>版本信息</Divider>

          {/* 版本号行 */}
          <div style={{ display: 'flex', gap: 24, marginBottom: 16, flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 280px' }}>
              <Text strong>最新版本号</Text>
              <Input.Search
                value={appLatestVersion}
                onChange={(e) => setAppLatestVersion(e.target.value)}
                placeholder="如 3.1.0"
                style={{ marginTop: 4 }}
                enterButton={<CheckOutlined />}
                onSearch={() => handleSaveSingleAppField('app_latest_version', appLatestVersion)}
              />
            </div>
            <div style={{ flex: '1 1 280px' }}>
              <Text strong>最低兼容版本</Text>
              <Tooltip title="低于此版本的 APP 打开后将被强制更新">
                <Input.Search
                  value={appMinVersion}
                  onChange={(e) => setAppMinVersion(e.target.value)}
                  placeholder="如 3.0.0"
                  style={{ marginTop: 4 }}
                  enterButton={<CheckOutlined />}
                  onSearch={() => handleSaveSingleAppField('app_min_version', appMinVersion)}
                />
              </Tooltip>
            </div>
          </div>

          <Divider orientation="left" plain>下载配置</Divider>

          {/* 下载地址 */}
          <div style={{ marginBottom: 16 }}>
            <Text strong>APK 下载地址</Text>
            <Input.Search
              value={appDownloadUrl}
              onChange={(e) => setAppDownloadUrl(e.target.value)}
              placeholder="https://example.com/smes-pda-v3.1.0.apk"
              style={{ marginTop: 4 }}
              enterButton={<CheckOutlined />}
              onSearch={() => handleSaveSingleAppField('app_download_url', appDownloadUrl)}
            />
          </div>

          <Divider orientation="left" plain>更新说明</Divider>

          {/* 更新说明 */}
          <div style={{ marginBottom: 16 }}>
            <TextArea
              value={appReleaseNotes}
              onChange={(e) => setAppReleaseNotes(e.target.value)}
              placeholder="- 优化扫码性能&#10;- 修复问题&#10;- 新增功能"
              rows={5}
              style={{ marginTop: 4 }}
            />
          </div>

          <Divider />

          {/* 操作栏 */}
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <Button
              type="primary"
              icon={<ScanOutlined />}
              onClick={handleAutoDetect}
              loading={autoDetectLoading}
              size="large"
            >
              自动检测最新版本
            </Button>
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              onClick={handleSaveAppVersion}
              loading={appSaving}
              size="large"
            >
              保存 App 版本配置
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                window.open('/api/app/version', '_blank')
              }}
            >
              预览 API 响应
            </Button>
          </div>
        </Card>
      </Spin>
    </div>
  )
}
