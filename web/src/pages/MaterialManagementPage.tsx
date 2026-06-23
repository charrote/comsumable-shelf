import { useState, useEffect, useRef } from 'react'
import { Table, Button, Modal, Form, Input, Space, Tag, Popconfirm, Spin, message, Tabs, Select, Upload } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, LinkOutlined, UploadOutlined, DownloadOutlined, ExclamationCircleOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd'
import {
  getMaterialsApi, createMaterialApi, updateMaterialApi, deleteMaterialApi,
  getCustomersApi, getMappingsApi, createMappingApi, updateMappingApi, deleteMappingApi,
  uploadMaterialsApi, downloadMaterialTemplateApi,
  batchDeleteMaterialsApi, batchUpdateMaterialsApi,
} from '../api'

const { Option } = Select

export function MaterialManagementPage() {
  // ── Materials state ──
  const [dataList, setDataList] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingRecord, setEditingRecord] = useState<any | null>(null)
  const [form] = Form.useForm()

  // ── Upload state ──
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadFileList, setUploadFileList] = useState<UploadFile[]>([])
  const [uploadCustomerCode, setUploadCustomerCode] = useState<string | undefined>(undefined)

  // ── Mappings state ──
  const [mappings, setMappings] = useState<any[]>([])
  const [mappingLoading, setMappingLoading] = useState(false)
  const [mappingModalOpen, setMappingModalOpen] = useState(false)
  const [editingMapping, setEditingMapping] = useState<any | null>(null)
  const [mappingForm] = Form.useForm()
  const [materialOptions, setMaterialOptions] = useState<any[]>([])

  // ── Batch operation state ──
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [batchEditModalOpen, setBatchEditModalOpen] = useState(false)
  const [batchEditForm] = Form.useForm()

  // ── Customers ──
  const [customers, setCustomers] = useState<any[]>([])

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
    getCustomersApi().then(res => setCustomers(Array.isArray(res.data) ? res.data : [])).catch(() => {})
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

  const handleUpload = async () => {
    if (!uploadCustomerCode) {
      message.error('请选择客户')
      return
    }
    if (uploadFileList.length === 0) {
      message.error('请选择文件')
      return
    }
    setUploading(true)
    try {
      const res = await uploadMaterialsApi(uploadFileList[0].originFileObj as File, uploadCustomerCode)
      const d = res.data
      message.success(`导入完成：共 ${d.total} 条，新增 ${d.imported} 条，跳过 ${d.skipped} 条（重复），创建 ${d.categories_created} 个类别`)
      setUploadModalOpen(false)
      setUploadFileList([])
      loadData()
    } catch (e: any) {
      message.error('导入失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setUploading(false)
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

  // ── Batch operations ──
  const handleBatchDelete = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择要禁用的物料')
      return
    }
    Modal.confirm({
      title: '批量禁用物料',
      icon: <ExclamationCircleOutlined />,
      content: `确定要禁用选中的 ${selectedRowKeys.length} 个物料吗？`,
      onOk: async () => {
        try {
          await batchDeleteMaterialsApi(selectedRowKeys as number[])
          message.success(`已批量禁用 ${selectedRowKeys.length} 个物料`)
          setSelectedRowKeys([])
          loadData()
        } catch (e: any) {
          message.error('批量禁用失败: ' + (e.response?.data?.detail || e.message))
        }
      },
    })
  }

  const handleBatchEdit = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择要编辑的物料')
      return
    }
    batchEditForm.resetFields()
    setBatchEditModalOpen(true)
  }

  const handleBatchEditSave = async (values: any) => {
    try {
      const fields: any = {}
      if (values.name) fields.name = values.name
      if (values.spec) fields.spec = values.spec
      if (values.unit) fields.unit = values.unit
      if (values.category_id) fields.category_id = values.category_id
      if (Object.keys(fields).length === 0) {
        message.warning('请填写至少一个要更新的字段')
        return
      }
      await batchUpdateMaterialsApi(selectedRowKeys as number[], fields)
      message.success(`已批量更新 ${selectedRowKeys.length} 个物料`)
      setBatchEditModalOpen(false)
      setSelectedRowKeys([])
      loadData()
    } catch (e: any) {
      message.error('批量更新失败: ' + (e.response?.data?.detail || e.message))
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
    { title: '序号', key: 'index', width: 60, render: (_: any, __: any, index: number) => index + 1 },
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
              <Button icon={<DownloadOutlined />} onClick={downloadMaterialTemplateApi}>下载模板</Button>
              <Button icon={<UploadOutlined />} onClick={() => setUploadModalOpen(true)}>Excel导入</Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
                新建物料
              </Button>
            </Space>
          </div>
          <Spin spinning={loading}>
            {selectedRowKeys.length > 0 && (
              <div style={{ marginBottom: 8, padding: '8px 12px', background: '#e6f7ff', borderRadius: 4 }}>
                <Space>
                  <span>已选 {selectedRowKeys.length} 项</span>
                  <Button size="small" onClick={() => setSelectedRowKeys([])}>取消选择</Button>
                  <Button size="small" danger icon={<DeleteOutlined />} onClick={handleBatchDelete}>批量禁用</Button>
                  <Button size="small" icon={<EditOutlined />} onClick={handleBatchEdit}>批量编辑</Button>
                </Space>
              </div>
            )}
            <Table
              columns={materialColumns}
              dataSource={dataList}
              pagination={{ pageSize: 10 }}
              rowKey="code"
              rowSelection={{
                selectedRowKeys,
                onChange: setSelectedRowKeys,
              }}
            />
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

      {/* ── Upload Modal ── */}
      <Modal
        title="Excel导入物料主数据"
        open={uploadModalOpen}
        onCancel={() => { setUploadModalOpen(false); setUploadFileList([]) }}
        onOk={handleUpload}
        confirmLoading={uploading}
      >
        <Form layout="vertical">
          <Form.Item label="客户" required>
            <Select
              placeholder="选择客户"
              value={uploadCustomerCode}
              onChange={setUploadCustomerCode}
              options={customers.map(c => ({ value: c.code, label: `${c.name} (${c.code})` }))}
            />
          </Form.Item>
          <Form.Item label="Excel文件" required help="支持 .xls 和 .xlsx 格式，重复料号自动跳过">
            <Upload
              fileList={uploadFileList}
              beforeUpload={() => false}
              onChange={({ fileList }) => setUploadFileList(fileList)}
              maxCount={1}
              accept=".xlsx,.xls"
            >
              <Button icon={<UploadOutlined />}>选择文件</Button>
            </Upload>
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

      {/* ── Batch Edit Modal ── */}
      <Modal
        title={`批量编辑物料（${selectedRowKeys.length} 项）`}
        open={batchEditModalOpen}
        onCancel={() => { setBatchEditModalOpen(false); batchEditForm.resetFields() }}
        onOk={() => batchEditForm.submit()}
      >
        <Form form={batchEditForm} layout="vertical" onFinish={handleBatchEditSave}>
          <Form.Item name="name" label="物料名称">
            <Input placeholder="留空则不更新此项" />
          </Form.Item>
          <Form.Item name="spec" label="规格型号">
            <Input placeholder="留空则不更新此项" />
          </Form.Item>
          <Form.Item name="unit" label="单位">
            <Input placeholder="留空则不更新此项" />
          </Form.Item>
          <Form.Item name="category_id" label="类别ID">
            <Input type="number" placeholder="留空则不更新此项" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
