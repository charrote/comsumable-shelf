import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Card, Descriptions, Tag, Button, Space, Input, InputNumber, message,
  Switch, Divider, Row, Col, Badge, Table, Modal, Tabs, Tooltip,
  Select, Typography, Alert, Popconfirm, Collapse, Spin, Radio,
} from 'antd'
import {
  PoweroffOutlined, ReloadOutlined, SettingOutlined, ExperimentOutlined,
  BugOutlined, ClearOutlined, CheckCircleOutlined, CloseCircleOutlined,
  BulbOutlined, ThunderboltOutlined, DeleteOutlined, ApiOutlined,
} from '@ant-design/icons'
import {
  getHardwareDebugStatusApi, hardwareDebugConnectApi, hardwareDebugDisconnectApi,
  getMainboardInfoApi, getMainboardConfigApi, getMainboardRelaysApi,
  setMainboardRelayApi, hardwareDebugPingApi,
  calibrateMainboardApi, resetMainboardApi, saveMainboardConfigApi,
  debugReadRegistersApi, debugWriteRegisterApi,
  getDebugBoardsApi, getDebugBoardInfoApi, getDebugBoardSlotsApi,
  getDebugBoardAdValuesApi, getDebugBoardCalibrationApi,
  debugControlLedApi, debugControlAllLedsApi, debugLedTestApi,
  debugCalibrateBoardApi, debugResetBoardApi, debugSetJudgmentApi,
  getHardwareDebugLogsApi, clearHardwareDebugLogsApi,
} from '../api'

const { Text } = Typography

// ── Types ──

interface DebugStatus {
  connected: boolean
  ip: string
  port: number
  station: number
  last_connect_attempt: number
  connect_error: string | null
  a_boards: number
  b_boards: number
  slots_per_board: number
}

interface DeviceInfo {
  device_mode: number
  station_addr: number
  hw_sw_version: number
  model_name: string
  uptime_seconds: number
  total_communications: number
  error_count: number
  voltage: number
  is_tcp: boolean
  config_mode: boolean
  eth_enabled: boolean
  wifi_enabled: boolean
  com1_enabled: boolean
  com2_enabled: boolean
  has_error: boolean
  is_busy: boolean
}

interface Board {
  station: number
  side: string
  board_addr: number
  tcp_station: number
  label: string
}

interface LogEntry {
  timestamp: number
  level: string
  source: string
  message: string
  data?: any
}

// ── Constants ──

const LOG_LEVEL_COLORS: Record<string, string> = {
  info: 'blue',
  warn: 'orange',
  error: 'red',
  debug: 'gray',
}

const SLOT_COLORS: Record<string, string> = {
  empty: '#f0f0f0',
  occupied: '#52c41a',
  error: '#ff4d4f',
  testing_green: '#389e0d',
  testing_red: '#cf1322',
  testing_blue: '#096dd9',
}

const LED_COLORS = ['off', 'green', 'red', 'blue']

// ── Component ──

