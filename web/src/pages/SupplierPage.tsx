import { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, Space, Popconfirm, message, Upload } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, UploadOutlined, DownloadOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd'
import {
  getSuppliersApi, createSupplierApi, updateSupplierApi, deleteSupplierApi,
  uploadSuppliersApi, downloadSupplierTemplateApi,
} from '../api'

export function SupplierPage() {
  const [dataList, setDataList] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingRecord, setEditingRecord] = useState<any | null>(null)
  const [form] = Form.useForm()

  // ── Upload state ──
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadFileList, setUploadFileList] = useState<UploadFile[]>([])

  const loadData = async () => {
    setLoading(true)
    try {
      const res = await getSuppliersApi()
      setDataList(Array.isArray(res.data) ? res.data : [])
    } catch {
      message.error('加载供应商数据失败')
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
    form.setFieldsValue({
      code: record.code,
      name: record.name,
      contact_name: record.contact_name,
      contact_phone: record.contact_phone,
      address: record.address,
    })
    setModalOpen(true)
  }

  const handleSave = async (values: any) => {
    try {
      if (editingRecord) {
        await updateSupplierApi(editingRecord.id, values)
        message.success('供应商更新成功')
      } else {
        await createSupplierApi(values)
        message.success('供应商创建成功')
      }
      setModalOpen(false)
      form.resetFields()
      loadData()
    } catch (e: any) {
      message.error(e.response?.data?.detail || (editingRecord ? '更新供应商失败' : '创建供应商失败'))
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteSupplierApi(id)
      message.success('供应商已删除')
      loadData()
    } catch {
      message.error('删除供应商失败')
    }
  }

  const handleUpload = async () => {
    if (uploadFileList.length === 0) {
      message.error('请选择文件')
      return
    }
    setUploading(true)
    try {
      const res = await uploadSuppliersApi(uploadFileList[0].originFileObj as File)
      const d = res.data
      message.success(`导入完成：共 ${d.total} 条，新增 ${d.imported} 条，跳过 ${d.skipped} 条（重复）`)
      setUploadModalOpen(false)
      setUploadFileList([])
      loadData()
    } catch (e: any) {
      message.error('导入失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setUploading(false)
    }
  }

  const columns = [
    { title: '序号', key: 'index', width: 60, render: (_: any, __: any, index: number) => index + 1 },
    { title: '供应商编码', dataIndex: 'code', key: 'code', width: 150 },
    { title: '供应商名称', dataIndex: 'name', key: 'name', width: 200 },
    { title: '联系人', dataIndex: 'contact_name', key: 'contact_name', width: 120 },
    { title: '联系电话', dataIndex: 'contact_phone', key: 'contact_phone', width: 140 },
    { title: '地址', dataIndex: 'address', key: 'address' },
    {
      title: '操作', key: 'action', width: 120,
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={() => openEditModal(record)} />
          <Popconfirm title="确认删除该供应商？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>供应商管理</h2>
        <Space>
          <Button icon={<DownloadOutlined />} onClick={downloadSupplierTemplateApi}>下载模板</Button>
          <Button icon={<UploadOutlined />} onClick={() => setUploadModalOpen(true)}>Excel导入</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>新建供应商</Button>
        </Space>
      </div>

      <Table
        columns={columns}
        dataSource={dataList}
        rowKey="id"
        loading={loading}
        pagination={{
          pageSize: 10,
          showSizeChanger: true,
          pageSizeOptions: ['10', '20', '50', '100'],
          showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条 / 共 ${total} 条`,
        }}
      />

      {/* ── Create/Edit Modal ── */}
      <Modal
        title={editingRecord ? '编辑供应商' : '新建供应商'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); form.resetFields() }}
        footer={null}
      >
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="code" label="供应商编码" rules={[{ required: true, message: '请输入供应商编码' }]}>
            <Input placeholder="输入供应商编码" />
          </Form.Item>
          <Form.Item name="name" label="供应商名称" rules={[{ required: true, message: '请输入供应商名称' }]}>
            <Input placeholder="输入供应商名称" />
          </Form.Item>
          <Form.Item name="contact_name" label="联系人">
            <Input placeholder="输入联系人姓名" />
          </Form.Item>
          <Form.Item name="contact_phone" label="联系电话">
            <Input placeholder="输入联系电话" />
          </Form.Item>
          <Form.Item name="address" label="地址">
            <Input placeholder="输入地址" />
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
        title="Excel导入供应商"
        open={uploadModalOpen}
        onCancel={() => { setUploadModalOpen(false); setUploadFileList([]) }}
        onOk={handleUpload}
        confirmLoading={uploading}
      >
        <Form layout="vertical">
          <Form.Item label="Excel文件" required help="支持 .xls 和 .xlsx 格式，重复编码自动跳过">
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
    </div>
  )
}
