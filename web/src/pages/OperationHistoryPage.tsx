import { useEffect, useState, useCallback } from 'react'
import {
  Card,
  Table,
  DatePicker,
  Select,
  Input,
  Button,
  Space,
  Tag,
  Typography,
  Row,
  Col,
  Empty,
  message,
} from 'antd'
import { SearchOutlined, ReloadOutlined, HistoryOutlined } from '@ant-design/icons'
import dayjs, { Dayjs } from 'dayjs'
import { getOperationHistoryApi, getOperationHistoryTypesApi } from '../api'
import type { ColumnsType } from 'antd/es/table'

const { RangePicker } = DatePicker
const { Text } = Typography

// ── Type definitions ──
interface OperationRecord {
  id: number
  operation_type: string
  operation_type_label: string
  shelving_mode: string | null
  shelving_mode_label: string | null
  led_color: string | null
  reel_id: number | null
  reel_code: string | null
  material_id: number | null
  material_code: string | null
  material_name: string | null
  shelf_id: number | null
  shelf_code: string | null
  slot_id: number | null
  slot_code: string | null
  customer_id: number | null
  quantity: number | null
  source_type: string | null
  source_id: number | null
  source_no: string | null
  operator: string | null
  note: string | null
  created_at: string | null
}

interface OperationTypeOption {
  value: string
  label: string
}

interface ShelvingModeOption {
  value: string
  label: string
}

// ── Color helpers ──
const OPERATION_COLORS: Record<string, string> = {
  shelving_on: 'green',
  shelving_off: 'orange',
  inventory_in: 'blue',
  inventory_out: 'red',
  adjustment: 'purple',
}

const LED_COLOR_HEX: Record<string, string> = {
  red: '#ff4d4f',
  green: '#52c41a',
  yellow: '#faad14',
  blue: '#1677ff',
  magenta: '#eb2f96',
  cyan: '#13c2c2',
  white: '#d9d9d9',
}

