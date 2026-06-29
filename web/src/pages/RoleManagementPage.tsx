import { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, Space, Tag, Popconfirm, Spin, message, Descriptions } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { getRolesApi, getRoleApi, createRoleApi, updateRoleApi, deleteRoleApi } from '../api'
import { useAuthStore } from '../store/authStore'
import { RolePermissionPage } from './RolePermissionPage'

export function RoleManagementPage() {
  const [roles, setRoles] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [detailOpen, setDetailOpen] = useState(false)
  const [permOpen, setPermOpen] = useState(false)
  const [selectedRole, setSelectedRole] = useState<any>(null)
  const [editingRole, setEditingRole] = useState<any>(null)
  const [roleDetail, setRoleDetail] = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()
  const hasPerm = useAuthStore((s) => s.hasPermission)

  const loadRoles = async () => {
    setLoading(true)
    try {
      const res = await getRolesApi()
      setRoles(Array.isArray(res.data) ? res.data : [])
    } catch (err: any) {
      message.error(err.response?.data?.detail || '加载角色失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadRoles()
  }, [])

  const openCreate = () => {
    setEditingRole(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = async (role: any) => {
    setEditingRole(role)
    form.setFieldsValue({
      name: role.name,
      code: role.code,
      description: role.description,
    })
    setModalOpen(true)
  }

  const openDetail = async (role: any) => {
    setSelectedRole(role)
    try {
      const res = await getRoleApi(role.id)
      setRoleDetail(res.data)
      setDetailOpen(true)
    } catch (err: any) {
      message.error('加载角色详情失败')
    }
  }

  const openPermissions = (role: any) => {
    setSelectedRole(role)
    setPermOpen(true)
  }

  const handleSubmit = async (values: any) => {
    setSaving(true)
    try {
      if (editingRole) {
        await updateRoleApi(editingRole.id, values)
        message.success('角色已更新')
      } else {
        await createRoleApi(values)
        message.success('角色已创建')
      }
      setModalOpen(false)
      form.resetFields()
      await loadRoles()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '操作失败')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteRoleApi(id)
      message.success('角色已禁用')
      await loadRoles()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '操作失败')
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '角色名称', dataIndex: 'name', key: 'name' },
    { title: '角色编码', dataIndex: 'code', key: 'code', width: 120 },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: '权限数',
      dataIndex: 'permission_count',
      key: 'permission_count',
      width: 80,
      align: 'center' as const,
    },
    {
      title: '用户数',
      dataIndex: 'user_count',
      key: 'user_count',
      width: 80,
      align: 'center' as const,
    },
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
      title: '类型',
      key: 'is_system',
      width: 80,
      render: (_: any, record: any) =>
        record.is_system ? <Tag color="blue">系统</Tag> : <Tag>自定义</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" size="small" onClick={() => openDetail(record)}>
            详情
          </Button>
          {hasPerm('role:update') && (
            <Button
              type="link"
              size="small"
              icon={<SafetyCertificateOutlined />}
              onClick={() => openPermissions(record)}
            >
              权限
            </Button>
          )}
          {hasPerm('role:update') && !record.is_system && (
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => openEdit(record)}
            />
          )}
          {hasPerm('role:delete') && !record.is_system && (
            <Popconfirm
              title="确认禁用该角色？"
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
        <h2>角色管理</h2>
        {hasPerm('role:create') && (
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建角色
          </Button>
        )}
      </div>
      <Spin spinning={loading}>
        <Table
          columns={columns}
          dataSource={roles}
          pagination={false}
          rowKey="id"
        />
      </Spin>

      {/* Create/Edit Modal */}
      <Modal
        title={editingRole ? '编辑角色' : '新建角色'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        width={500}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="name" label="角色名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item
            name="code"
            label="角色编码"
            rules={[{ required: true }, { pattern: /^[a-z_-]+$/, message: '仅支持小写字母、下划线和横线' }]}
          >
            <Input disabled={!!editingRole} placeholder="如: custom_role" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={saving}>
                {editingRole ? '保存修改' : '创建'}
              </Button>
              <Button onClick={() => setModalOpen(false)}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Detail Modal */}
      <Modal
        title={`角色详情 - ${roleDetail?.name || ''}`}
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={null}
        width={600}
      >
        {roleDetail && (
          <div>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="角色名称">{roleDetail.name}</Descriptions.Item>
              <Descriptions.Item label="角色编码">{roleDetail.code}</Descriptions.Item>
              <Descriptions.Item label="描述" span={2}>
                {roleDetail.description || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="类型">
                {roleDetail.is_system ? '系统内置' : '自定义'}
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={roleDetail.active ? 'green' : 'red'}>
                  {roleDetail.active ? '启用' : '禁用'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="用户数">{roleDetail.user_count}</Descriptions.Item>
              <Descriptions.Item label="权限数">{roleDetail.permissions?.length || 0}</Descriptions.Item>
            </Descriptions>
            <div style={{ marginTop: 16 }}>
              <strong>权限列表：</strong>
              <div style={{ marginTop: 8 }}>
                {roleDetail.permissions?.length > 0 ? (
                  roleDetail.permissions.map((perm: string) => (
                    <Tag key={perm} style={{ marginBottom: 4 }}>{perm}</Tag>
                  ))
                ) : (
                  <span style={{ color: '#999' }}>暂无权限</span>
                )}
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* Permission Assignment Modal */}
      {selectedRole && (
        <RolePermissionPage
          role={selectedRole}
          open={permOpen}
          onClose={() => {
            setPermOpen(false)
            loadRoles()
          }}
        />
      )}
    </div>
  )
}
