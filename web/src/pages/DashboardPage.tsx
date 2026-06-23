import { useState, useEffect } from 'react'
import { Card, Col, Row, Statistic, Table, Tag, Spin } from 'antd'
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  ShopOutlined,
  DatabaseOutlined,
  WarningOutlined,
  FileTextOutlined,
  InboxOutlined,
} from '@ant-design/icons'
import { getMaterialsApi, getShelvesApi, getInventoryApi, getDailyReportApi, getReceiptListApi, getIssueListApi } from '../api'

interface DashboardData {
  totalMaterials: number
  totalShelves: number
  onShelfReels: number
  trackingReels: number
  pendingReceipts: number
  pendingIssues: number
}

interface Transaction {
  key: string
  time: string
  type: string
  material: string
  quantity: number
  status: string
}

export function DashboardPage() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [slow, setSlow] = useState(false)
  const [data, setData] = useState<DashboardData>({
    totalMaterials: 0,
    totalShelves: 0,
    onShelfReels: 0,
    trackingReels: 0,
    pendingReceipts: 0,
    pendingIssues: 0,
  })
  const [transactions, setTransactions] = useState<Transaction[]>([])
  useEffect(() => {
    const slowTimer = setTimeout(() => setSlow(true), 5000)
    const today = new Date().toISOString().slice(0, 10)

    const fetchData = async () => {
      setLoading(true)
      setError(null)

      const results = await Promise.allSettled([
        getMaterialsApi({}),
        getShelvesApi(),
        getInventoryApi({}),
        getDailyReportApi(today),
        getReceiptListApi({ status: 'draft' }),
        getIssueListApi({ status: 'pending' }),
      ])

      clearTimeout(slowTimer)

      const errors: string[] = []
      let materials: any[] = []
      let shelves: any[] = []
      let pallets: any[] = []
      let reportDetails: any[] = []
      let pendingReceiptsCount = 0
      let pendingIssuesCount = 0

      if (results[0].status === 'fulfilled') {
        const d = results[0].value.data
        materials = Array.isArray(d) ? d : (Array.isArray(d?.data) ? d.data : d?.items ?? [])
      } else {
        errors.push('物料')
      }

      if (results[1].status === 'fulfilled') {
        const d = results[1].value.data
        shelves = Array.isArray(d) ? d : d?.items ?? []
      } else {
        errors.push('料架')
      }

      if (results[2].status === 'fulfilled') {
        const d = results[2].value.data
        pallets = d?.pallets ?? (Array.isArray(d) ? d : [])
      } else {
        errors.push('库存')
      }

      if (results[3].status === 'fulfilled') {
        const d = results[3].value.data
        reportDetails = d?.details ?? []
      }

      if (results[4].status === 'fulfilled') {
        const d = results[4].value.data
        pendingReceiptsCount = Array.isArray(d) ? d.length : d?.data?.length ?? 0
      }

      if (results[5].status === 'fulfilled') {
        const d = results[5].value.data
        pendingIssuesCount = Array.isArray(d) ? d.length : d?.data?.length ?? 0
      }

      const onShelfReels = pallets.filter(
        (item: any) => item.status === 'on_shelf',
      ).length
      const trackingReels = pallets.filter(
        (item: any) => item.status === 'tracking',
      ).length

      setData({
        totalMaterials: materials.length,
        totalShelves: shelves.length,
        onShelfReels,
        trackingReels,
        pendingReceipts: pendingReceiptsCount,
        pendingIssues: pendingIssuesCount,
      })

      setTransactions(
        reportDetails.map((op: any, i: number) => ({
          key: String(i),
          time: today,
          type: Number(op.in_qty || 0) > 0 ? '入库' : '出库',
          material: op.material_code ?? '',
          quantity: Number(op.in_qty || 0) + Number(op.out_qty || 0),
          status: '成功',
        })),
      )

      if (errors.length > 0) {
        setError(`部分数据加载失败: ${errors.join('、')}`)
      }

      setLoading(false)
    }

    fetchData()

    return () => clearTimeout(slowTimer)
  }, [])

  return (
    <div>
      {loading && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '40vh' }}>
          <div style={{ textAlign: 'center' }}>
            <Spin size="large" />
            {slow && (
              <p style={{ marginTop: 24, color: '#999' }}>
                后端服务未启动或连接超时，请确保后端运行在 8080 端口
              </p>
            )}
          </div>
        </div>
      )}
      {error && (
        <div style={{
          textAlign: 'center', margin: '40px 0', padding: 24,
          background: '#fffbe6', border: '1px solid #ffe58f', borderRadius: 8,
        }}>
          <p style={{ fontSize: 16, marginBottom: 8, color: '#ad6800' }}><WarningOutlined style={{ marginRight: 8 }} />部分数据加载异常</p>
          <p style={{ color: '#d46b08' }}>{error}</p>
          <p style={{ marginTop: 12, fontSize: 13, color: '#999' }}>
            部分面板仍显示已有数据
          </p>
        </div>
      )}
      {!loading && !error && (
        <>
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={6}>
              <Card>
                <Statistic
                  title="物料总数"
                  value={data.totalMaterials}
                  prefix={<DatabaseOutlined />}
                  valueStyle={{ color: '#3f8600' }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="料架总数"
                  value={data.totalShelves}
                  prefix={<ShopOutlined />}
                  valueStyle={{ color: '#1890ff' }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="在架库存盘"
                  value={data.onShelfReels}
                  suffix="盘"
                  prefix={<ArrowUpOutlined />}
                  valueStyle={{ color: '#3f8600' }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="跟踪中"
                  value={data.trackingReels}
                  suffix="盘"
                  prefix={<ArrowDownOutlined />}
                  valueStyle={{ color: '#cf1322' }}
                />
              </Card>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Card title="最近操作记录">
                <Table
                  dataSource={transactions}
                  columns={[
                    { title: '时间', dataIndex: 'time', key: 'time' },
                    { title: '类型', dataIndex: 'type', key: 'type' },
                    { title: '物料', dataIndex: 'material', key: 'material' },
                    { title: '数量', dataIndex: 'quantity', key: 'quantity' },
                    {
                      title: '状态',
                      dataIndex: 'status',
                      key: 'status',
                      render: (text: string) => (
                        <Tag color={text === '成功' ? 'green' : 'red'}>{text}</Tag>
                      ),
                    },
                  ]}
                  pagination={false}
                  size="small"
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card title="待处理事项">
                <div>
                  <p><FileTextOutlined style={{ marginRight: 8 }} />待确认入库: {data.pendingReceipts} 单</p>
                  <p><InboxOutlined style={{ marginRight: 8 }} />待执行发料: {data.pendingIssues} 单</p>
                </div>
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  )
}
