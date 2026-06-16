import { useState } from 'react'
import { Card, DatePicker, Button, Table, Space, Input, Statistic } from 'antd'
import { SearchOutlined } from '@ant-design/icons'

const { RangePicker } = DatePicker

const columns = [
  { title: '物料', dataIndex: 'material_code', key: 'material_code' },
  { title: '库存', dataIndex: 'stock_balance', key: 'stock_balance', width: 100 },
  { title: '入库', dataIndex: 'in_qty', key: 'in_qty', width: 100 },
  { title: '出库', dataIndex: 'out_qty', key: 'out_qty', width: 100 },
  { title: '尾数盘', dataIndex: 'tail_pallets', key: 'tail_pallets', width: 100 },
]

const mockData = [
  { key: '1', material_code: '4500067189', stock_balance: 45000, in_qty: 50, out_qty: 3, tail_pallets: 8 },
  { key: '2', material_code: '2623381607', stock_balance: 32000, in_qty: 50, out_qty: 5, tail_pallets: 5 },
]

export function ReportPage() {
  const [range, setRange] = useState<[any, any] | null>(null)

  return (
    <div>
      <h2>报表统计</h2>
      <Card style={{ marginBottom: 16 }}>
        <Space>
          <RangePicker onChange={setRange} />
          <Button icon={<SearchOutlined />}>查询</Button>
        </Space>
      </Card>
      <Space style={{ marginBottom: 16 }} wrap>
        <Card>
          <Statistic title="物料总数" value={128} />
        </Card>
        <Card>
          <Statistic title="今日入库" value={3} />
        </Card>
        <Card>
          <Statistic title="今日出库" value={2} />
        </Card>
        <Card>
          <Statistic title="尾数盘" value={13} />
        </Card>
      </Space>
      <Table
        columns={columns}
        dataSource={mockData}
        pagination={false}
        rowKey="key"
      />
    </div>
  )
}
