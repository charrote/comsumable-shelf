import { useState, useEffect } from 'react'
import { Table, Button, Space, Tag, Modal, Form, InputNumber, message, Descriptions, Tree, Card, Statistic, Row, Col, Select, Typography, Tooltip } from 'antd'
import { PlusOutlined, CalculatorOutlined, CheckCircleOutlined, CloseCircleOutlined, FileTextOutlined, SwapOutlined, BulbOutlined } from '@ant-design/icons'
import type { DataNode } from 'antd/es/tree'
import { getIssueListApi, createIssueApi, calculateIssueApi } from '../api'
import { getBomListApi, getBomApi } from '../api'

const { Text, Title } = Typography

const statusLabels: Record<string, string> = {
  pending: '待计算',
  assigned: '已分配',
  picking: '拣货中',
  completed: '已完成',
}

const statusColors: Record<string, string> = {
  pending: 'default',
  assigned: 'blue',
  picking: 'orange',
  completed: 'green',
}

// ── 储位灯颜色映射 ──
const PICKING_COLOR_MAP: Record<string, { label: string; hex: string; textColor: string }> = {
  red: { label: '红色', hex: '#ff4d4f', textColor: '#fff' },
  green: { label: '绿色', hex: '#52c41a', textColor: '#fff' },
  yellow: { label: '黄色', hex: '#faad14', textColor: '#000' },
  blue: { label: '蓝色', hex: '#1677ff', textColor: '#fff' },
  magenta: { label: '品红', hex: '#eb2f96', textColor: '#fff' },
  cyan: { label: '青色', hex: '#13c2c2', textColor: '#fff' },
  white: { label: '白色', hex: '#ffffff', textColor: '#000' },
}

function ColorBadge({ color }: { color: string }) {
  const info = PICKING_COLOR_MAP[color]
  if (!info) return null
  return (
    <Tooltip title={`储位灯颜色：${info.label}`}>
      <Tag
        color={info.hex}
        style={{
          color: info.textColor,
          border: color === 'white' ? '1px solid #d9d9d9' : 'none',
        }}
      >
        <BulbOutlined style={{ marginRight: 4 }} />
        {info.label}
      </Tag>
    </Tooltip>
  )
}

