import { useState } from 'react'
import { Card, Table, Form, Input, Button, Space, Tag, Switch } from 'antd'

const columns = [
  { title: '设置项', dataIndex: 'key', key: 'key', width: 200 },
  { title: '描述', dataIndex: 'description', key: 'description' },
  { title: '值', dataIndex: 'value', key: 'value', width: 120 },
]

const settingsData = [
  { key: 'FIFO_STRATEGY', description: 'FIFO 出库策略 (tail_first | time_fifo | mixed)', value: 'tail_first' },
  { key: 'LED_WORKER_COUNT', description: 'LED 亮灯并发数', value: '4' },
  { key: 'SLOT_POLL_INTERVAL', description: '储位轮询间隔 (秒)', value: '1' },
  { key: 'XR_MATCH_WINDOW_SECONDS', description: 'XR 配对时间窗口 (秒)', value: '10' },
  { key: 'DUPLICATE_DETECTION', description: '重复扫码检测开关', value: 'true' },
]

export function SystemSettingsPage() {
  return (
    <div>
      <h2>系统设置</h2>
      <Card>
        <Table
          columns={[
            ...columns,
            {
              title: '操作',
              key: 'action',
              width: 100,
              render: () => (
                <Button type="link" size="small">修改</Button>
              ),
            },
          ]}
          dataSource={settingsData}
          pagination={false}
          rowKey="key"
        />
      </Card>
    </div>
  )
}
