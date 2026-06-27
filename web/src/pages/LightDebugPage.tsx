import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Card,
  Tabs,
  Form,
  Input,
  InputNumber,
  Select,
  Button,
  Switch,
  Space,
  Tag,
  Table,
  Modal,
  Typography,
  Alert,
  message,
  Tooltip,
  Empty,
  Collapse,
} from 'antd'
import {
  BulbOutlined,
  SendOutlined,
  PoweroffOutlined,
  ExperimentOutlined,
  SearchOutlined,
  DeleteOutlined,
  PlusOutlined,
  ThunderboltOutlined,
  WarningOutlined,
  CopyOutlined,
  ClearOutlined,
  ReloadOutlined,
  SyncOutlined,
  WifiOutlined,
} from '@ant-design/icons'
import {
  getDebugShelvesApi,
  debugSingleLightApi,
  debugBatchLightApi,
  debugIndicatorApi,
  debugRackTestApi,
  debugCellListApi,
  debugTurnOffApi,
  debugTurnOffAllApi,
  getCallbackEventsApi,
  debugSensorTestApi,
} from '../api'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input

// ── 常量定义 ──────────────────────────────────────────────────────────

/** 储位灯色值映射 */
const LED_COLORS = [
  { value: 0, label: '灭灯', color: '#000', bg: '#f0f0f0' },
  { value: 1, label: '红色', color: '#fff', bg: '#f5222d' },
  { value: 2, label: '绿色', color: '#fff', bg: '#52c41a' },
  { value: 3, label: '黄色', color: '#fff', bg: '#faad14' },
  { value: 4, label: '蓝色', color: '#fff', bg: '#1890ff' },
  { value: 5, label: '洋红', color: '#fff', bg: '#eb2f96' },
  { value: 6, label: '青色', color: '#fff', bg: '#13c2c2' },
  { value: 7, label: '白色', color: '#000', bg: '#fff' },
]

/** 警示灯色值映射 */
const INDICATOR_COLORS = [
  { value: 0, label: '关闭', color: '#999' },
  { value: 1, label: '红色', color: '#f5222d' },
  { value: 2, label: '黄色', color: '#faad14' },
  { value: 3, label: '红+黄', color: '#fa8c16' },
  { value: 4, label: '绿色', color: '#52c41a' },
  { value: 5, label: '红+绿', color: '#f5222d' },
  { value: 6, label: '黄+绿', color: '#a0d911' },
  { value: 7, label: '红+黄+绿', color: '#f5222d' },
]

/** 测试模式定义 */
const TEST_MODES = [
  { value: 1, label: 'RGB 灯珠测试', desc: '逐个测试 RGB 三色灯珠（色彩循环）' },
  { value: 2, label: '灯序测试', desc: '测试灯光顺序（逐个点亮/熄灭）' },
  { value: 4, label: '警示灯测试', desc: '测试警示/指示灯' },
  { value: 8, label: '感应传感器测试', desc: '测试接近/感应传感器' },
]

/** 警示灯位置 */
const INDICATOR_POSITIONS = [
  { value: 0, label: '正面' },
  { value: 1, label: '反面' },
  { value: 2, label: '双面' },
]

// ── 颜色选择器组件 ────────────────────────────────────────────────────

function ColorSelector({
  value,
  onChange,
  colors,
  label,
}: {
  value: number
  onChange: (v: number) => void
  colors: { value: number; label: string; bg?: string; color?: string }[]
  label?: string
}) {
  return (
    <div>
      {label && <div style={{ marginBottom: 8, fontWeight: 500 }}>{label}</div>}
      <Space wrap>
        {colors.map((c) => (
          <Tooltip key={c.value} title={`${c.label} (${c.value})`}>
            <div
              onClick={() => onChange(c.value)}
              style={{
                width: 36,
                height: 36,
                borderRadius: 6,
                backgroundColor: c.bg || c.color || '#ccc',
                border: value === c.value ? '3px solid #1890ff' : '2px solid #d9d9d9',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 10,
                color: c.color || '#000',
                fontWeight: value === c.value ? 'bold' : 'normal',
                transition: 'all 0.2s',
                boxShadow: value === c.value ? '0 0 8px rgba(24,144,255,0.4)' : 'none',
              }}
            >
              {c.value === 0 ? 'OFF' : ''}
            </div>
          </Tooltip>
        ))}
      </Space>
    </div>
  )
}

// ── JSON 响应查看器 ────────────────────────────────────────────────────

