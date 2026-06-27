import { useState, useEffect } from 'react'
import { Card, Table, Button, Modal, Input, Select, Space, Spin, message, Switch, Divider, Tag, Typography } from 'antd'
import { getSettingsApi, updateSettingApi } from '../api'

const { Text, Title } = Typography

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

  const loadSettings = async () => {
    setLoading(true)
    try {
      const res = await getSettingsApi()
      const data = res.data
      const list = Array.isArray(data) ? data : data.settings || []
      setSettings(list)

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
            dataSource={settings.filter(s => s.key !== 'picking_task_colors')}
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
