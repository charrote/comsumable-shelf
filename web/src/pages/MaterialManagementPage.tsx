import { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, Space, Tag, Popconfirm, Spin, message } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { getMaterialsApi, createMaterialApi, updateMaterialApi, deleteMaterialApi } from '../api'

export function MaterialManagementPage() {
  const [dataList, setDataList] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingRecord, setEditingRecord] = useState<any | null>(null)
  const [form] = Form.useForm()

  const loadData = async (keyword?: string) => {
    setLoading(true)
    try {
      const res = await getMaterialsApi(keyword ? { keyword } : {})
      setDataList(res.data?.data || res.data || [])
    } catch {
      message.error('加载物料数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const openCreateModal = () => {
    setEditingRecord(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEditModal = (record: any) => {
    setEditingRecord(record)
    form.setFieldsValue(record)
    setModalOpen(true)
  }

  const handleSave = async (values: any) => {
    try {
      if (editingRecord) {
        await updateMaterialApi(editingRecord.id, values)
        message.success('物料更新成功')
      } else {
        await createMaterialApi(values)
        message.success('物料创建成功')
      }
      setModalOpen(false)
      form.resetFields()
      loadData()
    } catch {
      message.error(editingRecord ? '更新物料失败' : '创建物料失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteMaterialApi(id)
      message.success('物料已禁用')
      loadData()
    } catch {
      message.error('禁用物料失败')
    }
  }

  const columns = [
    { title: '编号', dataIndex: 'code', key: 'code', width: 120 },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '规格', dataIndex: 'spec', key: 'spec', width: 200 },
    { title: '单位', dataIndex: 'unit', key: 'unit', width: 60 },
    { title: '每盘数量', dataIndex: 'qty_per_pallet', key: 'qty_per_pallet', width: 100 },
    { title: '库存', dataIndex: 'stock_balance', key: 'stock_balance', width: 100 },
    {
      title: '状态',
      dataIndex: 'active',
      key: 'active',
      width: 80,
      render: (active: boolean) =>
        active !== false ? <Tag color="green">启用</Tag> : <Tag color="red">禁用</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={() => openEditModal(record)} />
          <Popconfirm
            title="确认禁用该物料？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>物料主数据管理</h2>
        <Space>
          <Input.Search
            placeholder="搜索物料编号/名称"
            allowClear
            onSearch={(value) => loadData(value || undefined)}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
            新建物料
          </Button>
        </Space>
      </div>
      <Spin spinning={loading}>
        <Table
          columns={columns}
          dataSource={dataList}
          pagination={{ pageSize: 10 }}
          rowKey="code"
        />
      </Spin>
      <Modal
        title={editingRecord ? '编辑物料' : '新建物料'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); form.resetFields() }}
        footer={null}
      >
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="code" label="物料编号" rules={[{ required: true }]}>
            <Input placeholder="输入物料编号" />
          </Form.Item>
          <Form.Item name="name" label="物料名称" rules={[{ required: true }]}>
            <Input placeholder="输入物料名称" />
          </Form.Item>
          <Form.Item name="spec" label="规格型号">
            <Input placeholder="输入规格型号" />
          </Form.Item>
          <Form.Item name="unit" label="单位">
            <Input placeholder="如 盘、卷" />
          </Form.Item>
          <Form.Item name="qty_per_pallet" label="每盘数量">
            <Input type="number" placeholder="每盘数量" />
          </Form.Item>
          <Form.Item name="barcode_pattern" label="条码规则">
            <Input placeholder="正则表达式匹配条码" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">保存</Button>
              <Button onClick={() => { setModalOpen(false); form.resetFields() }}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
