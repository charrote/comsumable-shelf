import { useState } from 'react'
import { Table, Button, Modal, Form, Input, Select, Space, Tag } from 'antd'
import { PlusOutlined } from '@ant-design/icons'

const { Option } = Select

const columns = [
  { title: '用户名', dataIndex: 'username', key: 'username' },
  { title: '角色', dataIndex: 'role', key: 'role', width: 120 },
  { title: '客户', dataIndex: 'customer_name', key: 'customer_name', width: 150 },
  {
    title: '状态',
    key: 'active',
    width: 80,
    render: () => <Tag color="green">启用</Tag>,
  },
]

const mockData = [
  { key: '1', username: 'admin', role: 'admin', customer_name: '全部' },
  { key: '2', username: 'operator1', role: 'operator', customer_name: '客户A' },
]

export function UserManagementPage() {
  const [modalOpen, setModalOpen] = useState(false)

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>用户管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新建用户
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={mockData}
        pagination={false}
        rowKey="key"
      />
      <Modal title="新建用户" open={modalOpen} onCancel={() => setModalOpen(false)} footer={null}>
        <Form layout="vertical">
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true }]}>
            <Select>
              <Option value="admin">管理员</Option>
              <Option value="supervisor">主管</Option>
              <Option value="operator">操作员</Option>
            </Select>
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
