import { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, Space, Tag, Popconfirm, Spin, message, Drawer } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons'
import { getShelvesApi, createShelfApi, updateShelfApi, deleteShelfApi, getShelfSlotsApi } from '../api'

export function ShelfManagementPage() {
  const [dataList, setDataList] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingRecord, setEditingRecord] = useState<any | null>(null)
  const [form] = Form.useForm()
  const [slotDrawerOpen, setSlotDrawerOpen] = useState(false)
  const [slotData, setSlotData] = useState<any[]>([])
  const [slotLoading, setSlotLoading] = useState(false)
  const [selectedShelf, setSelectedShelf] = useState<any | null>(null)

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

  const handleSave = async (values: any) => {
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
      message.success('料架已删除')
      loadData()
    } catch {
      message.error('删除料架失败')
    }
  }

  const handleViewSlots = async (record: any) => {
    setSelectedShelf(record)
    setSlotDrawerOpen(true)
    setSlotLoading(true)
    try {
      const res = await getShelfSlotsApi(record.id)
      setSlotData(res.data?.data || res.data || [])
    } catch {
      message.error('加载储位数据失败')
    } finally {
      setSlotLoading(false)
    }
  }

  const columns = [
    { title: '料架编号', dataIndex: 'code', key: 'code', width: 120 },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: 'A 面板', dataIndex: 'a_sides', key: 'a_sides', width: 80 },
    { title: 'B 面版', dataIndex: 'b_sides', key: 'b_sides', width: 80 },
    { title: '总槽位', dataIndex: 'total_slots', key: 'total_slots', width: 80 },
    { title: '控制器 IP', dataIndex: 'controller_ip', key: 'controller_ip', width: 150 },
    { title: '位置', dataIndex: 'location', key: 'location', width: 150 },
    {
      title: '状态',
      dataIndex: 'active',
      key: 'active',
      width: 80,
      render: (active: boolean) =>
        active !== false ? <Tag color="green">在线</Tag> : <Tag color="red">离线</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewSlots(record)}>
            储位
          </Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEditModal(record)} />
          <Popconfirm
            title="确认删除该料架？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>料架管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
          新建料架
        </Button>
      </div>
      <Spin spinning={loading}>
        <Table
          columns={columns}
          dataSource={dataList}
          pagination={false}
          rowKey="code"
        />
      </Spin>
      <Modal
        title={editingRecord ? '编辑料架' : '新建料架'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); form.resetFields() }}
        footer={null}
      >
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="code" label="料架编号" rules={[{ required: true }]}>
            <Input placeholder="如 SH-001" />
          </Form.Item>
          <Form.Item name="name" label="料架名称">
            <Input placeholder="如 SMT 主料架 A" />
          </Form.Item>
          <Form.Item name="a_sides" label="A 面 LED 面板数">
            <Input type="number" defaultValue={1} />
          </Form.Item>
          <Form.Item name="b_sides" label="B 面 LED 面板数">
            <Input type="number" defaultValue={1} />
          </Form.Item>
          <Form.Item name="controller_ip" label="控制器 IP">
            <Input placeholder="如 192.168.1.100" />
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
      <Drawer
        title={`${selectedShelf?.code || ''} - 储位列表`}
        open={slotDrawerOpen}
        onClose={() => setSlotDrawerOpen(false)}
        width={600}
      >
        <Spin spinning={slotLoading}>
          <Table
            columns={[
              { title: '位置', dataIndex: 'global_index', key: 'global_index', width: 80 },
              { title: '面', dataIndex: 'side', key: 'side', width: 60 },
              { title: '面板地址', dataIndex: 'board_address', key: 'board_address', width: 100 },
              { title: '板上槽号', dataIndex: 'slot_on_board', key: 'slot_on_board', width: 100 },
              { title: 'Modbus TCP ID', dataIndex: 'modbus_tcp_id', key: 'modbus_tcp_id', width: 120 },
              { title: '线圈基址', dataIndex: 'modbus_coil_base', key: 'modbus_coil_base', width: 100 },
            ]}
            dataSource={slotData}
            pagination={false}
            rowKey="id"
            size="small"
          />
        </Spin>
      </Drawer>
    </div>
  )
}
