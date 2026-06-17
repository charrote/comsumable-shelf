import { useState, useEffect, useCallback } from 'react'
import { Table, Input, Space, Tag, Select, Spin, message } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { getInventoryApi } from '../api'

const { Option } = Select

interface InventoryItem {
  pallet_id: number | string
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

export function InventoryPage() {
  const [data, setData] = useState<InventoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState<string | undefined>(undefined)
  const [total, setTotal] = useState(0)

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

  const columns = [
    { title: '库存盘号', dataIndex: 'pallet_id', key: 'pallet_id', width: 120 },
    { title: '物料编号', dataIndex: 'material_code', key: 'material_code' },
    { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 80 },
    { title: '入库时间', dataIndex: 'first_in_time', key: 'first_in_time', width: 160 },
    {
      title: '储位',
      dataIndex: 'shelf_slot_id',
      key: 'shelf_slot_id',
      width: 100,
    },
    {
      title: '状态',
      key: 'status',
      width: 100,
      render: (_: any, record: InventoryItem) => (
        <Tag color={statusColors[record.status] || 'default'}>{record.status}</Tag>
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
          rowKey={(record) => String(record.pallet_id)}
          pagination={{ pageSize: 20, total }}
        />
      </div>
    </Spin>
  )
}
