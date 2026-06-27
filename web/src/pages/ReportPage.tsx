import { useState } from 'react'
import { Card, DatePicker, Button, Table, Space, Statistic, Spin, message } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { getDailyReportApi } from '../api'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker

export function ReportPage() {
  const [range, setRange] = useState<[any, any] | null>(null)
  const [loading, setLoading] = useState(false)
  const [summary, setSummary] = useState<any>(null)
  const [details, setDetails] = useState<any[]>([])

  const handleQuery = async () => {
    if (!range || !range[0] || !range[1]) {
      message.warning('请选择日期范围')
      return
    }
    setLoading(true)
    try {
      const date = dayjs(range[0]).format('YYYY-MM-DD')
      const res = await getDailyReportApi(date)
      const data = res.data
      setSummary(data.summary)
      setDetails(data.details || [])
    } catch (err: any) {
      message.error(err.response?.data?.detail || '查询失败')
    } finally {
      setLoading(false)
    }
  }

  const columns = [
    { title: '物料编码', dataIndex: 'material_code', key: 'material_code' },
    { title: '期初库存', dataIndex: 'opening_balance', key: 'opening_balance', width: 120 },
    { title: '入库数量', dataIndex: 'in_qty', key: 'in_qty', width: 100 },
    { title: '出库数量', dataIndex: 'out_qty', key: 'out_qty', width: 100 },
    { title: '期末库存', dataIndex: 'closing_balance', key: 'closing_balance', width: 120 },
    { title: '在架盘数', dataIndex: 'reels_on_shelf', key: 'reels_on_shelf', width: 100 },
    { title: '待上架盘数', dataIndex: 'reels_pending_shelving', key: 'reels_pending_shelving', width: 100 },
    { title: '物理在库', dataIndex: 'reels_physical_inventory', key: 'reels_physical_inventory', width: 100 },
  ]

  return (
    <div>
      <h2>报表统计</h2>
      <Card style={{ marginBottom: 16 }}>
        <Space>
          <RangePicker onChange={setRange} />
          <Button icon={<SearchOutlined />} type="primary" onClick={handleQuery} loading={loading}>
            查询
          </Button>
        </Space>
      </Card>
      <Spin spinning={loading}>
        {summary && (
          <Space style={{ marginBottom: 16 }} wrap>
            <Card>
              <Statistic title="物料总数" value={summary.total_materials} />
            </Card>
            <Card>
              <Statistic title="入库总量" value={summary.total_in} />
            </Card>
            <Card>
              <Statistic title="出库总量" value={summary.total_out} />
            </Card>
            <Card>
              <Statistic title="期末库存(金额)" value={summary.total_balance} />
            </Card>
            <Card>
              <Statistic title="在架盘数" value={summary.total_reels_on_shelf} />
            </Card>
            <Card>
              <Statistic title="待上架盘数" value={summary.total_reels_pending_shelving} />
            </Card>
            <Card>
              <Statistic title="物理在库" value={summary.total_reels_physical_inventory} />
            </Card>
          </Space>
        )}
        <Table
          columns={columns}
          dataSource={details}
          pagination={false}
          rowKey="material_code"
        />
      </Spin>
    </div>
  )
}
