import { useState, useEffect } from 'react'
import { Card, Col, Row, Statistic, Tag, Spin, Table } from 'antd'
import {
  ArrowUpOutlined,
  ShopOutlined,
  DatabaseOutlined,
  WarningOutlined,
  ClockCircleOutlined,
  InboxOutlined,
} from '@ant-design/icons'
import {
  getMaterialsApi,
  getShelvesApi,
  getInventoryApi,
  getDashboardPendingListsApi,
} from '../api'
import type { ColumnsType } from 'antd/es/table'

interface DashboardData {
  totalMaterials: number
  totalShelves: number
  onShelfReels: number
  pendingShelvingReels: number
  physicalInventory: number
  pendingReceipts: number
  pendingIssues: number
}

interface PendingReceipt {
  id: number
  receipt_no: string
  purchase_order_no: string
  created_at: string | null
  items_count: number
  operator: string
}

interface PendingShelving {
  reel_id: number
  reel_code: string
  material_code: string
  material_name: string
  quantity: number
  created_at: string | null
}

interface PendingIssue {
  id: number
  order_no: string
  production_quantity: number
  required_date: string | null
  created_at: string | null
  detail_count: number
}

interface PendingLists {
  pending_receipts: PendingReceipt[]
  pending_shelving: PendingShelving[]
  pending_issues: PendingIssue[]
}

