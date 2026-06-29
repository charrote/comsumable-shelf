import { useState, useEffect } from 'react'
import { Card, Table, Button, Modal, Input, Select, Space, Spin, message, Switch, Divider, Tag, Typography, Tooltip } from 'antd'
import { DownloadOutlined, CheckOutlined, ReloadOutlined } from '@ant-design/icons'
import { getSettingsApi, updateSettingApi } from '../api'

const { Text, Title } = Typography
const { TextArea } = Input

// ── Known setting keys and their input configurations ──
interface SettingMeta {
  inputType: 'text' | 'number' | 'select'
  options?: { label: string; value: string }[]
}

const SETTING_META: Record<string, SettingMeta> = {
  fifo_strategy: {
    inputType: 'select',
    options: [
      { label: '尾数优先 (tail_first)', value: 'tail_first' },
      { label: '时间优先 (time_fifo)', value: 'time_fifo' },
      { label: '混合 (mixed)', value: 'mixed' },
    ],
  },
  duplicate_scan_behavior: {
    inputType: 'select',
    options: [
      { label: '拦截 (block)', value: 'block' },
      { label: '警告并放行 (warn)', value: 'warn' },
      { label: '不检查 (force)', value: 'force' },
    ],
  },
  default_slot_capacity: {
    inputType: 'number',
  },
}

// ── App 版本更新 settings keys（从通用设置中排除，使用专属 UI） ──
const APP_VERSION_KEYS = ['app_latest_version', 'app_min_version', 'app_download_url', 'app_release_notes']

// ── 储位灯颜色配置 ──
interface PickingColorOption {
  key: string
  label: string
  hex: string
  textColor: string
}

const PICKING_COLORS: PickingColorOption[] = [
  { key: 'red', label: '红色', hex: '#ff4d4f', textColor: '#fff' },
  { key: 'green', label: '绿色', hex: '#52c41a', textColor: '#fff' },
  { key: 'yellow', label: '黄色', hex: '#faad14', textColor: '#000' },
  { key: 'blue', label: '蓝色', hex: '#1677ff', textColor: '#fff' },
  { key: 'magenta', label: '品红', hex: '#eb2f96', textColor: '#fff' },
  { key: 'cyan', label: '青色', hex: '#13c2c2', textColor: '#fff' },
  { key: 'white', label: '白色', hex: '#ffffff', textColor: '#000' },
]