export function OperationHistoryPage() {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<OperationRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // Filters
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>([
    dayjs().startOf('day'),
    dayjs().endOf('day'),
  ])
  const [operationType, setOperationType] = useState<string | undefined>(undefined)
  const [shelvingMode, setShelvingMode] = useState<string | undefined>(undefined)
  const [keyword, setKeyword] = useState('')

  // Filter options
  const [operationTypes, setOperationTypes] = useState<OperationTypeOption[]>([])
  const [shelvingModes, setShelvingModes] = useState<ShelvingModeOption[]>([])

  // ── Load filter options ──
  useEffect(() => {
    getOperationHistoryTypesApi().then((res) => {
      setOperationTypes(res.data.operation_types || [])
      setShelvingModes(res.data.shelving_modes || [])
    }).catch(() => {
      // ignore
    })
  }, [])

  // ── Load data ──
  const loadData = useCallback(async () => {
    if (!dateRange[0] || !dateRange[1]) {
      message.warning('请选择查询时间段')
      return
    }
    setLoading(true)
    try {
      const startTime = dateRange[0].format('YYYY-MM-DDTHH:mm:ss')
      const endTime = dateRange[1].format('YYYY-MM-DDTHH:mm:ss')
      const res = await getOperationHistoryApi({
        start_time: startTime,
        end_time: endTime,
        operation_type: operationType,
        shelving_mode: shelvingMode,
        keyword: keyword || undefined,
        page,
        page_size: pageSize,
      })
      setData(res.data.items || [])
      setTotal(res.data.total || 0)
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '查询失败')
    } finally {
      setLoading(false)
    }
  }, [dateRange, operationType, shelvingMode, keyword, page, pageSize])

  // Initial load
  useEffect(() => {
    loadData()
  }, [loadData])

  // ── Table columns ──
  const columns: ColumnsType<OperationRecord> = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (val: string) => val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
    {
      title: '操作类型',
      dataIndex: 'operation_type',
      key: 'operation_type',
      width: 100,
      render: (_: string, record: OperationRecord) => (
        <Tag color={OPERATION_COLORS[record.operation_type] || 'default'}>
          {record.operation_type_label || record.operation_type}
        </Tag>
      ),
    },
    {
      title: '上架模式',
      dataIndex: 'shelving_mode',
      key: 'shelving_mode',
      width: 100,
      render: (mode: string | null, record: OperationRecord) => {
        if (!mode) return <Text type="secondary">-</Text>
        const color = mode === 'auto' ? 'blue' : 'orange'
        return <Tag color={color}>{record.shelving_mode_label || mode}</Tag>
      },
    },
    {
      title: 'LED颜色',
      dataIndex: 'led_color',
      key: 'led_color',
      width: 80,
      render: (color: string | null) => {
        if (!color) return <Text type="secondary">-</Text>
        const hex = LED_COLOR_HEX[color] || '#999'
        return (
          <Space>
            <span
              style={{
                display: 'inline-block',
                width: 12,
                height: 12,
                borderRadius: '50%',
                backgroundColor: hex,
                border: '1px solid #d9d9d9',
              }}
            />
            <Text>{color}</Text>
          </Space>
        )
      },
    },
    {
      title: '物料编码',
      dataIndex: 'material_code',
      key: 'material_code',
      width: 140,
      render: (val: string | null) => val || '-',
    },
    {
      title: '物料名称',
      dataIndex: 'material_name',
      key: 'material_name',
      width: 180,
      ellipsis: true,
      render: (val: string | null) => val || '-',
    },
    {
      title: '卷盘编码',
      dataIndex: 'reel_code',
      key: 'reel_code',
      width: 150,
      render: (val: string | null) => val || '-',
    },
    {
      title: '料架/储位',
      key: 'location',
      width: 140,
      render: (_: any, record: OperationRecord) => {
        if (!record.shelf_code && !record.slot_code) return <Text type="secondary">-</Text>
        const parts = []
        if (record.shelf_code) parts.push(record.shelf_code)
        if (record.slot_code) parts.push(record.slot_code)
        return parts.join(' / ')
      },
    },
    {
      title: '数量',
      dataIndex: 'quantity',
      key: 'quantity',
      width: 80,
      align: 'right',
      render: (val: number | null) => (val != null ? val : '-'),
    },
    {
      title: '来源',
      dataIndex: 'source_no',
      key: 'source_no',
      width: 140,
      render: (val: string | null) => val || '-',
    },
    {
      title: '操作人',
      dataIndex: 'operator',
      key: 'operator',
      width: 100,
      render: (val: string | null) => val || '-',
    },
    {
      title: '备注',
      dataIndex: 'note',
      key: 'note',
      width: 200,
      ellipsis: true,
      render: (val: string | null) => val || '-',
    },
  ]

  return (
    <div>
      <Card>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {/* Header */}
          <Row justify="space-between" align="middle">
            <Col>
              <Space>
                <HistoryOutlined style={{ fontSize: 20, color: '#1677ff' }} />
                <Typography.Title level={4} style={{ margin: 0 }}>
                  作业履历
                </Typography.Title>
              </Space>
            </Col>
            <Col>
              <Text type="secondary">
                共 {total} 条记录
              </Text>
            </Col>
          </Row>

          {/* Filters */}
          <Row gutter={[16, 12]}>
            <Col xs={24} sm={12} md={6}>
              <div style={{ marginBottom: 4 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>查询时间段</Text>
              </div>
              <RangePicker
                showTime
                value={dateRange as any}
                onChange={(dates) => {
                  if (dates && dates[0] && dates[1]) {
                    setDateRange([dates[0], dates[1]])
                  }
                }}
                style={{ width: '100%' }}
                format="YYYY-MM-DD HH:mm:ss"
              />
            </Col>
            <Col xs={12} sm={6} md={3}>
              <div style={{ marginBottom: 4 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>操作类型</Text>
              </div>
              <Select
                allowClear
                placeholder="全部类型"
                value={operationType}
                onChange={(val) => { setOperationType(val); setPage(1) }}
                style={{ width: '100%' }}
                options={operationTypes}
              />
            </Col>
            <Col xs={12} sm={6} md={3}>
              <div style={{ marginBottom: 4 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>上架模式</Text>
              </div>
              <Select
                allowClear
                placeholder="全部模式"
                value={shelvingMode}
                onChange={(val) => { setShelvingMode(val); setPage(1) }}
                style={{ width: '100%' }}
                options={shelvingModes}
              />
            </Col>
            <Col xs={16} sm={8} md={6}>
              <div style={{ marginBottom: 4 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>搜索</Text>
              </div>
              <Input.Search
                placeholder="物料编码/名称/卷盘编码"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                onSearch={() => setPage(1)}
                allowClear
                enterButton={<SearchOutlined />}
              />
            </Col>
            <Col xs={8} sm={4} md={3} style={{ display: 'flex', alignItems: 'flex-end' }}>
              <Button type="primary" icon={<SearchOutlined />} onClick={() => { setPage(1); loadData() }} style={{ width: '100%' }}>
                查询
              </Button>
            </Col>
            <Col xs={0} sm={2} md={1} style={{ display: 'flex', alignItems: 'flex-end' }}>
              <Button icon={<ReloadOutlined />} onClick={loadData} />
            </Col>
          </Row>
        </Space>
      </Card>

      <Card style={{ marginTop: 16 }}>
        <Table<OperationRecord>
          columns={columns}
          dataSource={data}
          rowKey="id"
          loading={loading}
          scroll={{ x: 1400 }}
          locale={{ emptyText: <Empty description="暂无作业履历数据" /> }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            pageSizeOptions: ['10', '20', '50', '100'],
            onChange: (p, ps) => {
              setPage(p)
              setPageSize(ps)
            },
          }}
        />
      </Card>
    </div>
  )
}