function formatTime(val: string | null | undefined): string {
  if (!val) return '-'
  const d = new Date(val)
  if (isNaN(d.getTime())) return val
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${mm}-${dd} ${hh}:${mi}`
}

export function DashboardPage() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [slow, setSlow] = useState(false)
  const [data, setData] = useState<DashboardData>({
    totalMaterials: 0,
    totalShelves: 0,
    onShelfReels: 0,
    pendingShelvingReels: 0,
    physicalInventory: 0,
    pendingReceipts: 0,
    pendingIssues: 0,
  })
  const [pendingLists, setPendingLists] = useState<PendingLists>({
    pending_receipts: [],
    pending_shelving: [],
    pending_issues: [],
  })

  useEffect(() => {
    const slowTimer = setTimeout(() => setSlow(true), 5000)

    const fetchData = async () => {
      setLoading(true)
      setError(null)

      const results = await Promise.allSettled([
        getMaterialsApi({}),
        getShelvesApi(),
        getInventoryApi({}),
        getDashboardPendingListsApi(),
      ])

      clearTimeout(slowTimer)

      const errors: string[] = []
      let materials: any[] = []
      let shelves: any[] = []
      let pallets: any[] = []
      let pendingListsData: PendingLists = {
        pending_receipts: [],
        pending_shelving: [],
        pending_issues: [],
      }

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
        pendingListsData = {
          pending_receipts: d?.pending_receipts ?? [],
          pending_shelving: d?.pending_shelving ?? [],
          pending_issues: d?.pending_issues ?? [],
        }
      } else {
        errors.push('待处理列表')
      }

      const onShelfReels = pallets.filter(
        (item: any) => item.status === 'on_shelf',
      ).length
      const pendingShelvingReels = pallets.filter(
        (item: any) => item.status === 'pending_shelving',
      ).length

      setData({
        totalMaterials: materials.length,
        totalShelves: shelves.length,
        onShelfReels,
        pendingShelvingReels,
        physicalInventory: onShelfReels + pendingShelvingReels,
        pendingReceipts: pendingListsData.pending_receipts.length,
        pendingIssues: pendingListsData.pending_issues.length,
      })

      setPendingLists(pendingListsData)

      if (errors.length > 0) {
        setError(`部分数据加载失败: ${errors.join('、')}`)
      }

      setLoading(false)
    }

    fetchData()

    return () => clearTimeout(slowTimer)
  }, [])

  // ─── Columns for each table ───

  const receiptColumns: ColumnsType<PendingReceipt> = [
    {
      title: '收料单号',
      dataIndex: 'receipt_no',
      key: 'receipt_no',
      width: 140,
      render: (val: string) => <span style={{ fontWeight: 500, fontSize: 13 }}>{val}</span>,
    },
    {
      title: '采购单号',
      dataIndex: 'purchase_order_no',
      key: 'purchase_order_no',
      width: 120,
      render: (val: string) => val || '-',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 120,
      render: (val: string) => formatTime(val),
    },
    {
      title: '料项数',
      dataIndex: 'items_count',
      key: 'items_count',
      width: 70,
      align: 'center',
    },
    {
      title: '操作人',
      dataIndex: 'operator',
      key: 'operator',
      width: 80,
      render: (val: string) => val || '-',
    },
  ]

  const shelvingColumns: ColumnsType<PendingShelving> = [
    {
      title: '料盘编码',
      dataIndex: 'reel_code',
      key: 'reel_code',
      width: 130,
      render: (val: string) => <span style={{ fontWeight: 500, fontSize: 13 }}>{val}</span>,
    },
    {
      title: '物料编码',
      dataIndex: 'material_code',
      key: 'material_code',
      width: 110,
    },
    {
      title: '物料名称',
      dataIndex: 'material_name',
      key: 'material_name',
      width: 120,
      render: (val: string) => val || '-',
    },
    {
      title: '数量',
      dataIndex: 'quantity',
      key: 'quantity',
      width: 70,
      align: 'right',
      render: (val: number) => val,
    },
  ]

  const issueColumns: ColumnsType<PendingIssue> = [
    {
      title: '发料单号',
      dataIndex: 'order_no',
      key: 'order_no',
      width: 150,
      render: (val: string) => <span style={{ fontWeight: 500, fontSize: 13 }}>{val}</span>,
    },
    {
      title: '生产数量',
      dataIndex: 'production_quantity',
      key: 'production_quantity',
      width: 90,
      align: 'right',
    },
    {
      title: '物料项数',
      dataIndex: 'detail_count',
      key: 'detail_count',
      width: 80,
      align: 'center',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 120,
      render: (val: string) => formatTime(val),
    },
  ]

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
          {/* 隐藏列表卡片滚动条 */}
          <style>{`
            .dashboard-scroll-inner {
              scrollbar-width: none;
              -ms-overflow-style: none;
            }
            .dashboard-scroll-inner::-webkit-scrollbar {
              display: none;
            }
          `}</style>
          {/* ── Top Row: 4 Stat Cards (equal height) ── */}
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={6}>
              <Card style={{ height: '100%' }}>
                <Statistic
                  title="物料总数"
                  value={data.totalMaterials}
                  prefix={<DatabaseOutlined />}
                  valueStyle={{ color: '#3f8600' }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card style={{ height: '100%' }}>
                <Statistic
                  title="料架总数"
                  value={data.totalShelves}
                  prefix={<ShopOutlined />}
                  valueStyle={{ color: '#1890ff' }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card style={{ height: '100%' }}>
                <Statistic
                  title="物理在库"
                  value={data.physicalInventory}
                  suffix="盘"
                  prefix={<ArrowUpOutlined />}
                  valueStyle={{ color: '#3f8600' }}
                />
                <div style={{ fontSize: 12, color: '#999', marginTop: 4, textAlign: 'center' }}>
                  在架 {data.onShelfReels} · 待上架 {data.pendingShelvingReels}
                </div>
              </Card>
            </Col>
            <Col span={6}>
              <Card style={{ height: '100%' }}>
                <Statistic
                  title="待上架"
                  value={data.pendingShelvingReels}
                  suffix="盘"
                  prefix={<WarningOutlined />}
                  valueStyle={{ color: data.pendingShelvingReels > 0 ? '#faad14' : '#3f8600' }}
                />
              </Card>
            </Col>
          </Row>

          {/* ── Bottom Row: 3 Equal-Width Pending Lists (equal height, taller, hidden scrollbar) ── */}
          <Row gutter={16}>
            {/* 待入库收料单 */}
            <Col span={8}>
              <Card
                title={
                  <span>
                    <InboxOutlined style={{ marginRight: 8 }} />
                    待入库收料单
                    <Tag style={{ marginLeft: 8 }} color="blue">{pendingLists.pending_receipts.length}</Tag>
                  </span>
                }
                style={{ height: 400 }}
                styles={{ body: { padding: 0, height: 'calc(100% - 57px)', overflow: 'hidden' } }}
              >
                <div className="dashboard-scroll-inner" style={{ height: '100%', overflowY: 'auto' }}>
                  <Table
                    dataSource={pendingLists.pending_receipts}
                    columns={receiptColumns}
                    rowKey="id"
                    pagination={false}
                    size="small"
                    locale={{ emptyText: '暂无待入库收料单' }}
                  />
                </div>
              </Card>
            </Col>

            {/* 待上架物料 */}
            <Col span={8}>
              <Card
                title={
                  <span>
                    <ClockCircleOutlined style={{ marginRight: 8 }} />
                    待上架物料
                    <Tag style={{ marginLeft: 8 }} color="orange">{pendingLists.pending_shelving.length}</Tag>
                  </span>
                }
                style={{ height: 400 }}
                styles={{ body: { padding: 0, height: 'calc(100% - 57px)', overflow: 'hidden' } }}
              >
                <div className="dashboard-scroll-inner" style={{ height: '100%', overflowY: 'auto' }}>
                  <Table
                    dataSource={pendingLists.pending_shelving}
                    columns={shelvingColumns}
                    rowKey="reel_id"
                    pagination={false}
                    size="small"
                    locale={{ emptyText: '暂无待上架物料' }}
                  />
                </div>
              </Card>
            </Col>

            {/* 待发料料单 */}
            <Col span={8}>
              <Card
                title={
                  <span>
                    <ArrowUpOutlined style={{ marginRight: 8 }} />
                    待发料料单
                    <Tag style={{ marginLeft: 8 }} color="green">{pendingLists.pending_issues.length}</Tag>
                  </span>
                }
                style={{ height: 400 }}
                styles={{ body: { padding: 0, height: 'calc(100% - 57px)', overflow: 'hidden' } }}
              >
                <div className="dashboard-scroll-inner" style={{ height: '100%', overflowY: 'auto' }}>
                  <Table
                    dataSource={pendingLists.pending_issues}
                    columns={issueColumns}
                    rowKey="id"
                    pagination={false}
                    size="small"
                    locale={{ emptyText: '暂无待发料料单' }}
                  />
                </div>
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  )
}