export function SystemSettingsPage() {
  const [settings, setSettings] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingKey, setEditingKey] = useState('')
  const [editingDescription, setEditingDescription] = useState('')
  const [editValue, setEditValue] = useState('')
  const [saving, setSaving] = useState(false)

  // 储位灯颜色配置状态
  const [pickingColors, setPickingColors] = useState<string[]>([])
  const [colorConfigKey, setColorConfigKey] = useState('')

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
      setSettings(list)

      // 加载 App 版本配置
      const extract = (key: string, fallback = '') =>
        list.find((s: any) => s.key === key)?.value ?? fallback
      setAppLatestVersion(extract('app_latest_version'))
      setAppMinVersion(extract('app_min_version'))
      setAppDownloadUrl(extract('app_download_url'))
      setAppReleaseNotes(extract('app_release_notes'))

      // 加载储位灯颜色配置
      const colorSetting = list.find((s: any) => s.key === 'picking_task_colors')
      if (colorSetting) {
        setColorConfigKey(colorSetting.key)
        try {
          const colors = JSON.parse(colorSetting.value)
          if (Array.isArray(colors)) {
            setPickingColors(colors)
          }
        } catch {
          setPickingColors(PICKING_COLORS.map(c => c.key))
        }
      }
    } catch (err: any) {
      message.error(err.response?.data?.detail || '加载设置失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSettings()
  }, [])

  const handleEdit = (record: any) => {
    setEditingKey(record.key)
    setEditingDescription(record.description || '')
    setEditValue(record.value)
    setModalOpen(true)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateSettingApi(editingKey, editValue, editingDescription)
      message.success('修改成功')
      setModalOpen(false)
      await loadSettings()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '修改失败')
    } finally {
      setSaving(false)
    }
  }

  const handleColorToggle = async (colorKey: string, enabled: boolean) => {
    let newColors: string[]
    if (enabled) {
      newColors = [...pickingColors, colorKey]
    } else {
      newColors = pickingColors.filter(c => c !== colorKey)
    }
    // 至少保留一个颜色
    if (newColors.length === 0) {
      message.warning('至少需要保留一个颜色')
      return
    }
    setPickingColors(newColors)
    try {
      await updateSettingApi('picking_task_colors', JSON.stringify(newColors), '储位灯任务颜色配置（JSON数组，仅勾选的颜色可用于发料单亮灯任务）')
      message.success('储位灯颜色配置已更新')
    } catch (err: any) {
      message.error(err.response?.data?.detail || '保存失败')
      // 回滚
      setPickingColors(pickingColors)
    }
  }

  // ── App 版本更新：保存全部 ──
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

  // ── App 版本更新：保存单个字段（行内保存） ──
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

  const meta = SETTING_META[editingKey]

  const renderValueInput = () => {
    if (!meta) {
      return <Input value={editValue} onChange={(e) => setEditValue(e.target.value)} style={{ marginTop: 4 }} />
    }
    switch (meta.inputType) {
      case 'select':
        return (
          <Select
            value={editValue}
            onChange={setEditValue}
            style={{ width: '100%', marginTop: 4 }}
            options={meta.options}
          />
        )
      case 'number':
        return (
          <Input
            type="number"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            style={{ marginTop: 4 }}
            placeholder="留空表示不限制"
          />
        )
      default:
        return <Input value={editValue} onChange={(e) => setEditValue(e.target.value)} style={{ marginTop: 4 }} />
    }
  }

  const columns = [
    { title: '设置项', dataIndex: 'key', key: 'key', width: 200 },
    { title: '描述', dataIndex: 'description', key: 'description' },
    { title: '值', dataIndex: 'value', key: 'value', width: 120, ellipsis: true },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: any, record: any) => (
        <Button type="link" size="small" onClick={() => handleEdit(record)}>
          修改
        </Button>
      ),
    },
  ]

  return (
    <div>
      <Title level={3}>系统设置</Title>
      <Spin spinning={loading}>
        {/* ── 常规设置 ── */}
        <Card title="通用设置" style={{ marginBottom: 24 }}>
          <Table
            columns={columns}
            dataSource={settings.filter(s => s.key !== 'picking_task_colors' && !APP_VERSION_KEYS.includes(s.key))}
            pagination={false}
            rowKey="key"
          />
        </Card>

        {/* ── 储位灯任务颜色配置 ── */}
        <Card title="储位灯任务" style={{ marginBottom: 24 }}>
          <div style={{ marginBottom: 16 }}>
            <Text type="secondary">
              储位灯有 7 种颜色，每一种颜色代表一张发料单任务，可同时支持 7 张发料单并发落架拣料。
              只有勾选的颜色才会被用于发料单亮灯任务。
            </Text>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
            {PICKING_COLORS.map(color => {
              const enabled = pickingColors.includes(color.key)
              return (
                <Card
                  key={color.key}
                  size="small"
                  style={{
                    width: 160,
                    border: `2px solid ${enabled ? color.hex : '#d9d9d9'}`,
                    opacity: enabled ? 1 : 0.5,
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                    {/* 颜色预览圆块 */}
                    <div
                      style={{
                        width: 48,
                        height: 48,
                        borderRadius: '50%',
                        backgroundColor: color.hex,
                        border: color.key === 'white' ? '1px solid #d9d9d9' : 'none',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: color.textColor,
                        fontWeight: 'bold',
                        fontSize: 12,
                      }}
                    >
                      {color.key === 'white' ? '白' : ''}
                    </div>
                    <Text strong>{color.label}</Text>
                    <Text code style={{ fontSize: 11 }}>{color.key}</Text>
                    <Switch
                      checked={enabled}
                      onChange={(checked) => handleColorToggle(color.key, checked)}
                      size="small"
                    />
                  </div>
                </Card>
              )
            })}
          </div>
          <Divider />
          <div>
            <Text strong>当前已启用颜色：</Text>
            <Space style={{ marginLeft: 8 }}>
              {pickingColors.map(key => {
                const color = PICKING_COLORS.find(c => c.key === key)
                if (!color) return null
                return (
                  <Tag key={key} color={color.hex} style={{ color: color.textColor, border: key === 'white' ? '1px solid #d9d9d9' : 'none' }}>
                    {color.label}
                  </Tag>
                )
              })}
            </Space>
          </div>
        </Card>

        {/* ── App 版本更新 ── */}
        <Card title="App 版本更新" style={{ marginBottom: 24 }}>
          <div style={{ marginBottom: 16 }}>
            <Text type="secondary">
              配置 PDA App 的版本更新信息，用户端在设置页面点击「检查更新」时将从 <Text code>/api/app/version</Text> 获取以下配置。
            </Text>
          </div>

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

          {/* 更新说明 */}
          <div style={{ marginBottom: 16 }}>
            <Text strong>更新说明</Text>
            <TextArea
              value={appReleaseNotes}
              onChange={(e) => setAppReleaseNotes(e.target.value)}
              placeholder="- 优化扫码性能&#10;- 修复问题&#10;- 新增功能"
              rows={3}
              style={{ marginTop: 4 }}
            />
          </div>

          {/* 操作栏 */}
          <div style={{ display: 'flex', gap: 12 }}>
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              onClick={handleSaveAppVersion}
              loading={appSaving}
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

      {/* ── 编辑弹窗 ── */}
      <Modal
        title="修改设置"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSave}
        confirmLoading={saving}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <strong>设置项：</strong>{editingKey}
          </div>
          <div>
            <strong>描述：</strong>{editingDescription}
          </div>
          <div>
            <strong>值：</strong>
            {renderValueInput()}
          </div>
        </Space>
      </Modal>
    </div>
  )
}
