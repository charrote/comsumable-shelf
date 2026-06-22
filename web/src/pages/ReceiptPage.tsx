import { useState, useEffect, useRef } from 'react'
import { Table, Button, Card, Space, Tag, Modal, Form, Input, InputNumber, Select, message, Descriptions, Typography, Spin, Row, Col, Statistic, Popconfirm, Radio } from 'antd'
import { ScanOutlined, PlusOutlined, PrinterOutlined, CheckCircleOutlined, CloseCircleOutlined, HistoryOutlined } from '@ant-design/icons'
import { createReceiptApi, scanReceiptApi, getReceiptListApi, getReceiptApi, confirmReceiptApi, reprintLabelApi, getMaterialsApi, scanPreviewApi } from '../api'

const { Text, Title } = Typography

const statusLabels: Record<string, string> = { draft: '草稿', confirmed: '已确认', completed: '已完成' }
const statusColors: Record<string, string> = { draft: 'default', confirmed: 'blue', completed: 'green' }

export function ReceiptPage() {
  const [receipts, setReceipts] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [createModal, setCreateModal] = useState(false)
  const [createForm] = Form.useForm()
  const [currentReceipt, setCurrentReceipt] = useState<any>(null)
  const [detailModal, setDetailModal] = useState(false)
  const [reprintModal, setReprintModal] = useState(false)
  const [reprintReelList, setReprintReelList] = useState<any[]>([])
  const [materials, setMaterials] = useState<any[]>([])

  // ── Scan Preview Flow ──
  const barcodeInputRef = useRef<any>(null)
  const [showScanModal, setShowScanModal] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [previewData, setPreviewData] = useState<any>(null)
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null)
  const [editQty, setEditQty] = useState<number>(1)
  const [editBatch, setEditBatch] = useState('')
  const [editDateCode, setEditDateCode] = useState('')
  const [editSpec, setEditSpec] = useState('')
  const [isNewMaterial, setIsNewMaterial] = useState(false)
  const [newCode, setNewCode] = useState('')
  const [newName, setNewName] = useState('')

  const loadReceipts = async () => {
    setLoading(true)
    try {
      const res = await getReceiptListApi()
      setReceipts(res.data?.data || res.data || [])
    } catch { message.error('加载收料单失败') }
    finally { setLoading(false) }
  }

  useEffect(() => { loadReceipts(); loadMaterials() }, [])

  const loadMaterials = async () => {
    try {
      const res = await getMaterialsApi({})
      setMaterials(res.data?.data || res.data || [])
    } catch {}
  }

  const handleCreate = async (values: any) => {
    try {
      const res = await createReceiptApi({ type: 'normal', operator: values.operator, customer_id: 1 })
      message.success(`收料单 ${res.data.receipt_no} 创建成功`)
      setCreateModal(false)
      createForm.resetFields()
      loadReceipts()
      startScan(res.data.id)
    } catch (e: any) { message.error(e.response?.data?.detail || '创建失败') }
  }

  const startScan = (receiptId?: number) => {
    const id = receiptId || currentReceipt?.id
    if (!id) { message.error('请先选择收料单'); return }
    setShowScanModal(true)
    setPreviewData(null)
    setSelectedMaterialId(null)
    setIsNewMaterial(false)
    setTimeout(() => barcodeInputRef.current?.focus(), 100)
  }

  const handleBarcodeScan = async (barcode: string) => {
    if (!barcode || !currentReceipt?.id) return
    setScanning(true)
    try {
      // Step 1: Preview scan — parse barcode and return candidates + extracted fields
      const previewRes = await scanPreviewApi(currentReceipt.id, {
        barcode, operator: 'admin', qty: 1,
      })
      const data = previewRes.data

      if (data.status === 'ok') {
        // Auto-matched with high confidence — confirm directly
        const confirmRes = await scanReceiptApi(currentReceipt.id, {
          barcode, operator: 'admin', qty: 1,
        })
        const confirmData = confirmRes.data
        if (confirmData.status === 'ok') {
          message.success(`入库成功！Reel#${confirmData.reel_id} ${confirmData.message || ''}`)
          loadReceiptDetail()
          setShowScanModal(false)
        } else {
          message.warning(confirmData.message || '入库结果异常')
        }
      } else {
        // Need user review — show preview
        setPreviewData({
          barcode,
          material_code: data.material_code || barcode,
          material_name: data.material_name || '',
          quantity: data.quantity || 1,
          batch_no: data.batch_no || '',
          date_code: data.date_code || '',
          spec: data.spec || '',
          candidates: data.candidates || [],
          status: data.status,
          message: data.message,
        })
        setEditQty(data.quantity || 1)
        setEditBatch(data.batch_no || '')
        setEditDateCode(data.date_code || '')
        setEditSpec(data.spec || '')
        setNewCode(data.material_code || barcode)
        setNewName(data.material_name || '')
        setSelectedMaterialId(data.candidates?.[0]?.material_id || null)
        setIsNewMaterial(data.status === 'new_material')
      }
    } catch (e: any) {
      message.error(e.response?.data?.detail || '扫码失败')
    } finally { setScanning(false) }
  }

  const handleConfirmScan = async (barcode: string, force = false) => {
    if (!currentReceipt?.id) return
    setScanning(true)
    try {
      const payload: any = {
        barcode,
        operator: 'admin',
        qty: editQty,
        batch_no: editBatch || undefined,
        date_code: editDateCode || undefined,
      }
      if (isNewMaterial) {
        payload.is_new_material = true
        payload.new_material_code = newCode || barcode
        payload.new_material_name = newName || newCode || barcode
      } else if (selectedMaterialId) {
        payload.manual_material_id = selectedMaterialId
      } else if (previewData?.candidates?.[0]) {
        payload.manual_material_id = previewData.candidates[0].material_id
      }

      const res = await scanReceiptApi(currentReceipt.id, payload)
      const data = res.data
      if (data.status === 'ok') {
        message.success(`入库成功！Reel#${data.reel_id} ${data.message || ''}`)
        loadReceiptDetail()
        setShowScanModal(false)
      } else {
        message.warning(data.message || '入库结果异常')
      }
    } catch (e: any) {
      message.error(e.response?.data?.detail || '确认失败')
    } finally { setScanning(false) }
  }

  const loadReceiptDetail = async () => {
    if (!currentReceipt?.id) return
    try {
      const res = await getReceiptApi(currentReceipt.id)
      setCurrentReceipt(res.data)
    } catch {}
  }

  const selectReceipt = async (record: any) => {
    try {
      const res = await getReceiptApi(record.id)
      setCurrentReceipt(res.data)
      setDetailModal(true)
    } catch { message.error('加载收料单详情失败') }
  }

  const handleConfirm = async () => {
    if (!currentReceipt?.id) return
    try {
      await confirmReceiptApi(currentReceipt.id)
      message.success('收料单已确认')
      loadReceiptDetail()
      loadReceipts()
    } catch (e: any) { message.error(e.response?.data?.detail || '确认失败') }
  }

  const handleReprint = async (receiptReelId: number) => {
    if (!currentReceipt?.id) return
    try {
      const res = await reprintLabelApi(currentReceipt.id, { receipt_reel_id: receiptReelId })
      if (res.data?.printed) message.success('标签已重新打印')
      else message.warning(res.data?.message || '打印失败')
    } catch (e: any) { message.error(e.response?.data?.detail || '重打失败') }
  }

  const columns = [
    { title: '收料单号', dataIndex: 'receipt_no', key: 'receipt_no', width: 180 },
    { title: '操作员', dataIndex: 'operator', key: 'operator', width: 100 },
    { title: '类型', dataIndex: 'type', key: 'type', width: 80 },
    { title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => <Tag color={statusColors[v]}>{statusLabels[v]}</Tag>,
    },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (v: string) => v ? new Date(v).toLocaleString() : '-',
    },
    { title: '操作', key: 'action', width: 160,
      render: (_: any, r: any) => (
        <Space>
          <Button type="link" size="small" onClick={() => selectReceipt(r)}>详情</Button>
          {r.status === 'draft' && (
            <Button type="link" size="small" icon={<ScanOutlined />} onClick={() => { selectReceipt(r).then(() => startScan(r.id)) }}>扫码</Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>收料管理</h2>
        <Space>
          <Button icon={<HistoryOutlined />} onClick={() => setReprintModal(true)}>标签重打</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModal(true)}>新建收料单</Button>
        </Space>
      </div>

      <Table columns={columns} dataSource={receipts} rowKey="id" loading={loading} pagination={{ pageSize: 20 }} />

      <Modal title="新建收料单" open={createModal} onCancel={() => { setCreateModal(false); createForm.resetFields() }} onOk={() => createForm.submit()}>
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="operator" label="操作员" rules={[{ required: true }]}>
            <Input placeholder="操作员姓名" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title={`收料单详情 - ${currentReceipt?.receipt_no || ''}`} open={detailModal} onCancel={() => setDetailModal(false)} width={700} footer={null}>
        {currentReceipt && (
          <div>
            <Descriptions column={3} size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="状态"><Tag color={statusColors[currentReceipt.status]}>{statusLabels[currentReceipt.status]}</Tag></Descriptions.Item>
              <Descriptions.Item label="类型">{currentReceipt.type}</Descriptions.Item>
              <Descriptions.Item label="操作员">{currentReceipt.operator}</Descriptions.Item>
              <Descriptions.Item label="创建时间">{currentReceipt.created_at ? new Date(currentReceipt.created_at).toLocaleString() : '-'}</Descriptions.Item>
            </Descriptions>
            <Table
              dataSource={currentReceipt.items || []} rowKey="id" size="small" pagination={false}
              columns={[
                { title: '物料', dataIndex: 'material_code', key: 'material_code' },
                { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 80,
                  render: (v: number, r: any) => `${v} ${r.material_unit || '盘'}`,
                },
                { title: 'Reel#', dataIndex: 'reel_id', key: 'reel_id', width: 80 },
                { title: '条码', dataIndex: 'barcode', key: 'barcode', ellipsis: true },
                { title: '标签', dataIndex: 'internal_label_printed', key: 'label', width: 80,
                  render: (v: boolean, r: any) => (
                    <Space>
                      <Tag color={v ? 'green' : 'default'}>{v ? '已打' : '未打'}</Tag>
                      <Button type="link" size="small" icon={<PrinterOutlined />} onClick={() => handleReprint(r.id)} />
                    </Space>
                  ),
                },
              ]}
            />
            <Space style={{ marginTop: 16 }}>
              {currentReceipt.status === 'draft' && (
                <>
                  <Button icon={<ScanOutlined />} onClick={() => startScan()}>扫码入库</Button>
                  <Popconfirm title="确认该收料单？确认后不可修改" onConfirm={handleConfirm}>
                    <Button type="primary" icon={<CheckCircleOutlined />}>确认收料</Button>
                  </Popconfirm>
                </>
              )}
            </Space>
          </div>
        )}
      </Modal>

      <Modal title="标签重打" open={reprintModal} onCancel={() => setReprintModal(false)} width={600} footer={null}>
        <Table
          dataSource={receipts.filter(r => r.status !== 'draft')} rowKey="id" size="small" pagination={false}
          columns={[
            { title: '收料单号', dataIndex: 'receipt_no', key: 'receipt_no', width: 180 },
            { title: '状态', dataIndex: 'status', key: 'status', width: 80,
              render: (v: string) => <Tag color={statusColors[v]}>{statusLabels[v]}</Tag>,
            },
            { title: '操作', key: 'action', width: 100,
              render: (_: any, r: any) => (
                <Button size="small" icon={<PrinterOutlined />} onClick={async () => {
                  try {
                    const detail = await getReceiptApi(r.id)
                    const items = detail.data?.items || []
                    if (items.length === 0) { message.warning('该收料单没有明细'); return }
                    Modal.confirm({
                      title: '选择要重打的标签',
                      content: (
                        <div>
                          {items.map((item: any) => (
                            <div key={item.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                              <span>Reel#{item.reel_id} - {item.material_code || item.material_name || '-'}</span>
                              <Button size="small" icon={<PrinterOutlined />} onClick={() => reprintLabelApi(r.id, { receipt_reel_id: item.id }).then(res => {
                                if (res.data?.printed) message.success('重打成功')
                                else message.warning(res.data?.message || '打印失败')
                              })}>打印</Button>
                            </div>
                          ))}
                        </div>
                      ),
                      okButtonProps: { style: { display: 'none' } },
                    })
                  } catch { message.error('加载详情失败') }
                }}>选择</Button>
              ),
            },
          ]}
        />
      </Modal>

      <Modal
        title="扫码入库确认"
        open={showScanModal}
        onCancel={() => setShowScanModal(false)}
        onOk={() => {
          if (!currentReceipt?.id) return
          const bc = previewData?.barcode || ''
          handleConfirmScan(bc)
        }}
        confirmLoading={scanning}
        width={650}
      >
        <Form layout="vertical">
          <Form.Item label="扫描条码">
            <Input.Search
              ref={barcodeInputRef}
              placeholder="扫描供应商条码..."
              enterButton={<ScanOutlined />}
              loading={scanning}
              onSearch={handleBarcodeScan}
              autoFocus
            />
          </Form.Item>
        </Form>

        {previewData && (
          <Card title="条码解析结果" size="small" style={{ marginTop: 16 }}>
            <Descriptions column={2} size="small">
              <Descriptions.Item label="条码">{previewData.barcode}</Descriptions.Item>
              <Descriptions.Item label="匹配状态">
                <Tag color={previewData.status === 'ok' ? 'green' : 'orange'}>
                  {previewData.status === 'ok' ? '自动匹配' : previewData.status === 'new_material' ? '新料号' : '待确认'}
                </Tag>
              </Descriptions.Item>
            </Descriptions>
            <div style={{ marginTop: 8, background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
              {previewData.status === 'ok' ? (
                <p style={{ color: '#52c41a', margin: 0 }}>{previewData.message}</p>
              ) : previewData.status === 'new_material' ? (
                <div>
                  <Form layout="inline" size="small">
                    <Form.Item label="新料号">
                      <Input value={newCode} onChange={e => setNewCode(e.target.value)} placeholder={previewData.material_code} style={{ width: 180 }} />
                    </Form.Item>
                    <Form.Item label="名称">
                      <Input value={newName} onChange={e => setNewName(e.target.value)} placeholder="新物料名称" style={{ width: 180 }} />
                    </Form.Item>
                  </Form>
                </div>
              ) : (
                <div>
                  <Text strong>匹配候选项：</Text>
                  <Radio.Group onChange={e => {
                      if (e.target.value === -1) {
                        setIsNewMaterial(true)
                        setSelectedMaterialId(null)
                      } else {
                        setIsNewMaterial(false)
                        setSelectedMaterialId(e.target.value)
                      }
                    }} value={isNewMaterial ? -1 : selectedMaterialId}>
                    <Space direction="vertical" style={{ width: '100%', marginTop: 8 }}>
                      {previewData.candidates?.map((c: any) => (
                        <Radio key={c.material_id} value={c.material_id}>
                          <Space>
                            <Text strong>{c.code}</Text>
                            <Text type="secondary">{c.name}</Text>
                            <Tag color={c.confidence >= 0.8 ? 'green' : c.confidence >= 0.5 ? 'orange' : 'red'}>
                              {(c.confidence * 100).toFixed(0)}%
                            </Tag>
                          </Space>
                        </Radio>
                      ))}
                      <Radio value={-1}>
                        <Text>其他（新建料号）</Text>
                      </Radio>
                    </Space>
                  </Radio.Group>
                </div>
              )}
            </div>

            <div style={{ marginTop: 12 }}>
              <Text strong>可编辑字段：</Text>
              <Row gutter={16} style={{ marginTop: 8 }}>
                <Col span={8}>
                  <Form.Item label="数量" style={{ marginBottom: 0 }}>
                    <InputNumber min={0.01} value={editQty} onChange={v => setEditQty(v || 1)} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="批次号" style={{ marginBottom: 0 }}>
                    <Input value={editBatch} onChange={e => setEditBatch(e.target.value)} placeholder="从条码解析" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="生产周期" style={{ marginBottom: 0 }}>
                    <Input value={editDateCode} onChange={e => setEditDateCode(e.target.value)} placeholder="如：2401" />
                  </Form.Item>
                </Col>
              </Row>
            </div>
          </Card>
        )}
      </Modal>
    </div>
  )
}
