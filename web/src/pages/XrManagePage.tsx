import { useState, useEffect } from 'react'
import { Table, Tag, Card, Input, Form, Button, message, Spin } from 'antd'
import { UploadOutlined } from '@ant-design/icons'
import { getXRListApi, uploadXrApi } from '../api'

const statusLabels: Record<string, string> = {
  pending_match: '待匹配',
  matched: '已匹配',
  failed: '失败',
}

const statusColors: Record<string, string> = {
  pending_match: 'orange',
  matched: 'green',
  failed: 'red',
}

const columns = [
  { title: '批次号', dataIndex: 'id', key: 'id', width: 100 },
  { title: '物料', dataIndex: 'material_code', key: 'material_code' },
  { title: '盘数', dataIndex: 'counted_qty', key: 'counted_qty', width: 80 },
  { title: '扫描时间', dataIndex: 'scanned_at', key: 'scanned_at', width: 160 },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    width: 100,
    render: (text: string) => (
      <Tag color={statusColors[text]}>{statusLabels[text] || text}</Tag>
    ),
  },
]

export function XrManagePage() {
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [uploadForm] = Form.useForm()

  const loadData = async () => {
    setLoading(true)
    try {
      const res = await getXRListApi({})
      setData(res.data?.data ?? res.data ?? [])
    } catch {
      message.error('加载点料记录失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleUpload = async (values: any) => {
    setLoading(true)
    try {
      const res = await uploadXrApi({ reel_id: values.reel_id, qty: values.qty })
      message.success(res.data?.message || '点料数据上传成功')
      uploadForm.resetFields()
      loadData()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '上传失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h2>点料机管理</h2>

      <Card title="点料机数据上报" style={{ marginBottom: 16 }}>
        <Form form={uploadForm} layout="inline" onFinish={handleUpload}>
          <Form.Item label="盘号" name="reel_id" rules={[{ required: true, message: '请输入盘号' }]}>
            <Input placeholder="扫码枪扫描盘号" style={{ width: 250 }} />
          </Form.Item>
          <Form.Item label="数量" name="qty" rules={[{ required: true, message: '请输入数量' }]}>
            <Input type="number" style={{ width: 100 }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" icon={<UploadOutlined />} htmlType="submit">上传</Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="点料记录">
        <Spin spinning={loading}>
          <Table
            columns={columns}
            dataSource={data}
            pagination={false}
            rowKey="id"
          />
        </Spin>
      </Card>
    </div>
  )
}
