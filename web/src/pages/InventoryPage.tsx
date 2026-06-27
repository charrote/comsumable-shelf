import { useState, useEffect, useCallback } from 'react'
import { Table, Input, Space, Tag, Select, Spin, message, Button, Modal } from 'antd'
import { SearchOutlined, ExportOutlined } from '@ant-design/icons'
import { getInventoryApi, directOutboundApi, getCustomersApi, exportInventoryApi } from '../api'

const { Option } = Select

interface InventoryItem {
  reel_id: number
  reel_code: string
  material_code: string
  quantity: number
  first_in_time: string
  shelf_slot_id: number | null
  status: string
  customer_name?: string
  customer_code?: string
  customer_id?: number
}

const statusColors: Record<string, string> = {
  pending_shelving: 'gold',
  on_shelf: 'green',
  in_use: 'blue',
  tracking: 'orange',
  exhausted: 'red',
  ready_restock: 'purple',
}

const statusLabels: Record<string, string> = {
  pending_shelving: '待上架',
  on_shelf: '在架',
  in_use: '使用中',
  tracking: '跟踪中',
  exhausted: '已耗尽',
  ready_restock: '待退库',
}

const allStatusOptions = Object.keys(statusLabels).map(key => ({
  value: key,
  label: statusLabels[key],
}))