export function HardwareDebugPage() {
  // Connection state
  const [status, setStatus] = useState<DebugStatus>({
    connected: false, ip: '', port: 502, station: 200,
    last_connect_attempt: 0, connect_error: null,
    a_boards: 0, b_boards: 0, slots_per_board: 20,
  })
  const [ip, setIp] = useState('192.168.1.100')
  const [port, setPort] = useState(502)
  const [connecting, setConnecting] = useState(false)
  const [pingRtt, setPingRtt] = useState<number | null>(null)

  // Device info
  const [deviceInfo, setDeviceInfo] = useState<DeviceInfo | null>(null)
  const [deviceInfoLoading, setDeviceInfoLoading] = useState(false)

  // Relays
  const [relays, setRelays] = useState<Record<string, boolean>>({})
  const [relayLoading, setRelayLoading] = useState(false)

  // Boards
  const [boards, setBoards] = useState<Board[]>([])
  const [boardsLoading, setBoardsLoading] = useState(false)
  const [selectedBoard, setSelectedBoard] = useState<number | null>(null)
  const [boardInfo, setBoardInfo] = useState<any>(null)
  const [boardSlots, setBoardSlots] = useState<Record<string, boolean>>({})
  const [boardAdValues, setBoardAdValues] = useState<Record<string, number>>({})
  const [boardCalibration, setBoardCalibration] = useState<any>(null)
  const [boardDataLoading, setBoardDataLoading] = useState(false)
  const [selectedSlot, setSelectedSlot] = useState<number | null>(null)
  const [boardTab, setBoardTab] = useState('A')
  const [judgmentValue, setJudgmentValue] = useState<number>(50)
  const [testRunning, setTestRunning] = useState<number | null>(null)

  // Logs
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [logLevelFilter, setLogLevelFilter] = useState<string | null>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const logContainerRef = useRef<HTMLDivElement>(null)
  const pollTimerRef = useRef<any>(null)
  const lastLogTimestamp = useRef(0)

  // Register browser
  const [regAddress, setRegAddress] = useState(60000)
  const [regCount, setRegCount] = useState(10)
  const [regFuncCode, setRegFuncCode] = useState(3)
  const [regStation, setRegStation] = useState(200)
  const [regResults, setRegResults] = useState<number[]>([])
  const [regLoading, setRegLoading] = useState(false)

  // Write register
  const [writeAddress, setWriteAddress] = useState(60000)
  const [writeValue, setWriteValue] = useState(0)

  // Error
  const [error, setError] = useState<string | null>(null)

  // ── Connection Management ──

  const refreshStatus = useCallback(async () => {
    try {
      const res = await getHardwareDebugStatusApi()
      const data = res.data
      setStatus(prev => ({
        ...prev,
        connected: data.connected,
        ip: data.ip || prev.ip,
        port: data.port || prev.port,
        a_boards: data.a_boards,
        b_boards: data.b_boards,
        slots_per_board: data.slots_per_board,
        connect_error: data.connect_error,
      }))
    } catch { /* ignore */ }
  }, [])

  const handleConnect = async () => {
    setConnecting(true)
    setError(null)
    try {
      const res = await hardwareDebugConnectApi(ip, port)
      if (res.data.success) {
        message.success(`连接成功: ${ip}:${port}`)
        await refreshStatus()
        // Auto-load data
        loadDeviceInfo()
        loadBoards()
      } else {
        setError(res.data.message || '连接失败')
        message.error(res.data.message || '连接失败')
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || '连接失败'
      setError(msg)
      message.error(msg)
    } finally {
      setConnecting(false)
    }
  }

  const handleDisconnect = async () => {
    try {
      await hardwareDebugDisconnectApi()
      message.success('已断开连接')
      setDeviceInfo(null)
      setRelays({})
      setBoards([])
      setBoardInfo(null)
      setBoardSlots({})
      setBoardAdValues({})
      setBoardCalibration(null)
      setPingRtt(null)
      setRegResults([])
      await refreshStatus()
    } catch { /* ignore */ }
  }

  const handlePing = async () => {
    try {
      const res = await hardwareDebugPingApi()
      if (res.data.success) {
        setPingRtt(res.data.rtt_ms)
        message.success(`通信正常 (RTT: ${res.data.rtt_ms}ms)`)
      } else {
        setPingRtt(null)
        message.warning('通信检测无响应')
      }
    } catch {
      setPingRtt(null)
      message.error('通信检测失败')
    }
  }

  // ── Data Loading ──

  const loadDeviceInfo = async () => {
    setDeviceInfoLoading(true)
    try {
      const [infoRes, configRes, relayRes] = await Promise.allSettled([
        getMainboardInfoApi(),
        getMainboardConfigApi(),
        getMainboardRelaysApi(),
      ])
      if (infoRes.status === 'fulfilled' && infoRes.value.data.success) {
        setDeviceInfo(infoRes.value.data.data)
      }
      if (configRes.status === 'fulfilled' && configRes.value.data.success) {
        const config = configRes.value.data.data
        if (config.ip) setIp(config.ip)
        if (config.a_boards !== undefined || config.b_boards !== undefined) {
          setStatus(prev => ({
            ...prev,
            a_boards: config.a_boards ?? prev.a_boards,
            b_boards: config.b_boards ?? prev.b_boards,
          }))
        }
      }
      if (relayRes.status === 'fulfilled' && relayRes.value.data.success) {
        setRelays(relayRes.value.data.data)
      }
    } catch { /* ignore */ }
    setDeviceInfoLoading(false)
  }

  const loadBoards = async () => {
    setBoardsLoading(true)
    try {
      const res = await getDebugBoardsApi()
      if (res.data.success) {
        const data = res.data.data
        setBoards(data.boards || [])
        setStatus(prev => ({
          ...prev,
          a_boards: data.a_boards,
          b_boards: data.b_boards,
          slots_per_board: data.slots_per_board,
        }))
        // Select first board
        const filtered = (data.boards || []).filter((b: Board) =>
          b.side === boardTab
        )
        if (filtered.length > 0) {
          setSelectedBoard(filtered[0].station)
        }
      }
    } catch { /* ignore */ }
    setBoardsLoading(false)
  }

  const loadBoardData = async (station: number) => {
    setBoardDataLoading(true)
    try {
      const [infoRes, slotsRes, adRes, calRes] = await Promise.allSettled([
        getDebugBoardInfoApi(station),
        getDebugBoardSlotsApi(station),
        getDebugBoardAdValuesApi(station),
        getDebugBoardCalibrationApi(station),
      ])
      if (infoRes.status === 'fulfilled' && infoRes.value.data.success) {
        setBoardInfo(infoRes.value.data.data)
      }
      if (slotsRes.status === 'fulfilled' && slotsRes.value.data.success) {
        setBoardSlots(slotsRes.value.data.data.slots || {})
      }
      if (adRes.status === 'fulfilled' && adRes.value.data.success) {
        setBoardAdValues(adRes.value.data.data)
      }
      if (calRes.status === 'fulfilled' && calRes.value.data.success) {
        setBoardCalibration(calRes.value.data.data)
      }
    } catch { /* ignore */ }
    setBoardDataLoading(false)
  }

  // ── Log Polling ──

  const loadLogs = useCallback(async (append = false) => {
    try {
      const params: any = { limit: 200 }
      if (append && lastLogTimestamp.current > 0) {
        params.since = lastLogTimestamp.current
      }
      if (logLevelFilter) {
        params.level = logLevelFilter
      }
      const res = await getHardwareDebugLogsApi(params.since, params.level, params.limit)
      if (res.data.success) {
        const newLogs = res.data.data || []
        if (newLogs.length > 0) {
          lastLogTimestamp.current = newLogs[newLogs.length - 1].timestamp
          if (append) {
            setLogs(prev => [...prev, ...newLogs].slice(-500))
          } else {
            setLogs(newLogs)
          }
        }
      }
    } catch { /* ignore */ }
  }, [logLevelFilter])

  // ── Effects ──

  // Initial load
  useEffect(() => {
    refreshStatus()
    loadLogs(false)
  }, [refreshStatus, loadLogs])

  // Auto-poll logs and ping when connected
  useEffect(() => {
    if (status.connected) {
      const timer = setInterval(async () => {
        await loadLogs(true)
      }, 2000)
      pollTimerRef.current = timer
      return () => {
        clearInterval(timer)
        pollTimerRef.current = null
      }
    } else {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current)
        pollTimerRef.current = null
      }
    }
  }, [status.connected, loadLogs])

  // Auto-scroll logs
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  // Load board data when selected board changes
  useEffect(() => {
    if (selectedBoard !== null && status.connected) {
      loadBoardData(selectedBoard)
    }
  }, [selectedBoard, status.connected])

  // Reload boards when tab changes
  useEffect(() => {
    const filtered = boards.filter(b => b.side === boardTab)
    if (filtered.length > 0) {
      setSelectedBoard(filtered[0].station)
    } else {
      setSelectedBoard(null)
      setBoardInfo(null)
      setBoardSlots({})
      setBoardAdValues({})
      setBoardCalibration(null)
    }
  }, [boardTab, boards])

  // ── Relay Control ──

  const handleRelayToggle = async (key: string, value: boolean) => {
    const num = parseInt(key.replace('K', ''))
    try {
      await setMainboardRelayApi(num, value)
      setRelays(prev => ({ ...prev, [key]: value }))
      message.success(`继电器 ${key} → ${value ? 'ON' : 'OFF'}`)
    } catch {
      message.error(`继电器 ${key} 控制失败`)
    }
  }

  // ── LED Control ──

  const handleSlotClick = async (slotNum: number) => {
    if (selectedBoard === null) return
    const key = `slot_${slotNum}`
    const current = boardSlots[key]
    // Cycle through: off(if occupied then turn off) -> green -> red -> blue -> off
    const currentColors = ['green', 'red', 'blue', 'off']
    let nextColor = 'green'
    if (current === true) {
      nextColor = 'off'  // If occupied, turn off to test
    }
    // If we already know a color was set, cycle
    try {
      await debugControlLedApi(selectedBoard, slotNum, nextColor)
      message.success(`储位 ${slotNum} LED → ${nextColor}`)
    } catch {
      message.error(`LED 控制失败`)
    }
  }

  const handleSlotColorSelect = async (slotNum: number, color: string) => {
    if (selectedBoard === null) return
    try {
      await debugControlLedApi(selectedBoard, slotNum, color)
      message.success(`储位 ${slotNum} LED → ${color}`)
    } catch {
      message.error(`LED 控制失败`)
    }
  }

  const handleLedTest = async (station: number) => {
    setTestRunning(station)
    try {
      await debugLedTestApi(station)
      message.success('LED 测试序列已启动')
    } catch {
      message.error('LED 测试启动失败')
    } finally {
      setTimeout(() => setTestRunning(null), 3000)
    }
  }

  const handleAllLedsOff = async (station: number) => {
    const colors = Array(20).fill('off')
    try {
      await debugControlAllLedsApi(station, colors)
      message.success('全部 LED 已关闭')
    } catch {
      message.error('关闭失败')
    }
  }

  // ── Board Actions ──

  const handleCalibrateBoard = async (station: number) => {
    try {
      await debugCalibrateBoardApi(station)
      message.success(`灯板 (站号 ${station}) 校准命令已发送`)
    } catch {
      message.error('校准失败')
    }
  }

  const handleResetBoard = async (station: number) => {
    try {
      await debugResetBoardApi(station)
      message.success(`灯板 (站号 ${station}) 复位命令已发送`)
    } catch {
      message.error('复位失败')
    }
  }

  const handleSetJudgment = async (station: number) => {
    try {
      await debugSetJudgmentApi(station, judgmentValue)
      message.success(`判定值设为 ${judgmentValue}`)
    } catch {
      message.error('设置判定值失败')
    }
  }

  // ── Register Browser ──

  const handleReadRegisters = async () => {
    setRegLoading(true)
    try {
      const res = await debugReadRegistersApi(regAddress, regCount, regFuncCode, regStation)
      if (res.data.success) {
        setRegResults(res.data.data)
      }
    } catch (err: any) {
      message.error(err.response?.data?.detail || '读取失败')
    }
    setRegLoading(false)
  }

  const handleWriteRegister = async () => {
    try {
      await debugWriteRegisterApi(writeAddress, writeValue, regStation)
      message.success(`寄存器 ${writeAddress} = 0x${writeValue.toString(16).padStart(4, '0')}`)
    } catch (err: any) {
      message.error(err.response?.data?.detail || '写入失败')
    }
  }

  // ── Mainboard Actions ──

  const handleCalibrateMainboard = async () => {
    try {
      await calibrateMainboardApi()
      message.success('主控板校准命令已发送')
    } catch {
      message.error('校准失败')
    }
  }

  const handleResetMainboard = async () => {
    try {
      await resetMainboardApi()
      message.success('主控板复位命令已发送')
      setTimeout(() => refreshStatus(), 5000)
    } catch {
      message.error('复位失败')
    }
  }

  const handleSaveConfig = async () => {
    try {
      await saveMainboardConfigApi()
      message.success('配置已保存')
    } catch {
      message.error('保存失败')
    }
  }

  // ── Log Controls ──

  const handleClearLogs = async () => {
    try {
      await clearHardwareDebugLogsApi()
      setLogs([])
      lastLogTimestamp.current = 0
      message.success('日志已清除')
    } catch {
      message.error('清除失败')
    }
  }

  // ── Format helpers ──

  const formatUptime = (seconds: number) => {
    const d = Math.floor(seconds / 86400)
    const h = Math.floor((seconds % 86400) / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    const s = seconds % 60
    return `${d}d ${h}h ${m}m ${s}s`
  }

  const formatTimestamp = (ts: number) => {
    const d = new Date(ts * 1000)
    return d.toLocaleTimeString('zh-CN', { hour12: false })
  }

  // ── Render: Connection Panel ──

  const renderConnectionPanel = () => (
    <Card
      title={
        <Space>
          <ApiOutlined />
          <span>主控板连接</span>
          {status.connected ? (
            <Tag icon={<CheckCircleOutlined />} color="success">已连接</Tag>
          ) : (
            <Tag icon={<CloseCircleOutlined />} color="error">未连接</Tag>
          )}
        </Space>
      }
      style={{ marginBottom: 16 }}
    >
      <Row gutter={16} align="middle">
        <Col span={4}>
          <Text strong>IP 地址:</Text>
          <Input
            value={ip}
            onChange={e => setIp(e.target.value)}
            placeholder="192.168.1.100"
            disabled={status.connected}
            style={{ marginTop: 4 }}
          />
        </Col>
        <Col span={3}>
          <Text strong>端口:</Text>
          <InputNumber
            value={port}
            onChange={v => setPort(v || 502)}
            min={1}
            max={65535}
            disabled={status.connected}
            style={{ marginTop: 4, width: '100%' }}
          />
        </Col>
        <Col span={6}>
          <Space style={{ marginTop: 22 }}>
            {!status.connected ? (
              <Button
                type="primary"
                icon={<PoweroffOutlined />}
                onClick={handleConnect}
                loading={connecting}
              >
                连接
              </Button>
            ) : (
              <>
                <Button
                  danger
                  icon={<PoweroffOutlined />}
                  onClick={handleDisconnect}
                >
                  断开
                </Button>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={handlePing}
                >
                  Ping
                </Button>
                {pingRtt !== null && (
                  <Tag color={pingRtt < 100 ? 'green' : pingRtt < 500 ? 'orange' : 'red'}>
                    {pingRtt}ms
                  </Tag>
                )}
              </>
            )}
            <Button onClick={() => { refreshStatus(); loadDeviceInfo(); loadBoards() }}>
              刷新
            </Button>
          </Space>
        </Col>
        {status.connected && (
          <Col span={8}>
            <Badge status={status.connected ? 'success' : 'error'} />
            <Text type="secondary">
              已连接到 {status.ip}:{status.port}
            </Text>
          </Col>
        )}
      </Row>
      {error && (
        <Alert
          message={error}
          type="error"
          showIcon
          closable
          onClose={() => setError(null)}
          style={{ marginTop: 12 }}
        />
      )}
    </Card>
  )

  // ── Render: Device Info ──

  const renderDeviceInfo = () => {
    if (!deviceInfo) return null

    const modeDesc = [
      deviceInfo.is_tcp ? 'TCP' : 'RTU',
      deviceInfo.config_mode ? '配置模式' : '正常工作',
      deviceInfo.eth_enabled ? '以太网' : '',
      deviceInfo.wifi_enabled ? 'WiFi' : '',
      deviceInfo.com1_enabled ? 'COM1(A)' : '',
      deviceInfo.com2_enabled ? 'COM2(B)' : '',
    ].filter(Boolean).join(' | ')

    return (
      <Card
        title="设备信息"
        size="small"
        style={{ marginBottom: 16 }}
        loading={deviceInfoLoading}
        extra={
          <Space>
            <Button size="small" icon={<ReloadOutlined />} onClick={loadDeviceInfo}>
              刷新
            </Button>
          </Space>
        }
      >
        <Descriptions column={3} size="small" bordered>
          <Descriptions.Item label="设备型号">{deviceInfo.model_name || 'N/A'}</Descriptions.Item>
          <Descriptions.Item label="站号">{deviceInfo.station_addr}</Descriptions.Item>
          <Descriptions.Item label="版本">
            硬件 V{(deviceInfo.hw_sw_version >> 8) & 0xFF}.{deviceInfo.hw_sw_version & 0xFF}
          </Descriptions.Item>
          <Descriptions.Item label="运行模式">
            <Tag color={deviceInfo.config_mode ? 'orange' : 'green'}>{modeDesc}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="电源电压">
            <Text strong style={{ color: deviceInfo.voltage < 11 ? '#ff4d4f' : '#52c41a' }}>
              {deviceInfo.voltage}V
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="运行时间">{formatUptime(deviceInfo.uptime_seconds)}</Descriptions.Item>
          <Descriptions.Item label="通信总次数">{deviceInfo.total_communications?.toLocaleString()}</Descriptions.Item>
          <Descriptions.Item label="错误次数">
            <Text style={{ color: deviceInfo.error_count > 0 ? '#ff4d4f' : undefined }}>
              {deviceInfo.error_count}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="状态">
            <Space>
              {deviceInfo.has_error && <Tag color="error">错误</Tag>}
              {deviceInfo.is_busy && <Tag color="processing">忙</Tag>}
              {!deviceInfo.has_error && !deviceInfo.is_busy && <Tag color="success">正常</Tag>}
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label="以太网">{deviceInfo.eth_enabled ? '启用' : '禁用'}</Descriptions.Item>
          <Descriptions.Item label="WiFi">{deviceInfo.wifi_enabled ? '启用' : '禁用'}</Descriptions.Item>
          <Descriptions.Item label="COM1 (A面)">{deviceInfo.com1_enabled ? '启用' : '禁用'}</Descriptions.Item>
          <Descriptions.Item label="COM2 (B面)">{deviceInfo.com2_enabled ? '启用' : '禁用'}</Descriptions.Item>
        </Descriptions>
      </Card>
    )
  }

  // ── Render: Relay Control ──

  const renderRelayControl = () => (
    <Card title="继电器控制 (K1-K6)" size="small" style={{ marginBottom: 16 }}>
      <Row gutter={[16, 12]}>
        {['K1', 'K2', 'K3', 'K4', 'K5', 'K6'].map(key => (
          <Col span={4} key={key}>
            <Space>
              <Text strong>{key}</Text>
              <Switch
                checked={relays[key] || false}
                onChange={checked => handleRelayToggle(key, checked)}
                checkedChildren="ON"
                unCheckedChildren="OFF"
              />
            </Space>
          </Col>
        ))}
      </Row>
    </Card>
  )

  // ── Render: Boards Panel ──

  const renderBoardSelector = () => {
    const filtered = boards.filter(b => b.side === boardTab)
    return (
      <Space style={{ marginBottom: 12 }}>
        <Radio.Group
          value={boardTab}
          onChange={e => setBoardTab(e.target.value)}
          optionType="button"
          buttonStyle="solid"
        >
          <Radio.Button value="A">
            A 面 ({status.a_boards} 块)
          </Radio.Button>
          <Radio.Button value="B">
            B 面 ({status.b_boards} 块)
          </Radio.Button>
        </Radio.Group>
        <Select
          value={selectedBoard}
          onChange={v => setSelectedBoard(v)}
          style={{ width: 200 }}
          placeholder="选择灯板"
          options={filtered.map(b => ({
            value: b.station,
            label: b.label,
          }))}
        />
        <Button icon={<ReloadOutlined />} onClick={loadBoards}>
          刷新
        </Button>
      </Space>
    )
  }

  const renderBoardInfo = () => {
    if (!boardInfo || selectedBoard === null) return null

    const station = selectedBoard
    const channels = boardInfo.channel_count || 20

    return (
      <Card
        title={`灯板信息 (站号 ${station})`}
        size="small"
        style={{ marginBottom: 12 }}
        loading={boardDataLoading}
        extra={
          <Space>
            <Button
              size="small"
              icon={<ExperimentOutlined />}
              onClick={() => handleCalibrateBoard(station)}
            >
              校准
            </Button>
            <Popconfirm title="确认复位该灯板?" onConfirm={() => handleResetBoard(station)}>
              <Button size="small" danger icon={<ReloadOutlined />}>复位</Button>
            </Popconfirm>
          </Space>
        }
      >
        <Row gutter={16}>
          <Col span={12}>
            <Descriptions column={2} size="small">
              <Descriptions.Item label="型号">{boardInfo.model || 'N/A'}</Descriptions.Item>
              <Descriptions.Item label="通道数">{channels}</Descriptions.Item>
              <Descriptions.Item label="硬件版本">{boardInfo.hw_version || 'N/A'}</Descriptions.Item>
              <Descriptions.Item label="软件版本">{boardInfo.sw_version || 'N/A'}</Descriptions.Item>
              <Descriptions.Item label="编译日期">{boardInfo.compile_date || 'N/A'}</Descriptions.Item>
            </Descriptions>
          </Col>
          <Col span={12}>
            <Space style={{ marginBottom: 8 }}>
              <Button
                icon={<BulbOutlined />}
                onClick={() => handleLedTest(station)}
                loading={testRunning === station}
              >
                LED 测试序列
              </Button>
              <Button
                icon={<ClearOutlined />}
                onClick={() => handleAllLedsOff(station)}
              >
                全部关闭
              </Button>
            </Space>
            <br />
            <Space>
              <Text>判定值:</Text>
              <InputNumber
                value={judgmentValue}
                onChange={v => setJudgmentValue(v || 50)}
                min={0}
                max={255}
                size="small"
                style={{ width: 80 }}
              />
              <Text type="secondary">≈ {(judgmentValue * 0.0196).toFixed(3)}V</Text>
              <Button size="small" onClick={() => handleSetJudgment(station)}>
                设置
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>
    )
  }

  const renderSlotGrid = () => {
    if (selectedBoard === null) return null

    const slotCount = status.slots_per_board || 20

    return (
      <Card
        title={`储位状态 (共 ${slotCount} 个储位)`}
        size="small"
        style={{ marginBottom: 12 }}
        loading={boardDataLoading}
        extra={
          <Space>
            <Tag color="green">有物料</Tag>
            <Tag color="default">空位</Tag>
          </Space>
        }
      >
        <Row gutter={[8, 8]}>
          {Array.from({ length: slotCount }, (_, i) => i + 1).map(slotNum => {
            const key = `slot_${slotNum}`
            const hasMaterial = boardSlots[key]
            const adVal = boardAdValues[`slot_${slotNum}`]
            return (
              <Col span={3} key={slotNum}>
                <Tooltip
                  title={
                    <div>
                      <div>储位 {slotNum}</div>
                      <div>状态: {hasMaterial ? '有物料' : '空位'}</div>
                      {adVal !== undefined && <div>AD 值: {adVal}</div>}
                      <div style={{ marginTop: 4 }}>
                        {LED_COLORS.map(c => (
                          <Tag
                            key={c}
                            color={c === 'off' ? 'default' : c}
                            style={{ cursor: 'pointer', margin: 1 }}
                            onClick={() => handleSlotColorSelect(slotNum, c)}
                          >
                            {c}
                          </Tag>
                        ))}
                      </div>
                    </div>
                  }
                >
                  <div
                    onClick={() => handleSlotClick(slotNum)}
                    style={{
                      width: '100%',
                      padding: '12px 4px',
                      textAlign: 'center',
                      borderRadius: 4,
                      cursor: 'pointer',
                      background: hasMaterial ? '#52c41a' : '#f0f0f0',
                      color: hasMaterial ? '#fff' : '#999',
                      border: selectedSlot === slotNum ? '2px solid #1890ff' : '1px solid #d9d9d9',
                      fontWeight: hasMaterial ? 'bold' : 'normal',
                      fontSize: 13,
                      transition: 'all 0.2s',
                    }}
                    onMouseEnter={() => setSelectedSlot(slotNum)}
                    onMouseLeave={() => setSelectedSlot(null)}
                  >
                    <div>{slotNum}</div>
                    {adVal !== undefined && (
                      <div style={{ fontSize: 10, opacity: 0.8 }}>{adVal}</div>
                    )}
                  </div>
                </Tooltip>
              </Col>
            )
          })}
        </Row>
      </Card>
    )
  }

  const renderBoardDetails = () => {
    if (!boardCalibration) return null

    return (
      <Collapse
        size="small"
        style={{ marginBottom: 12 }}
        items={[
          {
            key: 'ad',
            label: 'AD 采样值 & 校准值',
            children: (
              <Row gutter={16}>
                <Col span={8}>
                  <Descriptions title="AD 采样值" column={2} size="small" bordered>
                    {Object.entries(boardAdValues).slice(0, 20).map(([key, val]) => (
                      <Descriptions.Item key={key} label={key.replace('slot_', 'CH')}>
                        {val}
                      </Descriptions.Item>
                    ))}
                  </Descriptions>
                </Col>
                <Col span={8}>
                  {boardCalibration.calibration && (
                    <Descriptions title="红外校准值" column={2} size="small" bordered>
                      {boardCalibration.calibration.map((val: number, i: number) => (
                        <Descriptions.Item key={i} label={`CH ${i * 2 + 1}-${i * 2 + 2}`}>
                          0x{val.toString(16).padStart(4, '0')}
                        </Descriptions.Item>
                      ))}
                    </Descriptions>
                  )}
                </Col>
                <Col span={8}>
                  {boardCalibration.judgment && (
                    <Descriptions title="判定值" column={2} size="small" bordered>
                      {boardCalibration.judgment.map((val: number, i: number) => (
                        <Descriptions.Item key={i} label={`CH ${i * 2 + 1}-${i * 2 + 2}`}>
                          {val}
                        </Descriptions.Item>
                      ))}
                    </Descriptions>
                  )}
                </Col>
              </Row>
            ),
          },
        ]}
      />
    )
  }

  const renderBoardsPanel = () => (
    <Card
      title={
        <Space>
          <ThunderboltOutlined />
          <span>感应灯板调试</span>
          {boards.length > 0 && (
            <Tag>{boards.length} 块灯板</Tag>
          )}
        </Space>
      }
      style={{ marginBottom: 16 }}
    >
      {renderBoardSelector()}
      {selectedBoard !== null && (
        <>
          {renderBoardInfo()}
          {renderSlotGrid()}
          {renderBoardDetails()}
        </>
      )}
      {!status.connected && (
        <Alert message="请先连接主控板" type="info" showIcon />
      )}
      {status.connected && boards.length === 0 && (
        <Alert
          message="未检测到灯板配置。请先在料架管理中配置灯板数量，或使用寄存器浏览器写入 60108 (A面数量) 和 60109 (B面数量)。"
          type="warning"
          showIcon
        />
      )}
    </Card>
  )

  // ── Render: Register Browser ──

  const renderRegisterBrowser = () => (
    <Card
      title={
        <Space>
          <BugOutlined />
          <span>寄存器浏览器 (Raw Modbus)</span>
        </Space>
      }
      size="small"
      style={{ marginBottom: 16 }}
    >
      <Row gutter={16} style={{ marginBottom: 12 }}>
        <Col span={4}>
          <Text strong>功能码</Text>
          <Select
            value={regFuncCode}
            onChange={setRegFuncCode}
            style={{ width: '100%', marginTop: 4 }}
            options={[
              { value: 3, label: 'FC 3 (读保持寄存器)' },
              { value: 4, label: 'FC 4 (读输入寄存器)' },
            ]}
          />
        </Col>
        <Col span={3}>
          <Text strong>起始地址</Text>
          <InputNumber
            value={regAddress}
            onChange={v => setRegAddress(v || 0)}
            min={0}
            max={65535}
            style={{ width: '100%', marginTop: 4 }}
          />
        </Col>
        <Col span={2}>
          <Text strong>数量</Text>
          <InputNumber
            value={regCount}
            onChange={v => setRegCount(v || 1)}
            min={1}
            max={100}
            style={{ width: '100%', marginTop: 4 }}
          />
        </Col>
        <Col span={2}>
          <Text strong>站号</Text>
          <InputNumber
            value={regStation}
            onChange={v => setRegStation(v || 200)}
            min={1}
            max={255}
            style={{ width: '100%', marginTop: 4 }}
          />
        </Col>
        <Col span={3}>
          <div style={{ marginTop: 22 }}>
            <Button
              type="primary"
              onClick={handleReadRegisters}
              loading={regLoading}
            >
              读取
            </Button>
          </div>
        </Col>
      </Row>
      {regResults.length > 0 && (
        <>
          <Table
            dataSource={regResults.map((val, i) => ({
              key: i,
              address: regAddress + i,
              hex: `0x${val.toString(16).toUpperCase().padStart(4, '0')}`,
              decimal: val,
              binary: val.toString(2).padStart(16, '0'),
            }))}
            columns={[
              { title: '地址', dataIndex: 'address', width: 100 },
              { title: '十六进制', dataIndex: 'hex', width: 100 },
              { title: '十进制', dataIndex: 'decimal', width: 100 },
              { title: '二进制', dataIndex: 'binary', width: 180 },
            ]}
            pagination={false}
            size="small"
            bordered
          />
        </>
      )}
      <Divider orientation="left" style={{ fontSize: 12 }}>写寄存器</Divider>
      <Row gutter={16} align="middle">
        <Col span={3}>
          <Text strong>地址</Text>
          <InputNumber
            value={writeAddress}
            onChange={v => setWriteAddress(v || 0)}
            min={0}
            max={65535}
            style={{ width: '100%', marginTop: 4 }}
          />
        </Col>
        <Col span={3}>
          <Text strong>值</Text>
          <InputNumber
            value={writeValue}
            onChange={v => setWriteValue(v || 0)}
            min={0}
            max={65535}
            style={{ width: '100%', marginTop: 4 }}
          />
        </Col>
        <Col span={3}>
          <div style={{ marginTop: 22 }}>
            <Button onClick={handleWriteRegister}>
              写入 (FC 6)
            </Button>
          </div>
        </Col>
      </Row>
    </Card>
  )

  // ── Render: Mainboard Actions ──

  const renderMainboardActions = () => (
    <Card title="主控板操作" size="small" style={{ marginBottom: 16 }}>
      <Space wrap>
        <Popconfirm title="确认校准所有灯板?" onConfirm={handleCalibrateMainboard}>
          <Button icon={<ExperimentOutlined />}>
            全局校准
          </Button>
        </Popconfirm>
        <Popconfirm
          title="确认复位主控板? 连接将断开。"
          onConfirm={handleResetMainboard}
        >
          <Button danger icon={<ReloadOutlined />}>
            复位主控板
          </Button>
        </Popconfirm>
        <Button icon={<SettingOutlined />} onClick={handleSaveConfig}>
          保存配置
        </Button>
      </Space>
    </Card>
  )

  // ── Render: Debug Log ──

  const renderDebugLog = () => (
    <Card
      title={
        <Space>
          <BugOutlined />
          <span>调试日志</span>
          <Tag>{logs.length} 条</Tag>
        </Space>
      }
      extra={
        <Space>
          <Select
            value={logLevelFilter || 'all'}
            onChange={v => setLogLevelFilter(v === 'all' ? null : v)}
            size="small"
            style={{ width: 100 }}
            options={[
              { value: 'all', label: '全部' },
              { value: 'info', label: 'Info' },
              { value: 'warn', label: 'Warn' },
              { value: 'error', label: 'Error' },
            ]}
          />
          <Switch
            checked={autoScroll}
            onChange={setAutoScroll}
            checkedChildren="自动滚"
            unCheckedChildren="停止"
            size="small"
          />
          <Button size="small" icon={<DeleteOutlined />} onClick={handleClearLogs}>
            清除
          </Button>
          <Button size="small" icon={<ReloadOutlined />} onClick={() => loadLogs(false)}>
            刷新
          </Button>
        </Space>
      }
    >
      <div
        ref={logContainerRef}
        style={{
          height: 300,
          overflow: 'auto',
          background: '#1e1e1e',
          color: '#d4d4d4',
          padding: 8,
          borderRadius: 4,
          fontFamily: 'monospace',
          fontSize: 12,
        }}
      >
        {logs.length === 0 ? (
          <div style={{ color: '#666', textAlign: 'center', paddingTop: 120 }}>
            暂无日志
          </div>
        ) : (
          logs.map((entry, i) => (
            <div key={i} style={{ marginBottom: 2, whiteSpace: 'nowrap' }}>
              <span style={{ color: '#888' }}>
                [{formatTimestamp(entry.timestamp)}]
              </span>
              <span
                style={{
                  color: LOG_LEVEL_COLORS[entry.level] || '#d4d4d4',
                  margin: '0 8px',
                  fontWeight: entry.level === 'error' ? 'bold' : 'normal',
                }}
              >
                [{entry.level.toUpperCase()}]
              </span>
              <span style={{ color: '#569cd6' }}>[{entry.source}]</span>
              <span style={{ marginLeft: 8 }}>{entry.message}</span>
            </div>
          ))
        )}
      </div>
    </Card>
  )

  // ── Main Render ──

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>
          <BugOutlined style={{ marginRight: 8 }} />
          硬件调试
        </h2>
      </div>

      {renderConnectionPanel()}

      {status.connected && (
        <>
          {renderDeviceInfo()}
          {renderRelayControl()}
          {renderMainboardActions()}
          {renderBoardsPanel()}
          {renderRegisterBrowser()}
        </>
      )}

      {renderDebugLog()}
    </div>
  )
}
