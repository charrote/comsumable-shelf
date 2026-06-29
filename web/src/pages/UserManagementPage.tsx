import { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, Select, Space, Tag, Popconfirm, Spin, message } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, LockOutlined } from '@ant-design/icons'
import { getUsersApi, createUserApi, updateUserApi, deleteUserApi, getRolesApi } from '../api'
import { useAuthStore } from '../store/authStore'

const { Option } = Select

const roleColorMap: Record<string, string> = {
  admin: 'red',
  supervisor: 'blue',
  operator: 'green',
  readonly: 'orange',
}

const roleLabelMap: Record<string, string> = {
  admin: '管理员',
  supervisor: '主管',
  operator: '操作员',
  readonly: '只读用户',
}

export function UserManagementPage() {
  const [users, setUsers] = useState<any[]>([])
  const [roles, setRoles] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()
  const currentUser = useAuthStore((s) => s.user)
  const hasPerm = useAuthStore((s) => s.hasPermission)

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

  const loadRoles = async () => {
    try {
      const res = await getRolesApi()
      setRoles(Array.isArray(res.data) ? res.data : [])
    } catch {
      // Roles might not be loaded yet
    }
  }

  useEffect(() => {
    loadUsers()
    loadRoles()
  }, [])

  const openCreate = () => {
    setEditingUser(null)
    form.resetFields()
    form.setFieldsValue({ role: 'operator' })
    setModalOpen(true)
  }

  const openEdit = (user: any) => {
    setEditingUser(user)
    form.setFieldsValue({
      username: user.username,
      role: user.role,
      role_id: user.role_id,
      customer_name: user.customer_name,
    })
    setModalOpen(true)
  }

  const handleSubmit = async (values: any) => {
    setSaving(true)
    try {
      if (editingUser) {
        const updateData: any = {}
        if (values.username) updateData.username = values.username
        if (values.password) updateData.password = values.password
        if (values.role_id !== undefined) updateData.role_id = values.role_id
        if (values.role) updateData.role = values.role
        if (values.customer_name !== undefined) updateData.customer_name = values.customer_name
        await updateUserApi(editingUser.id, updateData)
        message.success('用户已更新')
      } else {
        await createUserApi(values)
        message.success('创建成功')
      }
      setModalOpen(false)
      form.resetFields()
      await loadUsers()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '操作失败')
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
      render: (_: string, record: any) => (
        <Tag color={roleColorMap[record.role] || 'default'}>
          {record.role_name || roleLabelMap[record.role] || record.role}
        </Tag>
      ),
    },
    { title: '客户', dataIndex: 'customer_name', key: 'customer_name', width: 150, render: (v: any) => v || '-' },
    {
      title: '状态',
      key: 'active',
      width: 80,
      render: (_: any, record: any) => (
        <Tag color={record.active === 0 ? 'red' : 'green'}>
          {record.active === 0 ? '禁用' : '启用'}
        </Tag>
      ),
    },
    {
      title: '最后登录',
      dataIndex: 'last_login_at',
      key: 'last_login_at',
      width: 170,
      render: (v: any) => v || '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: any, record: any) => (
        <Space>
          {hasPerm('user:update') && (
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => openEdit(record)}
            />
          )}
          {hasPerm('user:delete') && record.username !== currentUser?.username && record.role !== 'admin' && (
            <Popconfirm
              title="确认禁用该用户？"
              onConfirm={() => handleDelete(record.id)}
            >
              <Button type="link" danger size="small" icon={<DeleteOutlined />} />
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>用户管理</h2>
        {hasPerm('user:create') && (
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建用户
          </Button>
        )}
      </div>
      <Spin spinning={loading}>
        <Table
          columns={columns}
          dataSource={users}
          pagination={false}
          rowKey="id"
        />
      </Spin>

      <Modal
        title={editingUser ? '编辑用户' : '新建用户'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        width={500}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input disabled={editingUser && !hasPerm('user:update')} />
          </Form.Item>
          {!editingUser && (
            <Form.Item name="password" label="密码" rules={[{ required: true }]}>
              <Input.Password />
            </Form.Item>
          )}
          {editingUser && (
            <Form.Item name="password" label="新密码（留空不修改）">
              <Input.Password placeholder="留空则不修改密码" />
            </Form.Item>
          )}
          <Form.Item name="role_id" label="角色">
            <Select
              placeholder="选择角色"
              onChange={(value) => {
                // Also set the role string based on selection
                const selectedRole = roles.find((r) => r.id === value)
                if (selectedRole) {
                  form.setFieldsValue({ role: selectedRole.code })
                }
              }}
            >
              {roles.map((role: any) => (
                <Option key={role.id} value={role.id}>
                  {role.name} ({role.code})
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="customer_name" label="客户名称">
            <Input />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={saving}>
                {editingUser ? '保存修改' : '创建'}
              </Button>
              <Button onClick={() => setModalOpen(false)}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
