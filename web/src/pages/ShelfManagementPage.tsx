import { useState } from 'react'
import { Table, Button, Modal, Form, Input, Space, Tag, Switch } from 'antd'
import { PlusOutlined, SyncOutlined } from '@ant-design/icons'

const columns = [
  { title: '料架编号', dataIndex: 'code', key: 'code', width: 120 },
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: 'A 面板', dataIndex: 'a_sides', key: 'a_sides', width: 80 },
  { title: 'B 面版', dataIndex: 'b_sides', key: 'b_sides', width: 80 },
  { title: '总槽位', dataIndex: 'total_slots', key: 'total_slots', width: 80 },
  { title: '控制器 IP', dataIndex: 'controller_ip', key: 'controller_ip', width: 150 },
  { title: '位置', dataIndex: 'location', key: 'location', width: 150 },
  {
    title: '状态',
    key: 'active',
    width: 80,
    render: () => <Tag color="green">在线</Tag>,
  },
]

const mockData = [
  {
    key: '1', code: 'SH-001', name: 'SMT 主料架 A', a_sides: 1, b_sides: 1,
    total_slots: 256, controller_ip: '192.168.1.100', location: '产线 1 号',
  },
  {
    key: '2', code: 'SH-002', name: 'SMT 主料架 B', a_sides: 1, b_sides: 1,
    total_slots: 256, controller_ip: '192.168.1.101', location: '产线 2 号',
  },
]

export function ShelfManagementPage() {
  const [modalOpen, setModalOpen] = useState(false)

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>料架管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新建料架
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={mockData}
        pagination={false}
        rowKey="code"
      />
      <Modal
        title="新建料架"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
      >
        <Form layout="vertical">
          <Form.Item name="code" label="料架编号" rules={[{ required: true }]}>
            <Input placeholder="如 SH-001" />
          </Form.Item>
          <Form.Item name="name" label="料架名称">
            <Input placeholder="如 SMT 主料架 A" />
          </Form.Item>
          <Form.Item name="a_sides" label="A 面 LED 面板数">
            <Input type="number" defaultValue={1} />
          </Form.Item>
          <Form.Item name="b_sides" label="B 面 LED 面板数">
            <Input type="number" defaultValue={1} />
          </Form.Item>
          <Form.Item name="controller_ip" label="控制器 IP">
            <Input placeholder="如 192.168.1.100" />
          </Form.Item>
          <Form.Item name="location" label="安装位置">
            <Input placeholder="如 产线 1 号" />
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
