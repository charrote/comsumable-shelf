import { useState, useEffect } from 'react'
import { Table, Button, Card, Upload, Tag, message, Select, Space, Modal, Form, Input, Popconfirm, Radio } from 'antd'
import { UploadOutlined, DownloadOutlined, PlusOutlined, DeleteOutlined, EditOutlined, ExportOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd'
import { useNavigate } from 'react-router-dom'
import {
  getBomListApi, uploadBomApi, downloadBomTemplateApi,
  uploadBomQixinApi, downloadBomQixinTemplateApi,
  getCustomersApi, getMaterialsApi, createBomApi, deleteBomApi, updateBomApi,
  exportBomApi,
} from '../api'

const statusMap: Record<string, { color: string; label: string }> = {
  draft: { color: 'default', label: '草稿' },
  active: { color: 'green', label: '生效' },
  obsolete: { color: 'red', label: '废弃' },
}

export function BOMPage() {
  const navigate = useNavigate()
  const [bomList, setBomList] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [customers, setCustomers] = useState<any[]>([])
  const [materials, setMaterials] = useState<any[]>([])
  const [selectedCustomer, setSelectedCustomer] = useState<number | undefined>(undefined)
  const [uploadModalVisible, setUploadModalVisible] = useState(false)
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [uploadCustomerCode, setUploadCustomerCode] = useState<string | undefined>(undefined)
  const [uploadVersion, setUploadVersion] = useState('1.0')
  const [uploadProductCode, setUploadProductCode] = useState('')
  const [uploadProductName, setUploadProductName] = useState('')
  const [templateType, setTemplateType] = useState<'standard' | 'qixin'>('standard')
  const [createForm] = Form.useForm()

  useEffect(() => {
    getCustomersApi().then(res => setCustomers(Array.isArray(res.data) ? res.data : [])).catch(() => {})
    getMaterialsApi({}).then(res => setMaterials(res.data?.data || res.data || [])).catch(() => {})
  }, [])

  useEffect(() => {
    fetchBomList()
  }, [selectedCustomer])

  const fetchBomList = async () => {
    setLoading(true)
    try {
      const params: any = {}
      if (selectedCustomer) params.customer_id = selectedCustomer
      const res = await getBomListApi(params)
      setBomList(res.data || [])
    } catch (e) {
      console.error('Failed to fetch BOM list:', e)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (values: any) => {
    try {
      await createBomApi({
        customer_id: values.customer_id,
        product_material_id: values.product_material_id,
        version: values.version || '1.0',
        description: values.description,
      })
      message.success('BOM创建成功')
      setCreateModalVisible(false)
      createForm.resetFields()
      fetchBomList()
    } catch (e: any) {
      message.error(e.response?.data?.detail || '创建失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteBomApi(id)
      message.success('BOM已删除')
      fetchBomList()
    } catch (e: any) {
      message.error(e.response?.data?.detail || '删除失败')
    }
  }

  const handleStatusChange = async (id: number, status: string) => {
    try {
      await updateBomApi(id, { status })
      message.success('状态已更新')
      fetchBomList()
    } catch (e: any) {
      message.error(e.response?.data?.detail || '更新失败')
    }
  }

  const handleUpload = async () => {
    if (!uploadCustomerCode) {
      message.error('请选择客户')
      return
    }
    if (fileList.length === 0) {
      message.error('请选择文件')
      return
    }
    setUploading(true)
    try {
      const uploadApi = templateType === 'qixin' ? uploadBomQixinApi : uploadBomApi
      const res = await uploadApi(
        fileList[0].originFileObj as File,
        uploadCustomerCode,
        uploadVersion,
        uploadProductCode || undefined,
        uploadProductName || undefined,
      )
      message.success(`BOM上传成功，共解析 ${res.data?.total_items || 0} 条明细`)
      setUploadModalVisible(false)
      setFileList([])
      setUploadProductCode('')
      setUploadProductName('')
      setUploading(false)
      fetchBomList()
    } catch (e: any) {
      message.error('BOM上传失败: ' + (e.response?.data?.detail || e.message))
      setUploading(false)
    }
  }

  const handleDownloadTemplate = () => {
    if (templateType === 'qixin') {
      downloadBomQixinTemplateApi()
      message.info('已下载七鑫格式BOM模板')
    } else {
      downloadBomTemplateApi()
      message.info('已下载标准BOM模板')
    }
  }

  const columns = [
    { title: '序号', key: 'index', width: 55, render: (_: any, __: any, index: number) => index + 1 },
    {
      title: '产品编码', dataIndex: 'product_code', key: 'product_code', width: 150,
    },
    {
      title: '产品名称', dataIndex: 'product_name', key: 'product_name', width: 200,
    },
    {
      title: '版本', dataIndex: 'version', key: 'version', width: 80,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (val: string) => {
        const s = statusMap[val] || { color: 'default', label: val }
        return <Tag color={s.color}>{s.label}</Tag>
      },
    },
    {
      title: '明细数', dataIndex: 'item_count', key: 'item_count', width: 80,
    },
    {
      title: '客户', dataIndex: 'customer_name', key: 'customer_name', width: 120,
    },
    {
      title: '描述', dataIndex: 'description', key: 'description', ellipsis: true,
    },
    {
      title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 170,
      render: (val: string) => val ? new Date(val).toLocaleString() : '-',
    },
    {
      title: '操作', key: 'action', width: 200,
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => navigate(`/bom/${record.id}`)}>
            编辑
          </Button>
          <Select
            size="small"
            value={record.status}
            style={{ width: 80 }}
            onChange={(v) => handleStatusChange(record.id, v)}
            options={[
              { value: 'draft', label: '草稿' },
              { value: 'active', label: '生效' },
              { value: 'obsolete', label: '废弃' },
            ]}
          />
          <Button type="link" size="small" icon={<ExportOutlined />} onClick={() => exportBomApi(record.id)}>
            导出
          </Button>
          <Popconfirm title="确定删除此BOM？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>BOM管理</h2>
        <Space>
          <Select
            placeholder="筛选客户"
            allowClear
            style={{ width: 200 }}
            onChange={(v) => setSelectedCustomer(v)}
            options={customers.map(c => ({ value: c.id, label: `${c.name} (${c.code})` }))}
          />
          <Select
            value={templateType}
            onChange={setTemplateType}
            style={{ width: 120 }}
            options={[
              { value: 'standard', label: '标准模板' },
              { value: 'qixin', label: '七鑫模板' },
            ]}
          />
          <Button icon={<DownloadOutlined />} onClick={handleDownloadTemplate}>下载模板</Button>
          <Button icon={<UploadOutlined />} onClick={() => setUploadModalVisible(true)}>Excel导入</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalVisible(true)}>新建BOM</Button>
        </Space>
      </div>

      <Table
        columns={columns}
        dataSource={bomList}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20 }}
      />

      <Modal
        title="新建BOM"
        open={createModalVisible}
        onCancel={() => { setCreateModalVisible(false); createForm.resetFields() }}
        onOk={() => createForm.submit()}
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="customer_id" label="客户" rules={[{ required: true, message: '请选择客户' }]}>
            <Select
              placeholder="选择客户"
              showSearch
              optionFilterProp="label"
              options={customers.map(c => ({ value: c.id, label: `${c.name} (${c.code})` }))}
            />
          </Form.Item>
          <Form.Item name="product_material_id" label="产品物料" rules={[{ required: true, message: '请选择产品物料' }]}>
            <Select
              placeholder="选择产品物料"
              showSearch
              optionFilterProp="label"
              options={materials.map((m: any) => ({ value: m.id, label: `${m.code} - ${m.name}` }))}
            />
          </Form.Item>
          <Form.Item name="version" label="版本号" initialValue="1.0">
            <Input placeholder="如：1.0" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="BOM描述（可选）" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`Excel导入BOM（${templateType === 'qixin' ? '七鑫格式' : '标准格式'}）`}
        open={uploadModalVisible}
        onCancel={() => { setUploadModalVisible(false); setFileList([]); setUploadProductCode(''); setUploadProductName('') }}
        onOk={handleUpload}
        confirmLoading={uploading}
      >
        <Form layout="vertical">
          <Form.Item label="模板格式" help="当前模板格式可在导入前在上方切换">
            <Tag color={templateType === 'qixin' ? 'blue' : 'green'}>
              {templateType === 'qixin' ? '七鑫格式' : '标准格式'}
            </Tag>
          </Form.Item>
          <Form.Item label="客户" required>
            <Select
              placeholder="选择客户"
              value={uploadCustomerCode}
              onChange={setUploadCustomerCode}
              options={customers.map(c => ({ value: c.code, label: `${c.name} (${c.code})` }))}
            />
          </Form.Item>
          <Form.Item label="版本号">
            <Input value={uploadVersion} onChange={e => setUploadVersion(e.target.value)} placeholder="如：1.0" />
          </Form.Item>
          <Form.Item label="产品编码" help="留空则使用Excel中的产品编码">
            <Input value={uploadProductCode} onChange={e => setUploadProductCode(e.target.value)} placeholder="覆盖Excel中的产品编码（可选）" />
          </Form.Item>
          <Form.Item label="产品名称" help="留空则使用物料主数据中的名称">
            <Input value={uploadProductName} onChange={e => setUploadProductName(e.target.value)} placeholder="指定产品名称（可选）" />
          </Form.Item>
          <Form.Item label="Excel文件" required>
            <Upload
              fileList={fileList}
              beforeUpload={() => false}
              onChange={({ fileList }) => setFileList(fileList)}
              maxCount={1}
              accept=".xlsx,.xls"
            >
              <Button icon={<UploadOutlined />}>选择文件</Button>
            </Upload>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
