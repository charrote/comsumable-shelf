import { useState } from 'react'
import { Table, Button, Card, Upload, Tag, message, Spin, Input } from 'antd'
import { UploadOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd'
import { uploadBomApi } from '../api'

const columns = [
  { title: 'BOM 名称', dataIndex: 'bom_name', key: 'bom_name' },
  { title: '物料数', dataIndex: 'unique_materials', key: 'unique_materials', width: 80 },
  { title: '总行数', dataIndex: 'total_items', key: 'total_items', width: 80 },
  { title: '替代品', dataIndex: 'alternates_found', key: 'alternates_found', width: 80 },
  {
    title: '状态',
    dataIndex: 'parsed',
    key: 'parsed',
    width: 80,
    render: (val: number | boolean) => <Tag color={val ? 'green' : 'default'}>{val ? '已解析' : '未解析'}</Tag>,
  },
]

export function BOMPage() {
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [bomList, setBomList] = useState<any[]>([])
  const [uploading, setUploading] = useState(false)

  const [customerId, setCustomerId] = useState<number | undefined>(undefined)

  const customRequest = async (options: any) => {
    const { file, onSuccess, onError } = options
    setUploading(true)
    try {
      const res = await uploadBomApi(file as File, customerId)
      const bom = { ...(res.data?.data ?? res.data), id: res.data?.bom_header_id ?? res.data?.id }
      setBomList(prev => [...prev, bom])
      message.success(`BOM "${bom.bom_name || file.name}" 上传成功`)
      onSuccess(res.data, file)
    } catch (e: any) {
      message.error('BOM 上传失败: ' + (e.response?.data?.message || e.message))
      onError(e)
    } finally {
      setUploading(false)
    }
  }

  const handleChange = (info: { fileList: UploadFile[] }) => {
    setFileList(info.fileList)
  }

  return (
    <div>
      <h2>BOM 管理</h2>
      <Card title="上传 BOM" style={{ marginBottom: 16 }}>
        <div style={{ marginBottom: 12 }}>
          <Input
            type="number"
            placeholder="客户 ID (可选)"
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value ? Number(e.target.value) : undefined)}
            style={{ width: 200 }}
          />
        </div>
        <Upload
          multiple={false}
          fileList={fileList}
          onChange={handleChange}
          customRequest={customRequest}
          showUploadList={true}
          accept=".xlsx,.xls"
        >
          <Button icon={<UploadOutlined />} loading={uploading} disabled={uploading}>
            选择 BOM 文件
          </Button>
        </Upload>
        <p style={{ color: '#999', marginTop: 8 }}>支持 Excel 格式 (xlsx/xls)</p>
      </Card>
      <Table
        columns={columns}
        dataSource={bomList}
        pagination={false}
        rowKey="id"
      />
    </div>
  )
}