export function InventoryPage() {
  const [data, setData] = useState<InventoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [selectedCustomers, setSelectedCustomers] = useState<number[]>([])
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([])
  const [customers, setCustomers] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [exporting, setExporting] = useState(false)

  // ── Direct outbound modal (whole-reel mode) ──
  const [directModalVisible, setDirectModalVisible] = useState(false)
  const [directTarget, setDirectTarget] = useState<InventoryItem | null>(null)
  const [directLoading, setDirectLoading] = useState(false)

  useEffect(() => {
    getCustomersApi().then(res => setCustomers(Array.isArray(res.data) ? res.data : [])).catch(() => {})
  }, [])

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, any> = {}
      if (keyword) params.keyword = keyword
      if (selectedCustomers.length > 0) params.customer_ids = selectedCustomers
      if (selectedStatuses.length > 0) params.statuses = selectedStatuses
      const res = await getInventoryApi(params)
      const body = res.data
      const items: InventoryItem[] = body?.pallets ?? (Array.isArray(body) ? body : [])
      setData(items)
      setTotal(items.length)
    } catch (err: any) {
      message.error(err.response?.data?.detail || '加载库存数据失败')
    } finally {
      setLoading(false)
    }
  }, [keyword, selectedCustomers, selectedStatuses])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // ── Export inventory to Excel ──
  const handleExport = async () => {
    setExporting(true)
    try {
      const params: Record<string, any> = {}
      if (keyword) params.keyword = keyword
      if (selectedCustomers.length > 0) params.customer_ids = selectedCustomers
      if (selectedStatuses.length > 0) params.statuses = selectedStatuses
      await exportInventoryApi(params)
      message.success('库存列表已导出')
    } catch (err: any) {
      message.error('导出失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setExporting(false)
    }
  }

  // ── Open direct outbound modal ──
  const handleOpenDirect = (item: InventoryItem) => {
    setDirectTarget(item)
    setDirectModalVisible(true)
  }

  // ── Confirm direct outbound (whole-reel) ──
  const handleConfirmDirect = async () => {
    if (!directTarget) return
    setDirectLoading(true)
    try {
      const palletId = Number(directTarget.reel_id)
      const res = await directOutboundApi(palletId, {
        operator: 'web',
        release_slot: true,
      })
      message.success(res.data?.message || `盘 #${palletId} 出库成功`)
      setDirectModalVisible(false)
      setDirectTarget(null)
      fetchData() // refresh
    } catch (err: any) {
      message.error(err.response?.data?.detail || '直接出库失败')
    } finally {
      setDirectLoading(false)
    }
  }

  const columns = [
    { title: '库存盘号', dataIndex: 'reel_code', key: 'reel_code', width: 180 },
    { title: '物料编号', dataIndex: 'material_code', key: 'material_code', width: 140 },
    { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 70 },
    {
      title: '客户',
      key: 'customer',
      width: 140,
      render: (_: any, record: InventoryItem) =>
        record.customer_name ? `${record.customer_name}${record.customer_code ? ` (${record.customer_code})` : ''}` : '-',
    },
    { title: '入库时间', dataIndex: 'first_in_time', key: 'first_in_time', width: 155 },
    {
      title: '储位',
      dataIndex: 'shelf_slot_id',
      key: 'shelf_slot_id',
      width: 80,
      render: (val: any) => (val ? `Slot #${val}` : '-'),
    },
    {
      title: '状态',
      key: 'status',
      width: 90,
      render: (_: any, record: InventoryItem) => (
        <Tag color={statusColors[record.status] || 'default'}>
          {statusLabels[record.status] || record.status}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 110,
      render: (_: any, record: InventoryItem) =>
        record.status !== 'exhausted' ? (
          <Button
            type="link"
            size="small"
            icon={<ExportOutlined />}
            onClick={() => handleOpenDirect(record)}
          >
            出库
          </Button>
        ) : (
          <Tag color="default">已耗尽</Tag>
        ),
    },
  ]

  return (
    <Spin spinning={loading}>
      <div>
        <div style={{ marginBottom: 16 }}>
          <h2>库存管理</h2>
        </div>
        <Space style={{ marginBottom: 16 }} wrap>
          <Input
            placeholder="搜索物料编号或库存盘号"
            prefix={<SearchOutlined />}
            style={{ width: 280 }}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            allowClear
          />
          <Select
            mode="multiple"
            placeholder="筛选客户（可多选）"
            style={{ minWidth: 200, maxWidth: 320 }}
            value={selectedCustomers}
            onChange={(vals) => setSelectedCustomers(vals)}
            allowClear
            maxTagCount={2}
          >
            {customers.map(c => (
              <Option key={c.id} value={c.id}>{c.name} ({c.code})</Option>
            ))}
          </Select>
          <Select
            mode="multiple"
            placeholder="筛选状态（可多选）"
            style={{ minWidth: 180, maxWidth: 300 }}
            value={selectedStatuses}
            onChange={(vals) => setSelectedStatuses(vals)}
            allowClear
            maxTagCount={2}
          >
            {allStatusOptions.map(opt => (
              <Option key={opt.value} value={opt.value}>{opt.label}</Option>
            ))}
          </Select>
          <Button icon={<ExportOutlined />} loading={exporting} onClick={handleExport}>
            导出Excel
          </Button>
        </Space>
        <Table
          columns={columns}
          dataSource={data}
          rowKey={(record) => String(record.reel_id)}
          pagination={{ pageSize: 20, total }}
        />

        {/* ── Direct Outbound Confirmation Modal (whole-reel mode) ── */}
        <Modal
          title={
            <Space>
              <ExportOutlined />
              直接出库确认
            </Space>
          }
          open={directModalVisible}
          onOk={handleConfirmDirect}
          onCancel={() => {
            setDirectModalVisible(false)
            setDirectTarget(null)
          }}
          okText="确认出库（整盘）"
          cancelText="取消"
          confirmLoading={directLoading}
          okButtonProps={{ danger: true }}
        >
          {directTarget && (
            <div style={{ padding: '8px 0' }}>
              <p><strong>盘号：</strong>{directTarget.reel_code}</p>
              <p><strong>物料：</strong>{directTarget.material_code}</p>
              <p><strong>数量：</strong>{directTarget.quantity}</p>
              <p style={{ color: '#faad14', marginTop: 16 }}>
                ⚠️ 出库将以整盘为单位，该盘将被标记为<strong>已耗尽</strong>，储位将释放。
              </p>
            </div>
          )}
        </Modal>
      </div>
    </Spin>
  )
}
