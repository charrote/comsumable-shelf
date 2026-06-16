import { useState } from 'react'
import { Table, Button, Card, Upload, Tag, Space } from 'antd'
import { UploadOutlined, FileExcelOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd'

const columns = [
  { title: 'BOM 名称', dataIndex: 'name', key: 'name' },
  { title: '产品', dataIndex: 'product_code', key: 'product_code' },
  { title: '物料数', dataIndex: 'unique_materials', key: 'unique_materials', width: 80 },
  { title: '总行数', dataIndex: 'total_items', key: 'total_items', width: 80 },
  { title: '替代品', dataIndex: 'alternates_found', key: 'alternates_found', width: 80 },
  {
    title: '状态',
    dataIndex: 'parsed',
    key: 'parsed',
    width: 80,
    render: (val: number) => <Tag color={val ? 'green' : 'default'}>{val ? '已解析' : '未解析'}</Tag>,
  },
]

const mockData = [
  { key: '1', name: '主板 V2 BOM.xlsx', product_code: 'PCB-MAIN-001', unique_materials: 42, total_items: 56, alternates_found: 8, parsed: 1 },
  { key: '2', name: '副板 V3 BOM.xlsx', product_code: 'PCB-FUNC-002', unique_materials: 28, total_items: 35, alternates_found: 4, parsed: 1 },
]

export function BOMPage() {
  const [fileList, setFileList] = useState<UploadFile[]>([])

  const uploadProps = {
    action: '/api/bom/upload',
    multiple: false,
    fileList,
    onChange: (info: { fileList: UploadFile[] }) => setFileList(info.fileList),
  }

  return (
    <div>
      <h2>BOM 管理</h2>
      <Card title="上传 BOM" style={{ marginBottom: 16 }}>
        <Upload {...uploadProps}>
          <Button icon={<UploadOutlined />}>选择 BOM 文件</Button>
        </Upload>
        <p style={{ color: '#999', marginTop: 8 }}>支持 Excel 格式 (xlsx/xls)</p>
      </Card>
      <Table
        columns={columns}
        dataSource={mockData}
        pagination={false}
        rowKey="key"
      />
    </div>
  )
}
