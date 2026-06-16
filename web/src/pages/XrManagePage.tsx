import { Table, Button, Space, Tag, Card, Input, Form } from 'antd'
import { UploadOutlined } from '@ant-design/icons'

const columns = [
  { title: '批次号', dataIndex: 'batch_id', key: 'batch_id', width: 100 },
  { title: '物料', dataIndex: 'material_code', key: 'material_code' },
  { title: '盘数', dataIndex: 'counted_qty', key: 'counted_qty', width: 80 },
  { title: '扫描时间', dataIndex: 'scanned_at', key: 'scanned_at', width: 160 },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    width: 100,
    render: (text: string) => {
      const colors: Record<string, string> = {
        pending_match: 'orange',
        matched: 'green',
        failed: 'red',
      }
      return <Tag color={colors[text]}>{text}</Tag>
    },
  },
]

const mockData = [
  { key: '1', batch_id: 'XR-001', material_code: '4500067189', counted_qty: 47, scanned_at: '2024-01-15 09:00', status: 'matched' },
  { key: '2', batch_id: 'XR-002', material_code: '2623381607', counted_qty: 8, scanned_at: '2024-01-15 09:05', status: 'pending_match' },
]

export function XrManagePage() {
  return (
    <div>
      <h2>点料机管理</h2>

      <Card title="点料机数据上报" style={{ marginBottom: 16 }}>
        <Form layout="inline">
          <Form.Item label="盘号" name="reel_id">
            <Input placeholder="扫码枪扫描盘号" style={{ width: 250 }} />
          </Form.Item>
          <Form.Item label="数量" name="qty">
            <Input style={{ width: 100 }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" icon={<UploadOutlined />}>上传</Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="点料记录">
        <Table
          columns={columns}
          dataSource={mockData}
          pagination={false}
          rowKey="key"
        />
      </Card>
    </div>
  )
}
