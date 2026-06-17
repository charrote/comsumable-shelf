import { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, Select, Space, Tag, Popconfirm, Spin, message } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { getUsersApi, createUserApi, deleteUserApi } from '../api'

const { Option } = Select

const roleColorMap: Record<string, string> = {
  admin: 'red',
  supervisor: 'blue',
  operator: 'green',
}

const roleLabelMap: Record<string, string> = {
  admin: '管理员',
  supervisor: '主管',
  operator: '操作员',
}

export function UserManagementPage() {
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()

  const loadUsers = async () => {
    setLoading(true)
    try {
      const res = await getUsersApi({})
      const data = res.data
      setUsers(Array.isArray(data) ? data : data.users || [])
    } catch (err: any) {
      message.error(err.response?.data?.detail || '加载用户失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadUsers()
  }, [])

  const handleCreate = async (values: any) => {
    setSaving(true)
    try {
      await createUserApi(values)
      message.success('创建成功')
      setModalOpen(false)
      form.resetFields()
      await loadUsers()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '创建失败')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteUserApi(id)
      message.success('已禁用该用户')
      await loadUsers()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '操作失败')
    }
  }

  const columns = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      width: 120,
      render: (role: string) => (
        <Tag color={roleColorMap[role] || 'default'}>
          {roleLabelMap[role] || role}
        </Tag>
      ),
    },
    { title: '客户', dataIndex: 'customer_name', key: 'customer_name', width: 150 },
    {
      title: '状态',
      key: 'active',
      width: 80,
      render: (_: any, record: any) => (
        <Tag color={record.active === false ? 'red' : 'green'}>
          {record.active === false ? '禁用' : '启用'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: any, record: any) => (
        <Popconfirm
          title="确认禁用该用户？"
          onConfirm={() => handleDelete(record.id)}
        >
          <Button type="link" danger size="small" icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>用户管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新建用户
        </Button>
      </div>
      <Spin spinning={loading}>
        <Table
          columns={columns}
          dataSource={users}
          pagination={false}
          rowKey="id"
        />
      </Spin>
      <Modal title="新建用户" open={modalOpen} onCancel={() => setModalOpen(false)} footer={null}>
        <Form form={form} layout="vertical" onFinish={handleCreate}>
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
              <Button type="primary" htmlType="submit" loading={saving}>
                保存
              </Button>
              <Button onClick={() => setModalOpen(false)}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
