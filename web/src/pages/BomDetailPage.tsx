import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Button, Tree, Modal, Form, Input, InputNumber, Select, Space, message,
  Popconfirm, Tag, Typography, Descriptions, Divider, Empty, Spin,
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, EditOutlined, ArrowLeftOutlined,
  SaveOutlined, SwapOutlined,
} from '@ant-design/icons'
import {
  getBomApi, updateBomApi, addBomItemApi, updateBomItemApi, deleteBomItemApi,
  getMaterialsApi,
} from '../api'

const { Title, Text } = Typography

interface BomItem {
  id?: number
  parent_id?: number | null
  material_id: number
  material_code?: string
  material_name?: string
  material_unit?: string
  quantity: number
  position: number
  remark?: string
  alternatives: any[]
  children: BomItem[]
}

export function BomDetailPage() {
  const { bomId } = useParams<{ bomId: string }>()
  const navigate = useNavigate()
  const [bom, setBom] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [materials, setMaterials] = useState<any[]>([])
  const [fetching, setFetching] = useState(false)
  const [itemModalVisible, setItemModalVisible] = useState(false)
  const [editingItem, setEditingItem] = useState<BomItem | null>(null)
  const [parentId, setParentId] = useState<number | null>(null)
  const [altModalVisible, setAltModalVisible] = useState(false)
  const [editingAltItem, setEditingAltItem] = useState<BomItem | null>(null)
  const [itemForm] = Form.useForm()
  const [altForm] = Form.useForm()

  const timerRef = useRef<any>(null)

  const fetchMaterials = async (keyword?: string) => {
    setFetching(true)
    try {
      const res = await getMaterialsApi(keyword ? { keyword } : {})
      setMaterials(res.data?.data || res.data || [])
    } catch {
      message.error('加载物料失败')
    } finally {
      setFetching(false)
    }
  }

  const handleSearch = (value: string) => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
    }
    timerRef.current = setTimeout(() => {
      fetchMaterials(value)
    }, 500)
  }

  const handleMaterialChange = (value: number) => {
    const selectedMat = materials.find((m: any) => m.id === value)
    if (selectedMat) {
      itemForm.setFieldsValue({
        material_unit: selectedMat.unit || '盘'
      })
    }
  }

  useEffect(() => {
    if (bomId) {
      fetchBom()
      fetchMaterials()
    }
  }, [bomId])

  const fetchBom = async () => {
    setLoading(true)
    try {
      const res = await getBomApi(Number(bomId))
      setBom(res.data)
    } catch (e) {
      message.error('获取BOM详情失败')
    } finally {
      setLoading(false)
    }
  }

  const handleAddItem = (parentId: number | null = null) => {
    setParentId(parentId)
    setEditingItem(null)
    itemForm.resetFields()
    itemForm.setFieldsValue({ quantity: 1, position: 0, alternatives: [] })
    setItemModalVisible(true)
  }

  const handleEditItem = (item: BomItem) => {
    setEditingItem(item)
    setParentId(item.parent_id || null)
    itemForm.setFieldsValue({
      material_id: item.material_id,
      quantity: item.quantity,
      position: item.position,
      remark: item.remark,
      material_unit: item.material_unit,
    })
    setItemModalVisible(true)
  }

  const handleSaveItem = async (values: any) => {
    const data: any = {
      parent_id: parentId,
      material_id: values.material_id,
      quantity: values.quantity,
      position: values.position || 0,
      remark: values.remark,
      alternatives: editingItem?.alternatives || [],
    }
    try {
      if (editingItem?.id) {
        await updateBomItemApi(Number(bomId), editingItem.id, data)
        message.success('明细已更新')
      } else {
        await addBomItemApi(Number(bomId), data)
        message.success('明细已添加')
      }
      setItemModalVisible(false)
      fetchBom()
    } catch (e: any) {
      message.error(e.response?.data?.detail || '保存失败')
    }
  }

  const handleSaveAlt = async (values: any) => {
    if (!editingAltItem?.id) return
    const newAlternative = {
      material_id: values.alternative_material_id,
      priority: values.priority,
      percentage: values.percentage,
    }
    try {
      const data = {
        alternatives: [...(editingAltItem.alternatives || []), newAlternative],
      }
      await updateBomItemApi(Number(bomId), editingAltItem.id, data)
      message.success('替代料已添加')
      setAltModalVisible(false)
      fetchBom()
    } catch (e: any) {
      message.error(e.response?.data?.detail || '保存失败')
    }
  }

  const handleDeleteItem = async (itemId: number) => {
    try {
      await deleteBomItemApi(Number(bomId), itemId)
      message.success('明细已删除')
      fetchBom()
    } catch (e: any) {
      message.error(e.response?.data?.detail || '删除失败')
    }
  }

  const flattenItems = (items: BomItem[]): BomItem[] => {
    const result: BomItem[] = []
    const walk = (list: BomItem[]) => {
      for (const item of list) {
        result.push(item)
        if (item.children?.length) walk(item.children)
      }
    }
    walk(items)
    return result
  }

  const buildTreeData = (items: BomItem[]): any[] => {
    function handleAddAlt(item: BomItem): void {
      setEditingAltItem(item)
      altForm.resetFields()
      altForm.setFieldsValue({ priority: 1, percentage: 100 })
      setAltModalVisible(true)
    }

    return items.map(item => ({
      key: item.id,
      title: (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
          <Text strong>{item.material_code}</Text>
          <Text type="secondary">{item.material_name}</Text>
          <Tag>{item.quantity} {item.material_unit}</Tag>
          {item.remark && <Text type="secondary" style={{ fontSize: 12 }}>({item.remark})</Text>}
          {item.alternatives?.length > 0 && (
            <Tag color="orange" style={{ fontSize: 11 }}>
              <SwapOutlined />
              {item.alternatives.length}个替代料
            </Tag>
          )}
          <Space size={4} onClick={(e) => e.stopPropagation()}>
            <Button type="link" size="small" icon={<PlusOutlined />} onClick={() => handleAddItem(item.id!)}>子项</Button>
            <Button type="link" size="small" icon={<SwapOutlined />} onClick={() => handleAddAlt(item)}>替代</Button>
            <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEditItem(item)} />
            <Popconfirm title="确定删除？子项也会被删除" onConfirm={() => handleDeleteItem(item.id!)}>
              <Button type="link" size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Space>
        </div>
      ),
      children: item.children?.length ? buildTreeData(item.children) : [],
    }))
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
  if (!bom) return <Empty description="BOM不存在" />

  const treeData = buildTreeData(bom.items || [])
  const allItems = flattenItems(bom.items || [])

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/bom')}>返回列表</Button>
      </Space>

      <Card style={{ marginBottom: 16 }}>
        <Descriptions column={4} size="small">
          <Descriptions.Item label="产品编码"><Text strong>{bom.product_code}</Text></Descriptions.Item>
          <Descriptions.Item label="产品名称">{bom.product_name}</Descriptions.Item>
          <Descriptions.Item label="版本">{bom.version}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={bom.status === 'active' ? 'green' : bom.status === 'obsolete' ? 'red' : 'default'}>
              {bom.status === 'draft' ? '草稿' : bom.status === 'active' ? '生效' : bom.status === 'obsolete' ? '废弃' : bom.status}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="客户">{bom.customer_name}</Descriptions.Item>
          <Descriptions.Item label="描述">{bom.description || '-'}</Descriptions.Item>
          <Descriptions.Item label="明细数">{allItems.length}</Descriptions.Item>
          <Descriptions.Item label="更新时间">{bom.updated_at ? new Date(bom.updated_at).toLocaleString() : '-'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card
        title="BOM树形结构"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => handleAddItem(null)}>
            添加根物料
          </Button>
        }
      >
        {treeData.length > 0 ? (
          <Tree
            treeData={treeData}
            defaultExpandAll
            blockNode
            style={{ fontSize: 14 }}
          />
        ) : (
          <Empty description="暂无BOM明细，点击上方按钮添加" />
        )}
      </Card>

      <Modal
        title={editingItem ? '编辑BOM明细' : '添加BOM明细'}
        open={itemModalVisible}
        onCancel={() => setItemModalVisible(false)}
        onOk={() => itemForm.submit()}
        width={500}
      >
        <Form form={itemForm} layout="vertical" onFinish={handleSaveItem}>
          <Form.Item name="material_id" label="物料" rules={[{ required: true, message: '请选择物料' }]}>
            <Select
              showSearch
              optionFilterProp="label"
              options={materials.map((m: any) => ({ value: m.id, label: `${m.code} - ${m.name} (${m.unit})` }))}
              onChange={handleMaterialChange}
              onSearch={handleSearch}
              notFoundContent={fetching ? <Spin size="small" /> : <Empty description="无匹配物料" />}>
            </Select>
          </Form.Item>
          <Form.Item name="quantity" label="数量" rules={[{ required: true, message: '请输入数量' }]}>
            <InputNumber min={0.01} step={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="position" label="排序">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input placeholder="备注（可选）" />
          </Form.Item>
          <Form.Item name="material_unit" label="单位">
            <Input disabled />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="添加替代料"
        open={altModalVisible}
        onCancel={() => setAltModalVisible(false)}
        onOk={() => altForm.submit()}
        width={500}
      >
        <Form form={altForm} layout="vertical" onFinish={handleSaveAlt}>
          <Form.Item name="alternative_material_id" label="替代物料" rules={[{ required: true, message: '请选择替代物料' }]}>
            <Select
              placeholder="选择替代物料"
              showSearch
              optionFilterProp="label"
              options={materials.map((m: any) => ({ value: m.id, label: `${m.code} - ${m.name}` }))}
            />
          </Form.Item>
          <Form.Item name="priority" label="优先级" rules={[{ required: true }]}>
            <InputNumber min={1} max={99} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="percentage" label="替代百分比(%)" rules={[{ required: true }]}>
            <InputNumber min={0} max={100} step={5} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
