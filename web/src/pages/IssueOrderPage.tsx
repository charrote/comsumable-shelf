import { useState } from 'react'
import { Table, Button, Space, Tag, Modal, Form, Input, Select, DatePicker } from 'antd'
import { PlusOutlined } from '@ant-design/icons'

const { Option } = Select

const columns = [
  { title: '发料单号', dataIndex: 'order_no', key: 'order_no' },
  { title: 'BOM', dataIndex: 'bom_name', key: 'bom_name' },
  { title: '物料数', dataIndex: 'total_materials', key: 'total_materials', width: 80 },
  { title: '需求日期', dataIndex: 'required_date', key: 'required_date', width: 120 },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (_, record: any) => {
      const colors: Record<string, string> = {
        pending: 'default',
        calculating: 'processing',
        assigned: 'blue',
        completed: 'green',
      }
      return <Tag color={colors[record.status]}>{record.status}</Tag>
    },
  },
]

const mockData = [
  { key: '1', order_no: 'IS-20240115-001', bom_name: '主板 V2', total_materials: 8, required_date: '2024-01-16', status: 'pending' },
  { key: '2', order_no: 'IS-20240115-002', bom_name: '副板 V3', total_materials: 5, required_date: '2024-01-17', status: 'assigned' },
]

export function IssueOrderPage() {
  const [createModal, setCreateModal] = useState(false)

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>发料管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModal(true)}>
          新建发料单
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={mockData}
        pagination={false}
        rowKey="order_no"
      />
      <Modal title="新建发料单" open={createModal} onCancel={() => setCreateModal(false)} footer={null}>
        <Form layout="vertical">
          <Form.Item name="bom_header_id" label="选择 BOM">
            <Select placeholder="选择 BOM 文件">
              <Option value="1">主板 V2</Option>
              <Option value="2">副板 V3</Option>
            </Select>
          </Form.Item>
          <Form.Item name="required_date" label="需求日期">
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary">创建</Button>
              <Button onClick={() => setCreateModal(false)}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
