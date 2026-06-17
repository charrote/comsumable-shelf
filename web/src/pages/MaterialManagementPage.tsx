import { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, Space, Tag, Popconfirm, Spin, message, Tabs, Select } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, LinkOutlined } from '@ant-design/icons'
import {
  getMaterialsApi, createMaterialApi, updateMaterialApi, deleteMaterialApi,
  getMappingsApi, createMappingApi, updateMappingApi, deleteMappingApi,
} from '../api'

const { Option } = Select

export function MaterialManagementPage() {
  // ── Materials state ──
  const [dataList, setDataList] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingRecord, setEditingRecord] = useState<any | null>(null)
  const [form] = Form.useForm()

  // ── Mappings state ──
  const [mappings, setMappings] = useState<any[]>([])
  const [mappingLoading, setMappingLoading] = useState(false)
  const [mappingModalOpen, setMappingModalOpen] = useState(false)
  const [editingMapping, setEditingMapping] = useState<any | null>(null)
  const [mappingForm] = Form.useForm()
  const [materialOptions, setMaterialOptions] = useState<any[]>([])

  // ── Load materials ──
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

  // ── Load mappings ──
  const loadMappings = async () => {
    setMappingLoading(true)
    try {
      const res = await getMappingsApi()
      setMappings(res.data || [])
    } catch {
      message.error('加载映射数据失败')
    } finally {
      setMappingLoading(false)
    }
  }

  const loadMaterialOptions = async () => {
    try {
      const res = await getMaterialsApi({})
      setMaterialOptions(res.data?.data || res.data || [])
    } catch {
      // ignore
    }
  }

  // ── Material CRUD ──
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

  // ── Mapping CRUD ──
  const openCreateMapping = () => {
    setEditingMapping(null)
    mappingForm.resetFields()
    loadMaterialOptions()
    setMappingModalOpen(true)
  }

  const openEditMapping = (record: any) => {
    setEditingMapping(record)
    mappingForm.setFieldsValue({
      customer_id: record.customer_id,
      customer_material_code: record.customer_material_code,
      internal_material_id: record.internal_material_id,
    })
    loadMaterialOptions()
    setMappingModalOpen(true)
  }

  const handleSaveMapping = async (values: any) => {
    try {
      if (editingMapping) {
        await updateMappingApi(editingMapping.id, values)
        message.success('映射更新成功')
      } else {
        await createMappingApi(values)
        message.success('映射创建成功')
      }
      setMappingModalOpen(false)
      mappingForm.resetFields()
      loadMappings()
    } catch (err: any) {
      message.error(err?.response?.data?.detail || (editingMapping ? '更新映射失败' : '创建映射失败'))
    }
  }

  const handleDeleteMapping = async (id: number) => {
    try {
      await deleteMappingApi(id)
      message.success('映射已禁用')
      loadMappings()
    } catch {
      message.error('禁用映射失败')
    }
  }

  // ── Material table columns ──
  const materialColumns = [
    { title: '编号', dataIndex: 'code', key: 'code', width: 120 },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '规格', dataIndex: 'spec', key: 'spec', width: 200 },
    { title: '单位', dataIndex: 'unit', key: 'unit', width: 60 },
    { title: '每盘数量', dataIndex: 'qty_per_pallet', key: 'qty_per_pallet', width: 100 },
    { title: '库存', dataIndex: 'stock_balance', key: 'stock_balance', width: 100 },
    {
      title: '状态', dataIndex: 'active', key: 'active', width: 80,
      render: (active: boolean) =>
        active !== false ? <Tag color="green">启用</Tag> : <Tag color="red">禁用</Tag>,
    },
    {
      title: '操作', key: 'action', width: 120,
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={() => openEditModal(record)} />
          <Popconfirm title="确认禁用该物料？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  // ── Mapping table columns ──
  const mappingColumns = [
    { title: '客户', dataIndex: 'customer_name', key: 'customer_name', width: 120 },
    { title: '客户料号', dataIndex: 'customer_material_code', key: 'customer_material_code', width: 160 },
    { title: '内部料号', dataIndex: 'internal_material_code', key: 'internal_material_code', width: 120 },
    { title: '物料名称', dataIndex: 'internal_material_name', key: 'internal_material_name' },
    {
      title: '状态', dataIndex: 'active', key: 'active', width: 80,
      render: (active: number) =>
        active === 1 ? <Tag color="green">启用</Tag> : <Tag color="red">禁用</Tag>,
    },
    {
      title: '操作', key: 'action', width: 120,
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={() => openEditMapping(record)} />
          <Popconfirm title="确认禁用该映射？" onConfirm={() => handleDeleteMapping(record.id)}>
            <Button type="link" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const tabItems = [
    {
      key: 'materials',
      label: '物料管理',
      children: (
        <>
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
            <Table columns={materialColumns} dataSource={dataList} pagination={{ pageSize: 10 }} rowKey="code" />
          </Spin>
        </>
      ),
    },
    {
      key: 'mappings',
      label: '客户料号映射',
      children: (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
            <h2>客户料号映射表</h2>
            <Space>
              <Button type="primary" icon={<LinkOutlined />} onClick={openCreateMapping}>
                新建映射
              </Button>
            </Space>
          </div>
          <Spin spinning={mappingLoading}>
            <Table columns={mappingColumns} dataSource={mappings} pagination={{ pageSize: 10 }} rowKey="id" />
          </Spin>
        </>
      ),
    },
  ]

  return (
    <div>
      <Tabs defaultActiveKey="materials" items={tabItems} onTabClick={(key) => { if (key === 'mappings') loadMappings() }} />

      {/* ── Material Modal ── */}
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

      {/* ── Mapping Modal ── */}
      <Modal
        title={editingMapping ? '编辑映射' : '新建映射'}
        open={mappingModalOpen}
        onCancel={() => { setMappingModalOpen(false); mappingForm.resetFields() }}
        footer={null}
      >
        <Form form={mappingForm} layout="vertical" onFinish={handleSaveMapping}>
          <Form.Item name="customer_id" label="客户 ID" rules={[{ required: true }]}>
            <Input type="number" placeholder="客户 ID" />
          </Form.Item>
          <Form.Item name="customer_material_code" label="客户料号" rules={[{ required: true, message: '请输入客户料号' }]}>
            <Input placeholder="客户标签上的物料编码" />
          </Form.Item>
          <Form.Item name="internal_material_id" label="内部物料" rules={[{ required: true, message: '请选择内部物料' }]}>
            <Select
              showSearch
              placeholder="搜索并选择物料"
              optionFilterProp="label"
              loading={materialOptions.length === 0}
              onFocus={loadMaterialOptions}
            >
              {materialOptions.map((m: any) => (
                <Option key={m.id} value={m.id} label={`${m.code} ${m.name}`}>
                  {m.code} — {m.name}
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">保存</Button>
              <Button onClick={() => { setMappingModalOpen(false); mappingForm.resetFields() }}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
