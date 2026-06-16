import { useState } from 'react'
import { Table, Button, Input, Space, Tag, Select } from 'antd'
import { SearchOutlined } from '@ant-design/icons'

const { Option } = Select

const columns = [
  { title: '库存盘号', key: 'pallet_id', width: 120 },
  { title: '物料编号', dataIndex: 'material_code', key: 'material_code' },
  { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 80 },
  { title: '入库时间', dataIndex: 'first_in_time', key: 'first_in_time', width: 160 },
  {
    title: '储位',
    dataIndex: 'shelf_slot_id',
    key: 'shelf_slot_id',
    width: 100,
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (_, record: any) => {
      const colors: Record<string, string> = {
        on_shelf: 'green',
        in_use: 'blue',
        tracking: 'orange',
        exhausted: 'red',
      }
      return <Tag color={colors[record.status]}>{record.status}</Tag>
    },
  },
]

const mockData = [
  { key: '1', material_code: '4500067189', quantity: 50, first_in_time: '2024-01-15 09:00', shelf_slot_id: 12, status: 'on_shelf' },
  { key: '2', material_code: '4500067189', quantity: 5, first_in_time: '2024-01-15 08:30', shelf_slot_id: 13, status: 'on_shelf' },
  { key: '3', material_code: '2623381607', quantity: 12, first_in_time: '2024-01-14 14:00', shelf_slot_id: 24, status: 'in_use' },
  { key: '4', material_code: '1112325305', quantity: 2, first_in_time: '2024-01-14 10:00', shelf_slot_id: 36, status: 'tracking' },
]

export function InventoryPage() {
  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <h2>库存管理</h2>
      </div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="搜索物料编号或库存盘号"
          prefix={<SearchOutlined />}
          style={{ width: 300 }}
        />
        <Select placeholder="状态筛选" style={{ width: 120 }}>
          <Option value="on_shelf">在架</Option>
          <Option value="tracking">跟踪中</Option>
          <Option value="exhausted">已耗尽</Option>
        </Select>
      </Space>
      <Table
        columns={columns}
        dataSource={mockData}
        pagination={{ pageSize: 20 }}
        rowKey="key"
      />
    </div>
  )
}