export function IssueOrderPage() {
  const [issueList, setIssueList] = useState<any[]>([])
  const [bomList, setBomList] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [createModal, setCreateModal] = useState(false)
  const [detailModal, setDetailModal] = useState(false)
  const [currentIssue, setCurrentIssue] = useState<any>(null)
  const [createForm] = Form.useForm()
  const [creating, setCreating] = useState(false)
  const [calcLoading, setCalcLoading] = useState<Record<string, boolean>>({})

  const loadData = async () => {
    setLoading(true)
    try {
      const res = await getIssueListApi({})
      setIssueList(res.data || [])
    } catch {
      message.error('加载发料单失败')
    } finally {
      setLoading(false)
    }
  }

  const loadBomList = async () => {
    try {
      const res = await getBomListApi({})
      setBomList(res.data || [])
    } catch {}
  }

  useEffect(() => {
    loadData()
    loadBomList()
  }, [])

  const handleCreate = async (values: any) => {
    setCreating(true)
    try {
      const res = await createIssueApi({
        bom_id: values.bom_id,
        production_quantity: values.production_quantity,
        customer_id: 1,
      })
      message.success(`发料单 ${res.data.order_no} 创建成功`)
      setCreateModal(false)
      createForm.resetFields()
      loadData()
    } catch (e: any) {
      message.error(e.response?.data?.detail || '创建失败')
    } finally {
      setCreating(false)
    }
  }

  const handleCalculate = async (orderId: number) => {
    setCalcLoading(prev => ({ ...prev, [orderId]: true }))
    try {
      const res = await calculateIssueApi(orderId, { strategy: 'config' })
      // 检查是否有缺料
      const hasShortage = res.data?.materials?.some((m: any) => (m.shortage || 0) > 0)
      if (hasShortage) {
        message.warning('FIFO计算完成，但部分物料库存不足，订单仍为待计算状态')
      } else {
        message.success('FIFO计算完成，物料已全部锁定')
      }
      // 始终打开详情弹窗，让用户看到每条物料的分配/缺料情况
      await viewDetail(orderId)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '计算失败')
    } finally {
      setCalcLoading(prev => ({ ...prev, [orderId]: false }))
    }
  }

  const viewDetail = async (orderId: number) => {
    try {
      const res = await fetch(`/api/issues/${orderId}`)
      const data = await res.json()
      setCurrentIssue(data)
      setDetailModal(true)
    } catch {
      message.error('加载详情失败')
    }
  }

  // Build tree from flat details
  const buildTreeData = (details: any[]): DataNode[] => {
    return details.map(d => ({
      key: d.material_id,
      title: (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileTextOutlined />
          <span><strong>{d.material_code}</strong></span>
          <span style={{ color: '#999' }}>{d.material_name}</span>
          <Tag>{d.required_qty} {d.material_unit}</Tag>
          {d.shortage > 0 ? (
            <Tag color="red">缺{d.shortage}</Tag>
          ) : (
            <Tag color="green">齐套</Tag>
          )}
        </div>
      ),
      children: d.reel_assignments?.length > 0 ? d.reel_assignments.map((ra: any) => ({
        key: `reel-${ra.reel_id}`,
        title: (
          <div style={{ paddingLeft: 16 }}>
            <Space size={4}>
              <SwapOutlined />
              <span>Reel #{ra.reel_id}</span>
              {ra.reel_barcode && <Tag>{ra.reel_barcode}</Tag>}
              <span>{ra.pick_quantity}/{ra.original_quantity}</span>
              {ra.slot_code && <Tag color="blue">{ra.slot_code}</Tag>}
            </Space>
          </div>
        ),
      })) : [],
    }))
  }

  const columns = [
    { title: '发料单号', dataIndex: 'order_no', key: 'order_no', width: 180 },
    { title: '产品编码', dataIndex: 'product_code', key: 'product_code', width: 150 },
    { title: '产品名称', dataIndex: 'product_name', key: 'product_name', width: 200, ellipsis: true },
    { title: '生产数量', dataIndex: 'production_quantity', key: 'production_quantity', width: 100 },
    { title: '明细数', dataIndex: 'detail_count', key: 'detail_count', width: 80 },
    {
      title: '储位灯颜色', dataIndex: 'assigned_color', key: 'assigned_color', width: 110,
      render: (val: string) => val ? <ColorBadge color={val} /> : '-',
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (val: string) => <Tag color={statusColors[val]}>{statusLabels[val]}</Tag>,
    },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (val: string) => val ? new Date(val).toLocaleString() : '-',
    },
    {
      title: '操作', key: 'action', width: 150,
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" size="small" onClick={() => viewDetail(record.id)}>详情</Button>
          {record.status === 'pending' && (
            <Button
              type="link"
              size="small"
              icon={<CalculatorOutlined />}
              loading={calcLoading[record.id]}
              onClick={() => handleCalculate(record.id)}
            >
              计算
            </Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>发料管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModal(true)}>新建发料单</Button>
      </div>

      <Table
        columns={columns}
        dataSource={issueList}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20 }}
      />

      {/* Create Modal */}
      <Modal
        title="新建发料单"
        open={createModal}
        onCancel={() => { setCreateModal(false); createForm.resetFields() }}
        onOk={() => createForm.submit()}
        confirmLoading={creating}
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="bom_id" label="选择产品(BOM)" rules={[{ required: true, message: '请选择BOM' }]}>
            <Select
              placeholder="选择要生产的产品"
              showSearch
              optionFilterProp="label"
              options={bomList.map(b => ({
                value: b.id,
                label: `${b.product_code} - ${b.product_name} v${b.version}`,
              }))}
            />
          </Form.Item>
          <Form.Item name="production_quantity" label="生产数量" rules={[{ required: true, message: '请输入生产数量' }]}>
            <InputNumber min={1} step={1} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Detail Modal */}
      <Modal
        title={`发料单详情 - ${currentIssue?.order_no}`}
        open={detailModal}
        onCancel={() => setDetailModal(false)}
        footer={null}
        width={800}
      >
        {currentIssue && (
          <div>
            <Descriptions column={4} size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="产品"><Text strong>{currentIssue.product_code}</Text></Descriptions.Item>
              <Descriptions.Item label="版本">v{currentIssue.version || '-'}</Descriptions.Item>
              <Descriptions.Item label="生产数量">{currentIssue.production_quantity}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Space>
                  <Tag color={statusColors[currentIssue.status]}>{statusLabels[currentIssue.status]}</Tag>
                  {currentIssue.assigned_color && <ColorBadge color={currentIssue.assigned_color} />}
                </Space>
              </Descriptions.Item>
            </Descriptions>

            {/* Summary Stats */}
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={6}>
                <Card>
                  <Statistic title="物料种类" value={currentIssue.details?.length || 0} suffix="种" />
                </Card>
              </Col>
              <Col span={6}>
                <Card>
                  <Statistic title="齐套" value={currentIssue.details?.filter((d: any) => d.shortage === 0)?.length || 0} suffix={`/${currentIssue.details?.length || 0}`} valueStyle={{ color: '#3f8600' }} />
                </Card>
              </Col>
              <Col span={6}>
                <Card>
                  <Statistic title="缺料" value={currentIssue.details?.filter((d: any) => d.shortage > 0)?.length || 0} suffix="项" valueStyle={{ color: '#cf1322' }} />
                </Card>
              </Col>
              <Col span={6}>
                <Card>
                  <Statistic title="料盘总数" value={currentIssue.details?.reduce((sum: number, d: any) => sum + (d.reel_assignments?.length || 0), 0) || 0} suffix="盘" />
                </Card>
              </Col>
            </Row>

            {/* Material Tree */}
            <Title level={5}>物料及料盘明细</Title>
            <Tree
              treeData={buildTreeData(currentIssue.details || [])}
              defaultExpandAll
              showLine
            />
          </div>
        )}
      </Modal>
    </div>
  )
}
