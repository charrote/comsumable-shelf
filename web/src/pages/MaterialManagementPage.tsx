import { useState } from 'react'
import { Table, Button, Modal, Form, Input, Space, Tag, Popconfirm } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'

const columns = [
  { title: '编号', dataIndex: 'code', key: 'code', width: 120 },
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '规格', dataIndex: 'spec', key: 'spec', width: 200 },
  { title: '单位', dataIndex: 'unit', key: 'unit', width: 60 },
  { title: '每盘数量', dataIndex: 'qty_per_pallet', key: 'qty_per_pallet', width: 100 },
  { title: '库存', dataIndex: 'stock_balance', key: 'stock_balance', width: 100 },
  { title: '状态', key: 'active', width: 80, render: () => <Tag color="green">启用</Tag> },
]

const mockData = [
  { key: '1', code: '4500067189', name: '电阻', spec: '0402 10K', unit: '盘', qty_per_pallet: 10000, stock_balance: 45000 },
  { key: '2', code: '2623381607', name: '电容', spec: '0402 100nF', unit: '盘', qty_per_pallet: 10000, stock_balance: 32000 },
  { key: '3', code: '1112325305', name: 'IC', spec: 'SOP-8', unit: '盘', qty_per_pallet: 250, stock_balance: 750 },
]

export function MaterialManagementPage() {
  const [modalOpen, setModalOpen] = useState(false)

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>物料主数据管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新建物料
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={mockData}
        pagination={{ pageSize: 10 }}
        rowKey="code"
      />
      <Modal
        title="新建物料"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
      >
        <Form layout="vertical">
          <Form.Item name="code" label="物料编号" rules={[{ required: true }]}>
            <Input placeholder="输入物料编号" />
          </Form.Item>
          <Form.Item name="name" label="物料名称" rules={[{ required: true }]}>
            <Input placeholder="输入物料名称" />
          </Form.Item>
          <Form.Item name="spec" label="规格型号">
            <Input placeholder="输入规格型号" />
          </Form.Item>
          <Form.Item name="qty_per_pallet" label="每盘数量">
            <Input type="number" placeholder="每盘数量" />
          </Form.Item>
          <Form.Item name="barcode_pattern" label="条码规则">
            <Input placeholder="正则表达式匹配条码" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary">保存</Button>
              <Button onClick={() => setModalOpen(false)}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
