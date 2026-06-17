import { useState, useEffect } from 'react'
import { Table, Button, Space, Tag, Modal, Form, Input, DatePicker, message, Spin } from 'antd'
import { PlusOutlined, CalculatorOutlined, BulbOutlined } from '@ant-design/icons'
import { getIssueListApi, calculateIssueApi, assignLedApi, generateIssueFromBomApi } from '../api'

const statusLabels: Record<string, string> = {
  pending: '待处理',
  calculating: '计算中',
  assigned: '已分配',
  completed: '已完成',
}

const statusColors: Record<string, string> = {
  pending: 'default',
  calculating: 'processing',
  assigned: 'blue',
  completed: 'green',
}

export function IssueOrderPage() {
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [createModal, setCreateModal] = useState(false)
  const [form] = Form.useForm()
  const [creating, setCreating] = useState(false)
  const [calcLoading, setCalcLoading] = useState<Record<string, boolean>>({})
  const [assignLoading, setAssignLoading] = useState<Record<string, boolean>>({})

  const loadData = async () => {
    setLoading(true)
    try {
      const res = await getIssueListApi({})
      setData(res.data?.data ?? res.data ?? [])
    } catch {
      message.error('加载发料单失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleCreate = async (values: any) => {
    setCreating(true)
    try {
      await generateIssueFromBomApi(values.bom_id, { customer_id: values.customer_id })
      message.success('发料单创建成功')
      setCreateModal(false)
      form.resetFields()
      loadData()
    } catch (e: any) {
      message.error('创建失败: ' + (e.response?.data?.message || e.message))
    } finally {
      setCreating(false)
    }
  }

  const handleCalculate = async (orderId: number) => {
    setCalcLoading(prev => ({ ...prev, [orderId]: true }))
    try {
      await calculateIssueApi(orderId, { strategy: 'default' })
      message.success('计算完成')
      loadData()
    } catch (e: any) {
      message.error('计算失败: ' + (e.response?.data?.message || e.message))
    } finally {
      setCalcLoading(prev => ({ ...prev, [orderId]: false }))
    }
  }

  const handleAssignLed = async (orderId: number) => {
    setAssignLoading(prev => ({ ...prev, [orderId]: true }))
    try {
      await assignLedApi(orderId)
      message.success('LED 分配成功')
      loadData()
    } catch (e: any) {
      message.error('LED 分配失败: ' + (e.response?.data?.message || e.message))
    } finally {
      setAssignLoading(prev => ({ ...prev, [orderId]: false }))
    }
  }

  const columns = [
    { title: '发料单号', dataIndex: 'order_no', key: 'order_no' },
    { title: 'BOM', dataIndex: 'bom_name', key: 'bom_name' },
    { title: '物料数', dataIndex: 'total_materials', key: 'total_materials', width: 80 },
    { title: '需求日期', dataIndex: 'required_date', key: 'required_date', width: 120 },
    {
      title: '状态',
      key: 'status',
      width: 100,
      render: (_: any, record: any) => (
        <Tag color={statusColors[record.status]}>{statusLabels[record.status] || record.status}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 220,
      render: (_: any, record: any) => (
        <Space>
          <Button
            size="small"
            icon={<CalculatorOutlined />}
            loading={calcLoading[record.id]}
            onClick={() => handleCalculate(record.id)}
            disabled={record.status === 'completed'}
          >
            计算
          </Button>
          <Button
            size="small"
            icon={<BulbOutlined />}
            loading={assignLoading[record.id]}
            onClick={() => handleAssignLed(record.id)}
            disabled={record.status === 'completed'}
          >
            分配 LED
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>发料管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModal(true)}>
          新建发料单
        </Button>
      </div>
      <Spin spinning={loading}>
        <Table
          columns={columns}
          dataSource={data}
          pagination={false}
          rowKey="id"
        />
      </Spin>
      <Modal
        title="新建发料单"
        open={createModal}
        onCancel={() => setCreateModal(false)}
        footer={null}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="bom_id" label="BOM ID" rules={[{ required: true, message: '请输入 BOM ID' }]}>
            <Input type="number" placeholder="输入 BOM 编号" />
          </Form.Item>
          <Form.Item name="customer_id" label="客户 ID" rules={[{ required: true, message: '请输入客户 ID' }]}>
            <Input type="number" placeholder="输入客户 ID" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={creating}>创建</Button>
              <Button onClick={() => setCreateModal(false)}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
