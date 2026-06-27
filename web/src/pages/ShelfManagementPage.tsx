import { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, InputNumber, Space, Tag, Popconfirm, Spin, message, Drawer, Select } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { getShelvesApi, createShelfApi, updateShelfApi, deleteShelfApi, getShelfSlotsApi, createSlotApi, updateSlotApi, deleteSlotApi, rackTestApi, getSlotStatesExtendedApi } from '../api'

export function ShelfManagementPage() {
  const [dataList, setDataList] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingRecord, setEditingRecord] = useState<any | null>(null)
  const [form] = Form.useForm()

  // Slot drawer
  const [slotDrawerOpen, setSlotDrawerOpen] = useState(false)
  const [slotData, setSlotData] = useState<any[]>([])
  const [slotLoading, setSlotLoading] = useState(false)
  const [selectedShelf, setSelectedShelf] = useState<any | null>(null)
  const [extendedSlotData, setExtendedSlotData] = useState<any[]>([])

  // Slot create/edit modal
  const [slotModalOpen, setSlotModalOpen] = useState(false)
  const [editingSlot, setEditingSlot] = useState<any | null>(null)
  const [slotForm] = Form.useForm()

  const loadData = async () => {
    setLoading(true)
    try {
      const res = await getShelvesApi()
      setDataList(res.data?.data || res.data || [])
    } catch {
      message.error('加载料架数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const openCreateModal = () => {
    setEditingRecord(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEditModal = (record: any) => {
    setEditingRecord(record)
    form.setFieldsValue(record)
    setModalOpen(true)
  }

  const handleSaveShelf = async (values: any) => {
    try {
      if (editingRecord) {
        await updateShelfApi(editingRecord.id, values)
        message.success('料架更新成功')
      } else {
        await createShelfApi(values)
        message.success('料架创建成功')
      }
      setModalOpen(false)
      form.resetFields()
      loadData()
    } catch {
      message.error(editingRecord ? '更新料架失败' : '创建料架失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteShelfApi(id)
      message.success('料架已禁用')
      loadData()
    } catch {
      message.error('禁用料架失败')
    }
  }

  // ── 储位 drawer ──

  const loadSlots = async (shelf: any) => {
    setSlotLoading(true)
    try {
      const res = await getShelfSlotsApi(shelf.id)
      setSlotData(res.data?.data || res.data || [])
    } catch {
      message.error('加载储位数据失败')
      setSlotData([])
    } finally {
      setSlotLoading(false)
    }
  }

  const loadExtendedStates = async (shelfId: number) => {
    try {
      const extRes = await getSlotStatesExtendedApi(shelfId)
      setExtendedSlotData(extRes.data?.cells || [])
    } catch {
      setExtendedSlotData([])
    }
  }

  const handleViewSlots = async (record: any) => {
    setSelectedShelf(record)
    setSlotDrawerOpen(true)
    await loadSlots(record)
    // 尝试加载扩展状态（可能无 API 配置）
    loadExtendedStates(record.id)
  }

  const handleRackTest = async (record: any) => {
    try {
      const res = await rackTestApi(record.id, 15)
      message.success(`灯测试指令已发送`)
    } catch {
      message.error('灯测试调用失败，请检查控灯服务')
    }
  }

  // ── 储位创建/编辑 ──

  const openCreateSlot = () => {
    setEditingSlot(null)
    slotForm.resetFields()
    slotForm.setFieldsValue({ side: 'A' })
    setSlotModalOpen(true)
  }

  const openEditSlot = (slot: any) => {
    setEditingSlot(slot)
    slotForm.setFieldsValue(slot)
    setSlotModalOpen(true)
  }

  const handleSaveSlot = async (values: any) => {
    if (!selectedShelf) return
    try {
      if (editingSlot) {
        await updateSlotApi(selectedShelf.id, editingSlot.id, values)
        message.success('储位更新成功')
      } else {
        await createSlotApi(selectedShelf.id, values)
        message.success('储位创建成功')
      }
      setSlotModalOpen(false)
      slotForm.resetFields()
      await loadSlots(selectedShelf)
    } catch {
      message.error(editingSlot ? '更新储位失败' : '创建储位失败')
    }
  }

  const handleDeleteSlot = async (slotId: number) => {
    if (!selectedShelf) return
    try {
      await deleteSlotApi(selectedShelf.id, slotId)
      message.success('储位已删除')
      await loadSlots(selectedShelf)
    } catch {
      message.error('删除储位失败')
    }
  }

  // ── 表格列定义 ──

  const columns = [
    { title: '料架编号', dataIndex: 'code', key: 'code', width: 120 },
    { title: '名称', dataIndex: 'name', key: 'name', width: 150 },
    { title: '位置', dataIndex: 'location', key: 'location', width: 120 },
    { title: '储位数', dataIndex: 'slot_count', key: 'slot_count', width: 80 },
    {
      title: '状态',
      dataIndex: 'active',
      key: 'active',
      width: 70,
      render: (active: number) =>
        active !== 0 ? <Tag color="green">启用</Tag> : <Tag color="red">禁用</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 280,
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewSlots(record)}>
            储位
          </Button>
          <Button type="link" size="small" icon={<ThunderboltOutlined />} onClick={() => handleRackTest(record)}>
            灯测试
          </Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEditModal(record)} />
          <Popconfirm title="确认禁用该料架？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const slotColumns = [
    { title: '面', dataIndex: 'side', key: 'side', width: 50 },
    { title: '板上编号', dataIndex: 'slot_on_board', key: 'slot_on_board', width: 80 },
    { title: 'cell_id', dataIndex: 'cell_id', key: 'cell_id', width: 150 },
    { title: '最大容量', dataIndex: 'max_quantity', key: 'max_quantity', width: 80 },
    {
      title: '传感器',
      dataIndex: 'last_sensor_state',
      key: 'last_sensor_state',
      width: 70,
      render: (v: number) => (v ? <Tag color="red">有料</Tag> : <Tag color="green">空</Tag>),
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEditSlot(record)} />
          <Popconfirm title="确认删除该储位？" onConfirm={() => handleDeleteSlot(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      {/* ── 料架列表 ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>料架管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
          新建料架
        </Button>
      </div>
      <Spin spinning={loading}>
        <Table columns={columns} dataSource={dataList} pagination={false} rowKey="id" />
      </Spin>

      {/* ── 料架新增/编辑弹窗 ── */}
      <Modal
        title={editingRecord ? '编辑料架' : '新建料架'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); form.resetFields() }}
        footer={null}
        width={480}
      >
        <Form form={form} layout="vertical" onFinish={handleSaveShelf}>
          <Form.Item name="code" label="料架编号（同时也是通信编号）" rules={[{ required: true }]}>
            <Input placeholder="如 SMT01" />
          </Form.Item>
          <Form.Item name="name" label="料架名称">
            <Input placeholder="如 SMT 主料架 A" />
          </Form.Item>
          <Form.Item name="location" label="安装位置">
            <Input placeholder="如 产线 1 号" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">保存</Button>
              <Button onClick={() => { setModalOpen(false); form.resetFields() }}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* ── 储位抽屉 ── */}
      <Drawer
        title={`${selectedShelf?.code || ''} - 储位列表`}
        open={slotDrawerOpen}
        onClose={() => setSlotDrawerOpen(false)}
        width={900}
      >
        {/* 实时状态 */}
        {extendedSlotData.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <h4>实时储位状态（来自控灯 API）</h4>
            <Table
              columns={[
                { title: '储位号', dataIndex: 'cellId', key: 'cellId', width: 100 },
                { title: '占用', dataIndex: 'used', key: 'used', width: 60, render: (v: any) => v ? <Tag color="red">占用</Tag> : <Tag color="green">空</Tag> },
                { title: '灯色', dataIndex: 'ledColor', key: 'ledColor', width: 60 },
                { title: '闪烁', dataIndex: 'blink', key: 'blink', width: 60, render: (v: any) => v ? '是' : '否' },
                { title: '电量(V)', dataIndex: 'electricitys', key: 'electricitys', width: 80, render: (v: any) => {
                  const val = Number(v)
                  return val > 0 ? <span style={{ color: val < 2.5 ? 'red' : 'green' }}>{val}</span> : '-'
                }},
              ]}
              dataSource={extendedSlotData}
              pagination={false}
              rowKey="cellId"
              size="small"
            />
          </div>
        )}

        <Spin spinning={slotLoading}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <h4>储位列表</h4>
            <Button type="primary" size="small" icon={<PlusOutlined />} onClick={openCreateSlot}>
              新增储位
            </Button>
          </div>
          <Table
            columns={slotColumns}
            dataSource={slotData}
            pagination={false}
            rowKey="id"
            size="small"
          />
        </Spin>
      </Drawer>

      {/* ── 储位新增/编辑弹窗 ── */}
      <Modal
        title={editingSlot ? '编辑储位' : '新增储位'}
        open={slotModalOpen}
        onCancel={() => { setSlotModalOpen(false); slotForm.resetFields() }}
        footer={null}
        width={480}
      >
        <Form form={slotForm} layout="vertical" onFinish={handleSaveSlot}>
          <Form.Item name="side" label="面" rules={[{ required: true }]}>
            <Select>
              <Select.Option value="A">A 面</Select.Option>
              <Select.Option value="B">B 面</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="slot_on_board" label="板上编号" rules={[{ required: true }]}>
            <InputNumber min={1} style={{ width: '100%' }} placeholder="如 1, 2, 3..." />
          </Form.Item>
          <Form.Item name="max_quantity" label="最大容量">
            <InputNumber min={0} style={{ width: '100%' }} placeholder="空=不限制" />
          </Form.Item>
          {selectedShelf && !editingSlot && (
            <div style={{ color: '#888', fontSize: 12, marginBottom: 12 }}>
              cell_id 将自动生成为: <strong>{selectedShelf.code || '?'}{slotForm.getFieldValue('side') || '?'}{String(slotForm.getFieldValue('slot_on_board') || '').padStart(4, '0')}</strong>
            </div>
          )}
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">保存</Button>
              <Button onClick={() => { setSlotModalOpen(false); slotForm.resetFields() }}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