function ResponseViewer({ data, title }: { data: any; title?: string }) {
  if (!data) return null
  return (
    <Card
      size="small"
      title={title || '响应结果'}
      extra={
        <Button
          size="small"
          icon={<CopyOutlined />}
          onClick={() => {
            navigator.clipboard.writeText(JSON.stringify(data, null, 2))
            message.success('已复制到剪贴板')
          }}
        >
          复制
        </Button>
      }
      style={{ marginTop: 16, background: '#fafafa' }}
    >
      <pre
        style={{
          margin: 0,
          padding: 12,
          background: '#1e1e1e',
          color: '#d4d4d4',
          borderRadius: 4,
          fontSize: 12,
          lineHeight: 1.6,
          maxHeight: 400,
          overflow: 'auto',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all',
        }}
      >
        {JSON.stringify(data, null, 2)}
      </pre>
    </Card>
  )
}

// ── 页面主组件 ────────────────────────────────────────────────────────

export function LightDebugPage() {
  const [shelves, setShelves] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [responseData, setResponseData] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('single')

  // ── 单灯调试表单 ──
  const [singleForm] = Form.useForm()

  // ── 批量调试 ──
  const [batchCells, setBatchCells] = useState([
    { cell_id: '', led_color: 1, blink: false },
  ])
  const [batchVoiceText, setBatchVoiceText] = useState('')
  const [batchTurnOnTime, setBatchTurnOnTime] = useState(0)

  // ── 警示灯调试 ──
  const [indicatorForm] = Form.useForm()

  // ── 料架测试 ──
  const [testForm] = Form.useForm()
  const [testModeBitmask, setTestModeBitmask] = useState(15)

  // ── 储位查询 ──
  const [queryForm] = Form.useForm()
  const [queryResult, setQueryResult] = useState<any>(null)
  const [querying, setQuerying] = useState(false)

  // ── 快捷操作 ──
  const [quickShelf, setQuickShelf] = useState<string>('')
  const [quickCellId, setQuickCellId] = useState('')
  const [quickColorCell, setQuickColorCell] = useState('')
  const [turnOffAllLoading, setTurnOffAllLoading] = useState(false)

  // ── 回调测试 ──
  // WebSocket 实时监控
  const [wsConnected, setWsConnected] = useState(false)
  const [wsMessages, setWsMessages] = useState<any[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  // 回调事件日志
  const [callbackEvents, setCallbackEvents] = useState<any[]>([])
  const [eventsLoading, setEventsLoading] = useState(false)
  const [eventsFilterShelf, setEventsFilterShelf] = useState<number | undefined>(undefined)
  // 传感器测试
  const [sensorTestShelf, setSensorTestShelf] = useState('')
  const [sensorTestSending, setSensorTestSending] = useState(false)

  // 加载料架列表
  const loadShelves = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getDebugShelvesApi()
      setShelves(res.data || [])
    } catch (err: any) {
      // 404 或网络错误时保持空列表
      setShelves([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadShelves()
  }, [loadShelves])

  // 通用: 执行调试操作
  const executeDebug = async (apiFunc: () => Promise<any>) => {
    setSending(true)
    setError(null)
    setResponseData(null)
    try {
      const res = await apiFunc()
      setResponseData(res.data)
      message.success('指令已发送')
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || '请求失败'
      setError(errMsg)
      message.error(errMsg)
    } finally {
      setSending(false)
    }
  }

  // ── 单灯调试提交 ──
  const handleSingleSubmit = async () => {
    const values = await singleForm.validateFields()
    executeDebug(() => debugSingleLightApi(values))
  }

  // ── 批量调试提交 ──
  const handleBatchSubmit = async () => {
    const validCells = batchCells.filter((c) => c.cell_id.trim())
    if (validCells.length === 0) {
      message.warning('请至少添加一个有效的储位号')
      return
    }
    executeDebug(() =>
      debugBatchLightApi({
        cells: validCells.map((c) => ({
          cell_id: c.cell_id,
          led_color: c.led_color,
          blink: c.blink,
        })),
        turn_on_time: batchTurnOnTime,
        voice_text: batchVoiceText,
      })
    )
  }

  // ── 警示灯调试提交 ──
  const handleIndicatorSubmit = async () => {
    const values = await indicatorForm.validateFields()
    executeDebug(() => debugIndicatorApi(values))
  }

  // ── 料架测试提交 ──
  const handleTestSubmit = async () => {
    const values = await testForm.validateFields()
    executeDebug(() =>
      debugRackTestApi({
        rack_id: values.rack_id,
        test_mode: testModeBitmask,
        interval: values.interval || 1000,
      })
    )
  }

  // ── 储位查询 ──
  const handleQuerySubmit = async () => {
    const values = await queryForm.validateFields()
    setQuerying(true)
    setQueryResult(null)
    try {
      const res = await debugCellListApi(values)
      setQueryResult(res.data)
    } catch (err: any) {
      message.error(err.response?.data?.detail || err.message || '查询失败')
    } finally {
      setQuerying(false)
    }
  }

  // ── 单灯灭灯 ──
  const handleTurnOff = () => {
    if (!quickCellId.trim()) {
      message.warning('请输入储位号')
      return
    }
    executeDebug(() => debugTurnOffApi({ cell_id: quickCellId }))
  }

  // ── WebSocket 连接管理 ──
  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setWsConnected(true)
      // 发送心跳
      ws.send('ping')
    }

    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data)
        setWsMessages((prev) => [parsed, ...prev].slice(0, 200))
      } catch {
        // ping/pong 等非 JSON 消息忽略
      }
    }

    ws.onclose = () => {
      setWsConnected(false)
      wsRef.current = null
    }

    ws.onerror = () => {
      setWsConnected(false)
    }
  }, [])

  const disconnectWs = useCallback(() => {
    wsRef.current?.close()
    wsRef.current = null
    setWsConnected(false)
  }, [])

  // 清理
  useEffect(() => {
    return () => {
      wsRef.current?.close()
    }
  }, [])

  // ── 加载回调事件日志 ──
  const loadCallbackEvents = useCallback(async () => {
    setEventsLoading(true)
    try {
      const res = await getCallbackEventsApi({
        limit: 50,
        shelf_id: eventsFilterShelf,
      })
      setCallbackEvents(res.data || [])
    } catch (err: any) {
      // 静默处理
    } finally {
      setEventsLoading(false)
    }
  }, [eventsFilterShelf])

  useEffect(() => {
    loadCallbackEvents()
  }, [loadCallbackEvents])

  // ── 传感器测试触发 ──
  const handleSensorTest = async () => {
    if (!sensorTestShelf) {
      message.warning('请选择料架')
      return
    }
    setSensorTestSending(true)
    setResponseData(null)
    setError(null)
    try {
      const res = await debugSensorTestApi({
        rack_id: sensorTestShelf,
        interval: 2000,
      })
      setResponseData(res.data)
      message.success('传感器测试指令已发送，请观察料架指示灯和下方回调日志')
      // 延迟 3 秒后自动刷新回调日志
      setTimeout(() => loadCallbackEvents(), 3000)
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || '请求失败'
      setError(errMsg)
      message.error(errMsg)
    } finally {
      setSensorTestSending(false)
    }
  }

  // ── 全部灭灯 ──
  const handleTurnOffAll = () => {
    if (!quickShelf) {
      message.warning('请选择料架')
      return
    }
    Modal.confirm({
      title: '确认操作',
      content: `即将关闭料架 "${quickShelf}" 下所有储位的灯，确认继续？`,
      okText: '确认',
      cancelText: '取消',
      onOk: async () => {
        setTurnOffAllLoading(true)
        try {
          const res = await debugTurnOffAllApi({ rack_id: quickShelf })
          setResponseData(res.data)
          message.success(`灭灯完成: ${res.data?.data?.turned_off || 0} 个储位`)
        } catch (err: any) {
          message.error(err.response?.data?.detail || err.message || '操作失败')
        } finally {
          setTurnOffAllLoading(false)
        }
      },
    })
  }

  // 解析查询结果中的储位列表
  const getCellItems = () => {
    if (!queryResult?.data?.response) return []
    const raw = queryResult.data.response
    // 兼容不同响应格式
    return raw.data || raw.resultData?.items || raw.resultData || []
  }

  const cellColumns = [
    {
      title: '储位号',
      dataIndex: 'cellId',
      key: 'cellId',
      render: (v: string) => <Text code>{v}</Text>,
    },
    {
      title: '灯色',
      dataIndex: 'ledColor',
      key: 'ledColor',
      render: (v: number) => {
        const c = LED_COLORS.find((x) => x.value === v)
        return c ? (
          <Tag color={c.bg} style={{ color: c.color }}>
            {c.label}
          </Tag>
        ) : (
          <Tag>{v}</Tag>
        )
      },
    },
    {
      title: '闪烁',
      dataIndex: 'blink',
      key: 'blink',
      render: (v: number) => (v ? <Tag color="blue">是</Tag> : <Tag>否</Tag>),
    },
    {
      title: '状态',
      dataIndex: 'used',
      key: 'used',
      render: (v: number) =>
        v ? <Tag color="green">有物料</Tag> : <Tag>空闲</Tag>,
    },
    {
      title: '电量 (V)',
      dataIndex: 'electricitys',
      key: 'electricitys',
      render: (v: string) => {
        if (!v) return '-'
        const vol = parseFloat(v)
        const color = vol < 2.5 ? '#f5222d' : vol < 2.8 ? '#faad14' : '#52c41a'
        return <span style={{ color, fontWeight: 600 }}>{v}</span>
      },
    },
    {
      title: '蓝牙 ID',
      dataIndex: 'bluetooth_id',
      key: 'bluetooth_id',
      render: (v: string) => v || '-',
    },
  ]

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <div>
          <Title level={4} style={{ margin: 0 }}>
            <BulbOutlined /> 灯控调试
          </Title>
          <Text type="secondary">
            用于硬件工程师调试智能料架控灯 API，所有操作直接透传硬件接口
          </Text>
        </div>
        <Space>
          <Tag icon={<BulbOutlined />} color={shelves.length > 0 ? 'success' : 'error'}>
            {shelves.length > 0 ? `已连接 (${shelves.length} 个料架)` : '未检测到料架'}
          </Tag>
          <Button icon={<ReloadOutlined />} onClick={loadShelves} loading={loading}>
            刷新
          </Button>
        </Space>
      </div>

      {error && (
        <Alert
          message="操作失败"
          description={error}
          type="error"
          showIcon
          closable
          style={{ marginBottom: 16 }}
          onClose={() => setError(null)}
        />
      )}

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'single',
            label: (
              <span>
                <BulbOutlined /> 单灯调试
              </span>
            ),
            children: (
              <Card>
                <Form
                  form={singleForm}
                  layout="vertical"
                  initialValues={{ led_color: 1, blink: false, turn_on_time: 0 }}
                  onFinish={handleSingleSubmit}
                >
                  <Form.Item
                    name="cell_id"
                    label="储位号"
                    rules={[{ required: true, message: '请输入储位号' }]}
                    extra="格式如 A0010001（料架号+4位序号）"
                  >
                    <Input placeholder="例如: A0010001" style={{ width: 300 }} />
                  </Form.Item>

                  <Form.Item name="led_color" label="灯色">
                    <ColorSelector
                      value={singleForm.getFieldValue('led_color')}
                      onChange={(v) => singleForm.setFieldsValue({ led_color: v })}
                      colors={LED_COLORS}
                    />
                  </Form.Item>

                  <Space style={{ marginBottom: 24 }}>
                    <Form.Item name="blink" label="闪烁" valuePropName="checked" noStyle>
                      <Switch />
                    </Form.Item>
                    <Form.Item
                      name="turn_on_time"
                      label="亮灯时间（秒）"
                      tooltip="0 表示常亮，大于 0 表示指定秒数后自动灭灯"
                      noStyle
                    >
                      <InputNumber min={0} max={3600} style={{ width: 160 }} />
                    </Form.Item>
                  </Space>

                  <div>
                    <Button
                      type="primary"
                      htmlType="submit"
                      icon={<SendOutlined />}
                      loading={sending}
                    >
                      发送指令
                    </Button>
                  </div>
                </Form>
              </Card>
            ),
          },
          {
            key: 'batch',
            label: (
              <span>
                <ExperimentOutlined /> 批量调试
              </span>
            ),
            children: (
              <Card>
                <Paragraph type="secondary">
                  批量控制多个储位灯，支持语音播报（可选）
                </Paragraph>

                <Space style={{ marginBottom: 16 }}>
                  <InputNumber
                    addonBefore="亮灯时间（秒）"
                    min={0}
                    max={3600}
                    value={batchTurnOnTime}
                    onChange={(v) => setBatchTurnOnTime(v || 0)}
                    style={{ width: 200 }}
                  />
                  <Input
                    placeholder="语音播报文本（可选）"
                    style={{ width: 300 }}
                    value={batchVoiceText}
                    onChange={(e) => setBatchVoiceText(e.target.value)}
                  />
                </Space>

                <div style={{ marginBottom: 16 }}>
                  <Text strong>储位列表：</Text>
                  <Button
                    type="dashed"
                    size="small"
                    icon={<PlusOutlined />}
                    style={{ marginLeft: 8 }}
                    onClick={() =>
                      setBatchCells([
                        ...batchCells,
                        { cell_id: '', led_color: 1, blink: false },
                      ])
                    }
                  >
                    添加
                  </Button>
                </div>

                {batchCells.map((cell, idx) => (
                  <Card
                    key={idx}
                    size="small"
                    style={{ marginBottom: 8, background: '#fafafa' }}
                    extra={
                      batchCells.length > 1 && (
                        <Button
                          type="text"
                          danger
                          icon={<DeleteOutlined />}
                          onClick={() => {
                            const next = batchCells.filter((_, i) => i !== idx)
                            setBatchCells(next)
                          }}
                        />
                      )
                    }
                  >
                    <Space align="start" wrap>
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          储位号
                        </Text>
                        <Input
                          placeholder="A0010001"
                          value={cell.cell_id}
                          onChange={(e) => {
                            const next = [...batchCells]
                            next[idx] = { ...next[idx], cell_id: e.target.value }
                            setBatchCells(next)
                          }}
                          style={{ width: 140 }}
                        />
                      </div>
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          灯色
                        </Text>
                        <Select
                          value={cell.led_color}
                          onChange={(v) => {
                            const next = [...batchCells]
                            next[idx] = { ...next[idx], led_color: v }
                            setBatchCells(next)
                          }}
                          style={{ width: 100 }}
                          options={LED_COLORS.map((c) => ({
                            value: c.value,
                            label: c.label,
                          }))}
                        />
                      </div>
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          闪烁
                        </Text>
                        <div style={{ paddingTop: 4 }}>
                          <Switch
                            checked={cell.blink}
                            onChange={(v) => {
                              const next = [...batchCells]
                              next[idx] = { ...next[idx], blink: v }
                              setBatchCells(next)
                            }}
                          />
                        </div>
                      </div>
                    </Space>
                  </Card>
                ))}

                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  loading={sending}
                  onClick={handleBatchSubmit}
                  style={{ marginTop: 8 }}
                >
                  批量发送
                </Button>
              </Card>
            ),
          },
          {
            key: 'indicator',
            label: (
              <span>
                <WarningOutlined /> 警示灯调试
              </span>
            ),
            children: (
              <Card>
                <Form
                  form={indicatorForm}
                  layout="vertical"
                  initialValues={{ indicator_id: 0, indicator_status: 1, blink: false }}
                  onFinish={handleIndicatorSubmit}
                >
                  <Form.Item
                    name="rack_id"
                    label="料架号"
                    rules={[{ required: true, message: '请选择料架' }]}
                  >
                    <Select
                      showSearch
                      placeholder="选择料架"
                      style={{ width: 300 }}
                      options={shelves.map((s) => ({
                        value: s.code,
                        label: `${s.code} - ${s.name || ''}`,
                      }))}
                      filterOption={(input, option) =>
                        (option?.label as string)
                          ?.toLowerCase()
                          .includes(input.toLowerCase())
                      }
                    />
                  </Form.Item>

                  <Form.Item name="indicator_id" label="警示灯位置">
                    <Select
                      style={{ width: 200 }}
                      options={INDICATOR_POSITIONS}
                    />
                  </Form.Item>

                  <Form.Item name="indicator_status" label="灯色">
                    <ColorSelector
                      value={indicatorForm.getFieldValue('indicator_status')}
                      onChange={(v) =>
                        indicatorForm.setFieldsValue({ indicator_status: v })
                      }
                      colors={INDICATOR_COLORS}
                      label=""
                    />
                  </Form.Item>

                  <Form.Item name="blink" label="闪烁" valuePropName="checked">
                    <Switch />
                  </Form.Item>

                  <Button
                    type="primary"
                    htmlType="submit"
                    icon={<SendOutlined />}
                    loading={sending}
                  >
                    发送指令
                  </Button>
                </Form>
              </Card>
            ),
          },
          {
            key: 'test',
            label: (
              <span>
                <ThunderboltOutlined /> 料架测试
              </span>
            ),
            children: (
              <Card>
                <Paragraph type="secondary">
                  选择测试模式（可多选组合），向料架发送硬件测试指令
                </Paragraph>

                <Form
                  form={testForm}
                  layout="vertical"
                  initialValues={{ interval: 1000 }}
                  onFinish={handleTestSubmit}
                >
                  <Form.Item
                    name="rack_id"
                    label="料架号 / 储位号"
                    rules={[{ required: true, message: '请输入料架号或储位号' }]}
                  >
                    <Select
                      showSearch
                      placeholder="选择料架或直接输入储位号"
                      style={{ width: 300 }}
                      options={shelves.map((s) => ({
                        value: s.code,
                        label: `${s.code} - ${s.name || ''}`,
                      }))}
                      filterOption={(input, option) =>
                        (option?.label as string)
                          ?.toLowerCase()
                          .includes(input.toLowerCase())
                      }
                    />
                  </Form.Item>

                  <div style={{ marginBottom: 24 }}>
                    <Text strong style={{ display: 'block', marginBottom: 8 }}>
                      测试模式（可多选）
                    </Text>
                    <Space wrap>
                      {TEST_MODES.map((m) => (
                        <Tag
                          key={m.value}
                          color={testModeBitmask & m.value ? 'blue' : 'default'}
                          style={{
                            cursor: 'pointer',
                            padding: '4px 12px',
                            fontSize: 14,
                          }}
                          onClick={() => {
                            setTestModeBitmask(
                              testModeBitmask & m.value
                                ? testModeBitmask & ~m.value
                                : testModeBitmask | m.value
                            )
                          }}
                        >
                          {m.label}
                        </Tag>
                      ))}
                    </Space>
                    <div style={{ marginTop: 8 }}>
                      <Tag color="purple">当前模式值: {testModeBitmask}</Tag>
                      <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
                        {testModeBitmask === 0
                          ? '取消测试'
                          : TEST_MODES.filter((m) => testModeBitmask & m.value)
                              .map((m) => m.label)
                              .join(' + ') || '未选择'}
                      </Text>
                    </div>
                  </div>

                  <Form.Item
                    name="interval"
                    label="变化间隔（毫秒）"
                    tooltip="测试时灯色/灯序变化的间隔时间"
                  >
                    <InputNumber min={100} max={10000} step={100} style={{ width: 200 }} />
                  </Form.Item>

                  <Button
                    type="primary"
                    htmlType="submit"
                    icon={<SendOutlined />}
                    loading={sending}
                  >
                    开始测试
                  </Button>
                </Form>
              </Card>
            ),
          },
          {
            key: 'query',
            label: (
              <span>
                <SearchOutlined /> 储位查询
              </span>
            ),
            children: (
              <Card>
                <Form
                  form={queryForm}
                  layout="inline"
                  initialValues={{ page_index: 1, page_size: 200 }}
                  onFinish={handleQuerySubmit}
                  style={{ marginBottom: 16 }}
                >
                  <Form.Item name="rack_id" label="料架号">
                    <Select
                      showSearch
                      placeholder="全部料架"
                      allowClear
                      style={{ width: 200 }}
                      options={shelves.map((s) => ({
                        value: s.code,
                        label: `${s.code} - ${s.name || ''}`,
                      }))}
                      filterOption={(input, option) =>
                        (option?.label as string)
                          ?.toLowerCase()
                          .includes(input.toLowerCase())
                      }
                    />
                  </Form.Item>

                  <Form.Item name="filter" label="储位筛选">
                    <Input placeholder="部分储位号" style={{ width: 160 }} />
                  </Form.Item>

                  <Form.Item name="page_size" label="每页数量">
                    <InputNumber min={10} max={500} style={{ width: 120 }} />
                  </Form.Item>

                  <Form.Item>
                    <Button
                      type="primary"
                      htmlType="submit"
                      icon={<SearchOutlined />}
                      loading={querying}
                    >
                      查询
                    </Button>
                  </Form.Item>
                </Form>

                {queryResult && (
                  <>
                    <Alert
                      type="info"
                      showIcon
                      message={
                        <span>
                          查询完成 | 共 {getCellItems().length} 个储位
                        </span>
                      }
                      style={{ marginBottom: 12 }}
                    />

                    <Table
                      dataSource={getCellItems()}
                      columns={cellColumns}
                      rowKey={(r: any) => r.cellId || r.cell_id || Math.random()}
                      size="small"
                      pagination={{ pageSize: 20, showSizeChanger: true }}
                      scroll={{ x: 800 }}
                    />

                    <Collapse
                      ghost
                      items={[
                        {
                          key: 'raw',
                          label: '查看原始响应',
                          children: (
                            <pre
                              style={{
                                background: '#1e1e1e',
                                color: '#d4d4d4',
                                padding: 12,
                                borderRadius: 4,
                                fontSize: 12,
                                maxHeight: 300,
                                overflow: 'auto',
                              }}
                            >
                              {JSON.stringify(queryResult, null, 2)}
                            </pre>
                          ),
                        },
                      ]}
                    />
                  </>
                )}

                {!queryResult && (
                  <Empty description="点击「查询」按钮获取料架储位状态" />
                )}
              </Card>
            ),
          },
          {
            key: 'quick',
            label: (
              <span>
                <PoweroffOutlined /> 快捷操作
              </span>
            ),
            children: (
              <Card>
                <Space direction="vertical" size="large" style={{ width: '100%' }}>
                  {/* 单个灭灯 */}
                  <Card size="small" title="单灯灭灯" type="inner">
                    <Space>
                      <Input
                        placeholder="储位号 (如 A0010001)"
                        value={quickCellId}
                        onChange={(e) => setQuickCellId(e.target.value)}
                        style={{ width: 280 }}
                      />
                      <Button
                        icon={<PoweroffOutlined />}
                        onClick={handleTurnOff}
                        loading={sending}
                      >
                        关闭
                      </Button>
                    </Space>
                  </Card>

                  {/* 全部灭灯 */}
                  <Card size="small" title="整架灭灯" type="inner">
                    <Space>
                      <Select
                        showSearch
                        placeholder="选择料架"
                        value={quickShelf || undefined}
                        onChange={setQuickShelf}
                        style={{ width: 280 }}
                        options={shelves.map((s) => ({
                          value: s.code,
                          label: `${s.code} - ${s.name || ''}`,
                        }))}
                        filterOption={(input, option) =>
                          (option?.label as string)
                            ?.toLowerCase()
                            .includes(input.toLowerCase())
                        }
                      />
                      <Button
                        danger
                        icon={<ClearOutlined />}
                        onClick={handleTurnOffAll}
                        loading={turnOffAllLoading}
                      >
                        关闭全部
                      </Button>
                    </Space>
                    <Paragraph
                      type="secondary"
                      style={{ margin: '8px 0 0', fontSize: 12 }}
                    >
                      关闭所选料架下所有储位的灯。系统会先查询储位列表，再逐个发送灭灯指令。
                    </Paragraph>
                  </Card>

                  {/* 快速颜色测试 */}
                  <Card size="small" title="快速颜色测试" type="inner">
                    <Paragraph type="secondary">
                      选择一个颜色，快速点亮指定储位进行目视确认
                    </Paragraph>
                    <Space align="start">
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          储位号
                        </Text>
                        <Input
                          placeholder="A0010001"
                          style={{ width: 160, display: 'block' }}
                          value={quickColorCell}
                          onChange={(e) => setQuickColorCell(e.target.value)}
                        />
                      </div>
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          选择颜色
                        </Text>
                        <div style={{ paddingTop: 4 }}>
                          {LED_COLORS.filter((c) => c.value > 0).map((c) => (
                            <Tooltip key={c.value} title={c.label}>
                              <Button
                                size="small"
                                style={{
                                  backgroundColor: c.bg,
                                  borderColor: c.bg,
                                  color: c.color,
                                  width: 32,
                                  height: 32,
                                  marginRight: 4,
                                }}
                                onClick={async () => {
                                  if (!quickColorCell.trim()) {
                                    message.warning('请输入储位号')
                                    return
                                  }
                                  try {
                                    await debugSingleLightApi({
                                      cell_id: quickColorCell.trim(),
                                      led_color: c.value,
                                    })
                                    message.success(
                                      `已发送 ${c.label} (${c.value}) 到 ${quickColorCell.trim()}`
                                    )
                                  } catch (err: any) {
                                    message.error(
                                      err.response?.data?.detail || '发送失败'
                                    )
                                  }
                                }}
                              >
                                {c.value}
                              </Button>
                            </Tooltip>
                          ))}
                        </div>
                      </div>
                    </Space>
                  </Card>
                </Space>
              </Card>
            ),
          },
          {
            key: 'callback',
            label: (
              <span>
                <SyncOutlined /> 回调测试
              </span>
            ),
            children: (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                {/* ── 说明 ── */}
                <Alert
                  type="info"
                  showIcon
                  message="回调测试说明"
                  description={
                    <span>
                      回调是由智能料架硬件主动触发的储位变化通知（放入/取出物料时发送）。
                      本页面提供以下工具帮助验证回调链路是否正常：
                      <ol style={{ margin: '4px 0 0', paddingLeft: 20 }}>
                        <li><b>传感器测试</b> — 让硬件执行传感器自检，触发回调</li>
                        <li><b>实时监控</b> — WebSocket 实时接收系统广播的回调事件</li>
                        <li><b>回调日志</b> — 查看数据库记录的历史回调事件</li>
                      </ol>
                    </span>
                  }
                />

                {/* ── 第一步：传感器测试（触发回调） ── */}
                <Card
                  size="small"
                  title={
                    <Space>
                      <ThunderboltOutlined />
                      <span>第一步：触发回调 — 传感器测试</span>
                    </Space>
                  }
                >
                  <Paragraph type="secondary">
                    选择料架后点击「传感器测试」，硬件将执行感应传感器自检。
                    自检过程中储位传感器状态变化会触发回调发送到系统。
                    你也可以直接在物理料架上放入/取出物料来触发回调。
                  </Paragraph>
                  <Space>
                    <Select
                      showSearch
                      placeholder="选择料架"
                      value={sensorTestShelf || undefined}
                      onChange={setSensorTestShelf}
                      style={{ width: 280 }}
                      options={shelves.map((s) => ({
                        value: s.code,
                        label: `${s.code} - ${s.name || ''}`,
                      }))}
                      filterOption={(input, option) =>
                        (option?.label as string)
                          ?.toLowerCase()
                          .includes(input.toLowerCase())
                      }
                    />
                    <Button
                      type="primary"
                      icon={<ExperimentOutlined />}
                      loading={sensorTestSending}
                      onClick={handleSensorTest}
                    >
                      传感器测试 (mode=8)
                    </Button>
                    <Button
                      icon={<ReloadOutlined />}
                      onClick={loadCallbackEvents}
                    >
                      刷新日志
                    </Button>
                  </Space>
                </Card>

                {/* ── 第二步：WebSocket 实时监控 ── */}
                <Card
                  size="small"
                  title={
                    <Space>
                      <WifiOutlined />
                      <span>第二步：实时监控（WebSocket）</span>
                      <Tag
                        color={wsConnected ? 'success' : 'error'}
                        style={{ marginLeft: 8 }}
                      >
                        {wsConnected ? '已连接' : '未连接'}
                      </Tag>
                    </Space>
                  }
                  extra={
                    <Space>
                      {wsConnected ? (
                        <Button size="small" danger onClick={disconnectWs}>
                          断开
                        </Button>
                      ) : (
                        <Button size="small" type="primary" onClick={connectWs}>
                          连接
                        </Button>
                      )}
                      {wsMessages.length > 0 && (
                        <Button
                          size="small"
                          icon={<DeleteOutlined />}
                          onClick={() => setWsMessages([])}
                        >
                          清空
                        </Button>
                      )}
                    </Space>
                  }
                >
                  {wsMessages.length === 0 ? (
                    <Empty
                      description={
                        wsConnected
                          ? '等待接收回调事件… 请执行传感器测试或在料架上操作'
                          : '点击「连接」开始实时监控'
                      }
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                    />
                  ) : (
                    <div
                      style={{
                        maxHeight: 260,
                        overflow: 'auto',
                        background: '#1e1e1e',
                        borderRadius: 4,
                        padding: 8,
                      }}
                    >
                      {wsMessages.map((msg, idx) => (
                        <div
                          key={idx}
                          style={{
                            marginBottom: 4,
                            padding: '4px 8px',
                            borderRadius: 4,
                            background:
                              msg.type === 'reel_bound'
                                ? '#1a3a1a'
                                : msg.type === 'cell_changed'
                                  ? msg.data?.status === 1
                                    ? '#1a2a3a'
                                    : '#3a2a1a'
                                  : '#2a2a2a',
                            color: '#d4d4d4',
                            fontSize: 12,
                            fontFamily: 'monospace',
                          }}
                        >
                          <Tag
                            color={
                              msg.type === 'reel_bound'
                                ? 'green'
                                : msg.type === 'cell_changed'
                                  ? 'blue'
                                  : 'default'
                            }
                            style={{ fontSize: 10, marginRight: 4 }}
                          >
                            {msg.type}
                          </Tag>
                          <span>{JSON.stringify(msg.data)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>

                {/* ── 第三步：回调事件日志 ── */}
                <Card
                  size="small"
                  title={
                    <Space>
                      <SyncOutlined />
                      <span>第三步：回调事件日志</span>
                      <Tag>{callbackEvents.length} 条</Tag>
                    </Space>
                  }
                  extra={
                    <Space>
                      <Select
                        allowClear
                        placeholder="按料架筛选"
                        style={{ width: 160 }}
                        value={eventsFilterShelf}
                        onChange={(v) => setEventsFilterShelf(v)}
                        options={shelves.map((s) => ({
                          value: s.id,
                          label: s.code,
                        }))}
                      />
                      <Button
                        size="small"
                        icon={<ReloadOutlined />}
                        onClick={loadCallbackEvents}
                        loading={eventsLoading}
                      >
                        刷新
                      </Button>
                    </Space>
                  }
                >
                  <Table
                    dataSource={callbackEvents}
                    columns={[
                      {
                        title: '时间',
                        dataIndex: 'created_at',
                        key: 'created_at',
                        width: 180,
                        render: (v: string) => {
                          if (!v) return '-'
                          const d = new Date(v)
                          return d.toLocaleString('zh-CN', {
                            hour12: false,
                          })
                        },
                      },
                      {
                        title: '事件类型',
                        dataIndex: 'event_type',
                        key: 'event_type',
                        width: 100,
                        render: (v: string) => {
                          const colorMap: Record<string, string> = {
                            occupied: 'green',
                            released: 'orange',
                            error: 'red',
                          }
                          return <Tag color={colorMap[v] || 'default'}>{v}</Tag>
                        },
                      },
                      {
                        title: '来源',
                        dataIndex: 'source',
                        key: 'source',
                        width: 80,
                      },
                      {
                        title: '储位号 (cell_id)',
                        dataIndex: 'cell_id',
                        key: 'cell_id',
                        width: 130,
                        render: (v: string) => (v ? <Text code>{v}</Text> : '-'),
                      },
                      {
                        title: '料架/储位',
                        key: 'slot_info',
                        width: 160,
                        render: (_: any, record: any) => {
                          const info = record.slot_info
                          if (!info) return '-'
                          return (
                            <Text type="secondary">
                              {info.shelf_code || '-'}/{info.cell_id || '-'}
                            </Text>
                          )
                        },
                      },
                      {
                        title: '关联料盘',
                        dataIndex: 'reel_id',
                        key: 'reel_id',
                        width: 90,
                        render: (v: number | null) =>
                          v ? <Tag color="blue">#{v}</Tag> : '-',
                      },
                      {
                        title: '原始数据',
                        dataIndex: 'raw_data',
                        key: 'raw_data',
                        ellipsis: true,
                        render: (v: string) =>
                          v ? (
                            <Tooltip title={v}>
                              <Text code style={{ fontSize: 11 }}>
                                {v.length > 60 ? v.slice(0, 60) + '…' : v}
                              </Text>
                            </Tooltip>
                          ) : (
                            '-'
                          ),
                      },
                    ]}
                    rowKey="id"
                    size="small"
                    pagination={{ pageSize: 10, showSizeChanger: false }}
                    scroll={{ x: 900 }}
                    locale={{ emptyText: '暂无回调事件，请执行传感器测试或在料架上操作' }}
                  />
                </Card>
              </Space>
            ),
          },
        ]}
      />

      {/* 全局响应区 */}
      {responseData && (
        <div style={{ marginTop: 16 }}>
          <ResponseViewer data={responseData} title="API 响应" />
        </div>
      )}
    </div>
  )
}
