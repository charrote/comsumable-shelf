import { useState, useEffect } from 'react'
import { Card, Button, Input, Spin, message, Typography, Tooltip, Space, Divider } from 'antd'
import { DownloadOutlined, CheckOutlined, ReloadOutlined } from '@ant-design/icons'
import { getSettingsApi, updateSettingApi } from '../api'

const { Text, Title } = Typography
const { TextArea } = Input

export function AppVersionUpdatePage() {
  const [loading, setLoading] = useState(false)

  // App 版本更新状态
  const [appLatestVersion, setAppLatestVersion] = useState('')
  const [appMinVersion, setAppMinVersion] = useState('')
  const [appDownloadUrl, setAppDownloadUrl] = useState('')
  const [appReleaseNotes, setAppReleaseNotes] = useState('')
  const [appSaving, setAppSaving] = useState(false)

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
      message.success('App 版本配置已保存')
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
          <div style={{ display: 'flex', gap: 12 }}>
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
