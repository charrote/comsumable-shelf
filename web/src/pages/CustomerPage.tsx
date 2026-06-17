import { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, Space, Popconfirm, message } from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons'
import { getCustomersApi, createCustomerApi, updateCustomerApi, deleteCustomerApi } from '../api'

export function CustomerPage() {
  const [customers, setCustomers] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()

  const loadCustomers = async () => {
    setLoading(true)
    try {
      const res = await getCustomersApi()
      setCustomers(Array.isArray(res.data) ? res.data : [])
    } catch (err: any) {
      message.error(err.response?.data?.detail || '加载客户失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCustomers()
  }, [])

  const handleCreate = async (values: any) => {
    setSaving(true)
    try {
      if (editId !== null) {
        await updateCustomerApi(editId, values)
        message.success('修改成功')
      } else {
        await createCustomerApi(values)
        message.success('创建成功')
      }
      setModalOpen(false)
      form.resetFields()
      setEditId(null)
      await loadCustomers()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '操作失败')
    } finally {
      setSaving(false)
    }
  }

  const handleEdit = (record: any) => {
    setEditId(record.id)
    form.setFieldsValue({
      name: record.name,
      code: record.code,
      contact_name: record.contact_name,
      contact_phone: record.contact_phone,
      address: record.address,
    })
    setModalOpen(true)
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteCustomerApi(id)
      message.success('删除成功')
      await loadCustomers()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '删除失败')
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '客户名称', dataIndex: 'name', key: 'name' },
    { title: '客户编码', dataIndex: 'code', key: 'code', width: 120 },
    { title: '联系人', dataIndex: 'contact_name', key: 'contact_name', width: 100 },
    { title: '联系电话', dataIndex: 'contact_phone', key: 'contact_phone', width: 140 },
    { title: '地址', dataIndex: 'address', key: 'address' },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: any) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Popconfirm
            title="确认删除该客户？"
            onConfirm={() => handleDelete(record.id)}
            okText="确认"
            cancelText="取消"
          >
            <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <h2>客户管理</h2>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditId(null); form.resetFields(); setModalOpen(true) }}>
          新建客户
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={customers}
        loading={loading}
        pagination={{ pageSize: 20 }}
        rowKey="id"
      />
      <Modal
        title={editId !== null ? '编辑客户' : '新建客户'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); form.resetFields(); setEditId(null) }}
        footer={null}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="客户名称" rules={[{ required: true, message: '请输入客户名称' }]}>
            <Input placeholder="请输入客户名称" />
          </Form.Item>
          <Form.Item name="code" label="客户编码" rules={[{ required: true, message: '请输入客户编码' }]}>
            <Input placeholder="请输入客户编码" />
          </Form.Item>
          <Form.Item name="contact_name" label="联系人">
            <Input placeholder="请输入联系人" />
          </Form.Item>
          <Form.Item name="contact_phone" label="联系电话">
            <Input placeholder="请输入联系电话" />
          </Form.Item>
          <Form.Item name="address" label="地址">
            <Input placeholder="请输入地址" />
          </Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={saving}>{editId !== null ? '保存' : '创建'}</Button>
            <Button onClick={() => { setModalOpen(false); form.resetFields(); setEditId(null) }}>取消</Button>
          </Space>
        </Form>
      </Modal>
    </div>
  )
}