import { useState, useEffect, useCallback } from 'react'
import { Table, Input, Space, Tag, Select, Spin, message, Button, Modal, Form, InputNumber } from 'antd'
import { SearchOutlined, ExportOutlined } from '@ant-design/icons'
import { getInventoryApi, directOutboundApi } from '../api'

const { Option } = Select

interface InventoryItem {
  reelId: number | string
  material_code: string
  quantity: number
  first_in_time: string
  shelf_slot_id: number | string
  status: string
}

const statusColors: Record<string, string> = {
  on_shelf: 'green',
  in_use: 'blue',
  tracking: 'orange',
  exhausted: 'red',
}

const statusLabels: Record<string, string> = {
  on_shelf: '在架',
  in_use: '使用中',
  tracking: '跟踪中',
  exhausted: '已耗尽',
}

export function InventoryPage() {
  const [data, setData] = useState<InventoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState<string | undefined>(undefined)
  const [total, setTotal] = useState(0)

  // ── Direct outbound modal ──
  const [directModalVisible, setDirectModalVisible] = useState(false)
  const [directTarget, setDirectTarget] = useState<InventoryItem | null>(null)
  const [directQty, setDirectQty] = useState<number>(1)
  const [directLoading, setDirectLoading] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (keyword) params.keyword = keyword
      if (status) params.status = status
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
  }, [keyword, status])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // ── Open direct outbound modal ──
  const handleOpenDirect = (item: InventoryItem) => {
    setDirectTarget(item)
    setDirectQty(item.quantity)
    setDirectModalVisible(true)
  }

  // ── Confirm direct outbound ──
  const handleConfirmDirect = async () => {
    if (!directTarget) return
    if (directQty <= 0 || directQty > directTarget.quantity) {
      message.warning(`出库数量须在 1 ~ ${directTarget.quantity} 之间`)
      return
    }
    setDirectLoading(true)
    try {
      const palletId = Number(directTarget.reelId)
      const res = await directOutboundApi(palletId, {
        quantity: directQty,
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
    { title: '库存盘号', dataIndex: 'reelId', key: 'reelId', width: 120 },
    { title: '物料编号', dataIndex: 'material_code', key: 'material_code' },
    { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 80 },
    { title: '入库时间', dataIndex: 'first_in_time', key: 'first_in_time', width: 160 },
    {
      title: '储位',
      dataIndex: 'shelf_slot_id',
      key: 'shelf_slot_id',
      width: 100,
      render: (val: any) => (val ? `Slot #${val}` : '-'),
    },
    {
      title: '状态',
      key: 'status',
      width: 100,
      render: (_: any, record: InventoryItem) => (
        <Tag color={statusColors[record.status] || 'default'}>
          {statusLabels[record.status] || record.status}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: InventoryItem) =>
        record.status !== 'exhausted' ? (
          <Button
            type="link"
            icon={<ExportOutlined />}
            onClick={() => handleOpenDirect(record)}
          >
            直接出库
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
            style={{ width: 300 }}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            allowClear
          />
          <Select
            placeholder="状态筛选"
            style={{ width: 120 }}
            value={status}
            onChange={(val) => setStatus(val)}
            allowClear
          >
            <Option value="on_shelf">在架</Option>
            <Option value="in_use">使用中</Option>
            <Option value="tracking">跟踪中</Option>
            <Option value="exhausted">已耗尽</Option>
          </Select>
        </Space>
        <Table
          columns={columns}
          dataSource={data}
          rowKey={(record) => String(record.reelId)}
          pagination={{ pageSize: 20, total }}
        />

        {/* ── Direct Outbound Confirmation Modal ── */}
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
          okText="确认出库"
          cancelText="取消"
          confirmLoading={directLoading}
          okButtonProps={{ danger: true }}
        >
          {directTarget && (
            <Form layout="vertical">
              <p>
                <strong>盘号：</strong>#{directTarget.reelId}
              </p>
              <p>
                <strong>物料：</strong>{directTarget.material_code}
              </p>
              <p>
                <strong>当前库存：</strong>{directTarget.quantity}
              </p>
              <Form.Item label="出库数量" required>
                <InputNumber
                  min={1}
                  max={directTarget.quantity}
                  value={directQty}
                  onChange={(val) => setDirectQty(val || 0)}
                  style={{ width: '100%' }}
                />
              </Form.Item>
              {directQty === directTarget.quantity && (
                <p style={{ color: '#faad14' }}>
                  出库数量等于库存，该盘将被标记为<strong>已耗尽</strong>，储位将释放。
                </p>
              )}
            </Form>
          )}
        </Modal>
      </div>
    </Spin>
  )
}
