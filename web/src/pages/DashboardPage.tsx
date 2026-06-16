import { Card, Col, Row, Statistic, Table, Tag } from 'antd'
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  WarehouseOutlined,
  InventoryOutlined,
} from '@ant-design/icons'

const { Meta } = Card

const dashboardData = {
  totalMaterials: 128,
  totalShelves: 12,
  onShelfPallets: 456,
  trackingPallets: 23,
  pendingReceipts: 5,
  pendingIssues: 3,
}

const recentTransactions = [
  { key: '1', time: '2024-01-15 09:30', type: '入库', material: '4500067189', quantity: 50, status: '成功' },
  { key: '2', time: '2024-01-15 09:25', type: '发料', material: '4500067189', quantity: 3, status: '成功' },
  { key: '3', time: '2024-01-15 09:20', type: '入库', material: '2623381607', quantity: 50, status: '成功' },
]

export function DashboardPage() {
  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="物料总数"
              value={dashboardData.totalMaterials}
              prefix={<InventoryOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="料架总数"
              value={dashboardData.totalShelves}
              prefix={<WarehouseOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="在架库存盘"
              value={dashboardData.onShelfPallets}
              suffix="盘"
              prefix={<ArrowUpOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="跟踪中"
              value={dashboardData.trackingPallets}
              suffix="盘"
              prefix={<ArrowDownOutlined />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Card title="最近操作记录">
            <Table
              dataSource={recentTransactions}
              columns={[
                { title: '时间', dataIndex: 'time', key: 'time' },
                { title: '类型', dataIndex: 'type', key: 'type' },
                { title: '物料', dataIndex: 'material', key: 'material' },
                { title: '数量', dataIndex: 'quantity', key: 'quantity' },
                {
                  title: '状态',
                  dataIndex: 'status',
                  key: 'status',
                  render: (text: string) => (
                    <Tag color={text === '成功' ? 'green' : 'red'}>{text}</Tag>
                  ),
                },
              ]}
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="待处理事项">
            <div>
              <p>📋 待确认入库: {dashboardData.pendingReceipts} 单</p>
              <p>📦 待执行发料: {dashboardData.pendingIssues} 单</p>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
