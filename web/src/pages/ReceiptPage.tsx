import { useState, useEffect, useRef } from 'react'
import { Table, Button, Card, Space, Tag, Modal, Form, Input, InputNumber, Select, Checkbox, message, Descriptions, Typography, Spin, Row, Col, Statistic, Popconfirm, Radio } from 'antd'
import { ScanOutlined, PlusOutlined, PrinterOutlined, CheckCircleOutlined, CloseCircleOutlined, HistoryOutlined, DeleteOutlined, ReloadOutlined, FormOutlined } from '@ant-design/icons'
import {
  createReceiptApi, scanReceiptApi, getReceiptListApi, getReceiptApi,
  confirmReceiptApi, reprintLabelApi, getMaterialsApi, scanPreviewApi,
  deleteReceiptApi, batchDeleteReceiptsApi, createMappingApi,
  manualEntryApi,
} from '../api'

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
  const [selectedRowKeys, setSelectedRowKeys] = useState<number[]>([])
  const [scannedItems, setScannedItems] = useState<any[]>([])

  // ── Scan Preview Flow ──
  const barcodeInputRef = useRef<any>(null)
  const [showScanModal, setShowScanModal] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [previewData, setPreviewData] = useState<any>(null)
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null)
  const [editMaterialCode, setEditMaterialCode] = useState('')
  const [editMaterialName, setEditMaterialName] = useState('')
  const [editQty, setEditQty] = useState<number>(1)
  const [editBatch, setEditBatch] = useState('')
  const [editDateCode, setEditDateCode] = useState('')
  const [editSpec, setEditSpec] = useState('')
  const [editSupplierCode, setEditSupplierCode] = useState('')
  const [isNewMaterial, setIsNewMaterial] = useState(false)
  const [newCode, setNewCode] = useState('')
  const [newName, setNewName] = useState('')
  const [scanBarcode, setScanBarcode] = useState('')
  const [printLabel, setPrintLabel] = useState(false)
  const [barcodeFocused, setBarcodeFocused] = useState(false)

  // ── Manual Entry Mode (no-barcode labels) ──
  const [manualEntryMode, setManualEntryMode] = useState(false)
  const [manualMaterialCode, setManualMaterialCode] = useState('')
  const [manualMaterialName, setManualMaterialName] = useState('')
  const [manualSpec, setManualSpec] = useState('')
  const [manualQty, setManualQty] = useState<number>(1)
  const [manualBatch, setManualBatch] = useState('')
  const [manualDateCode, setManualDateCode] = useState('')
  const [manualSupplierCode, setManualSupplierCode] = useState('')

  const loadReceipts = async () => {
    setLoading(true)
    try {
      const res = await getReceiptListApi()
      setReceipts(res.data?.data || res.data || [])
    } catch { message.error('加载收料单失败') }
    finally { setLoading(false) }
  }

  useEffect(() => { loadReceipts(); loadMaterials() }, [])

  // ── 扫码弹框打开时：确保条码框清空且聚焦 ──
  useEffect(() => {
    if (showScanModal) {
      // 强制清空条码值（防御性：无论之前是什么状态，打开弹框时一定为空）
      setScanBarcode('')
      // 在 DOM 渲染完成后聚焦输入框
      setTimeout(() => barcodeInputRef.current?.focus(), 150)
    }
  }, [showScanModal])

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
      // Set currentReceipt so that scan flow can access the receipt id
      setCurrentReceipt(res.data)
      loadReceipts()
      startScan(res.data.id)
    } catch (e: any) { message.error(e.response?.data?.detail || '创建失败') }
  }

  const startScan = (receiptId?: number) => {
    const id = receiptId || currentReceipt?.id
    if (!id) { message.error('请先选择收料单'); return }
    // Reload latest receipt with items
    if (id) {
      getReceiptApi(id).then(r => setCurrentReceipt(r.data)).catch(() => {})
    }
    // 先清空所有扫描状态，再打开弹框（useEffect 会确保条码框清空 + 聚焦）
    setScanBarcode('')
    setPrintLabel(false)
    setPreviewData(null)
    setScannedItems([])
    setSelectedMaterialId(null)
    setEditMaterialCode('')
    setEditMaterialName('')
    setIsNewMaterial(false)
    setManualEntryMode(false)
    setManualMaterialCode('')
    setManualMaterialName('')
    setManualSpec('')
    setManualQty(1)
    setManualBatch('')
    setManualDateCode('')
    setManualSupplierCode('')
    setShowScanModal(true)
  }

  const handleBarcodeScan = async (barcode: string) => {
    if (!barcode) return
    if (!currentReceipt?.id) {
      message.error('请先选择收料单')
      return
    }
    setScanning(true)
    try {
      // Preview scan — parse barcode and return candidates + extracted fields
      // NOTE: This does NOT save anything — only queries the backend for recognition
      const previewRes = await scanPreviewApi(currentReceipt.id, {
        barcode, operator: 'admin', qty: 1,
      })
      const data = previewRes.data

      // Always show confirmation modal for user review, regardless of status/confidence
      setPreviewData({
        barcode,
        material_code: data.material_code || barcode,
        material_name: data.material_name || '',
        quantity: data.quantity || 1,
        batch_no: data.batch_no || '',
        date_code: data.date_code || '',
        spec: data.spec || '',
        supplier_code: data.supplier_code || '',
        candidates: data.candidates || [],
        status: data.status,
        confidence: data.confidence || 0,
        message: data.message,
      })
      setEditMaterialCode(data.material_code || barcode)
      setEditMaterialName(data.material_name || '')
      setEditQty(data.quantity || 1)
      setEditBatch(data.batch_no || '')
      setEditDateCode(data.date_code || '')
      setEditSpec(data.spec || '')
      setEditSupplierCode(data.supplier_code || '')
      setNewCode(data.material_code || barcode)
      setNewName(data.material_name || '')
      setSelectedMaterialId(data.candidates?.[0]?.material_id || null)
      setIsNewMaterial(data.status === 'new_material')
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
        print_label: printLabel,
      }

      const codeChanged = editMaterialCode && previewData?.material_code &&
        editMaterialCode !== previewData.material_code
      const nameChanged = editMaterialName && previewData?.material_name &&
        editMaterialName !== previewData.material_name
      const userModified = codeChanged || nameChanged || isNewMaterial || selectedMaterialId

      if (isNewMaterial) {
        // User explicitly chose "新建料号"
        payload.is_new_material = true
        payload.new_material_code = newCode || barcode
        payload.new_material_name = newName || newCode || barcode
      } else if (selectedMaterialId) {
        // User selected a candidate from the list
        payload.manual_material_id = selectedMaterialId
      } else if (codeChanged || nameChanged) {
        // User manually edited the material code/name — treat as new material
        payload.is_new_material = true
        payload.new_material_code = editMaterialCode || barcode
        payload.new_material_name = editMaterialName || editMaterialCode || barcode
      } else if (previewData?.candidates?.[0]) {
        payload.manual_material_id = previewData.candidates[0].material_id
      }

      const res = await scanReceiptApi(currentReceipt.id, payload)
      const data = res.data
      if (data.status === 'ok') {
        const reelCode = data.reel_code || `REEL#${data.reel_id}`
        message.success(`入库成功！${reelCode}`)

        // ── Add to scanned list (keep modal open for multi-item) ──
        setScannedItems(prev => [{
          id: data.reel_id,
          reel_id: data.reel_id,
          reel_code: reelCode,
          material_id: data.material_id,
          material_code: data.material_code || editMaterialCode,
          material_name: data.material_name || editMaterialName,
          barcode,
          qty: editQty,
          message: data.message,
        }, ...prev])

        // ── Save barcode mapping if user modified the result ──
        if (userModified && data.material_id && previewData) {
          const origCode = previewData.material_code || barcode
          const mappedId = data.material_id
          try {
            await createMappingApi({
              customer_id: currentReceipt.customer_id || 1,
              customer_material_code: origCode,
              internal_material_id: mappedId,
            })
          } catch {
            // Mapping saving is best-effort; don't block the flow
          }
        }

        // ── Reset preview for next scan ──
        setPreviewData(null)
        setSelectedMaterialId(null)
        setEditMaterialCode('')
        setEditMaterialName('')
        setEditQty(1)
        setEditBatch('')
        setEditDateCode('')
        setIsNewMaterial(false)
        setNewCode('')
        setNewName('')
        setScanBarcode('')
        setTimeout(() => barcodeInputRef.current?.focus(), 200)
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
      message.success('收料单已完成并锁单')
      setDetailModal(false)
      loadReceipts()
    } catch (e: any) { message.error(e.response?.data?.detail || '锁单失败') }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteReceiptApi(id)
      message.success('入库单已删除')
      loadReceipts()
      setSelectedRowKeys(prev => prev.filter(k => k !== id))
    } catch (e: any) { message.error(e.response?.data?.detail || '删除失败') }
  }

  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) { message.warning('请选择要删除的入库单'); return }
    try {
      await batchDeleteReceiptsApi(selectedRowKeys)
      message.success(`已删除 ${selectedRowKeys.length} 张入库单`)
      setSelectedRowKeys([])
      loadReceipts()
    } catch (e: any) { message.error(e.response?.data?.detail || '批量删除失败') }
  }

  const handleReprint = async (receiptReelId: number) => {
    if (!currentReceipt?.id) return
    try {
      const res = await reprintLabelApi(currentReceipt.id, { receipt_reel_id: receiptReelId })
      if (res.data?.printed) message.success('标签已重新打印')
      else message.warning(res.data?.message || '打印失败')
    } catch (e: any) { message.error(e.response?.data?.detail || '重打失败') }
  }

  const handleManualEntry = async () => {
    if (!currentReceipt?.id) return
    if (!manualMaterialCode.trim()) {
      message.warning('请输入物料编码')
      return
    }
    setScanning(true)
    try {
      const res = await manualEntryApi(currentReceipt.id, {
        operator: 'admin',
        material_code: manualMaterialCode.trim(),
        material_name: manualMaterialName.trim(),
        spec: manualSpec.trim() || undefined,
        quantity: manualQty,
        batch_no: manualBatch.trim() || undefined,
        date_code: manualDateCode.trim() || undefined,
        supplier_code: manualSupplierCode.trim() || undefined,
        print_label: printLabel,
      })
      const data = res.data
      const reelCode = data.reel_code || `REEL#${data.reel_id}`
      message.success(`入库成功！${reelCode}`)

      setScannedItems(prev => [{
        id: data.reel_id,
        reel_id: data.reel_id,
        reel_code: reelCode,
        material_id: data.material_id,
        material_code: data.material_code || manualMaterialCode,
        material_name: data.material_name || manualMaterialName,
        barcode: `[手工] ${manualMaterialCode}`,
        qty: manualQty,
        message: data.message,
      }, ...prev])

      // Reset manual form for next entry
      setManualMaterialCode('')
      setManualMaterialName('')
      setManualSpec('')
      setManualQty(1)
      setManualBatch('')
      setManualDateCode('')
      setManualSupplierCode('')
      setTimeout(() => barcodeInputRef.current?.focus(), 200)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '手工录入失败')
    } finally { setScanning(false) }
  }

  const handleRescan = () => {
    setPreviewData(null)
    setSelectedMaterialId(null)
    setEditMaterialCode('')
    setEditMaterialName('')
    setEditQty(1)
    setEditBatch('')
    setEditDateCode('')
    setIsNewMaterial(false)
    setNewCode('')
    setNewName('')
    setScanBarcode('')
    setTimeout(() => barcodeInputRef.current?.focus(), 100)
  }

  const rowSelection = {
    selectedRowKeys,
    onChange: (keys: React.Key[]) => setSelectedRowKeys(keys as number[]),
    getCheckboxProps: (r: any) => ({ disabled: r.status !== 'draft' }),
  }

  const columns = [
    { title: '收料单号', dataIndex: 'receipt_no', key: 'receipt_no', width: 180 },
    { title: '操作员', dataIndex: 'operator', key: 'operator', width: 100 },
    { title: '类型', dataIndex: 'type', key: 'type', width: 80 },
    { title: '物料数', key: 'items_count', width: 80,
      render: (_: any, r: any) => (r.items_count ?? (r.items?.length ?? 0)),
    },
    { title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => <Tag color={statusColors[v]}>{statusLabels[v]}</Tag>,
    },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (v: string) => v ? new Date(v).toLocaleString() : '-',
    },
    { title: '操作', key: 'action', width: 200,
      render: (_: any, r: any) => (
        <Space>
          <Button type="link" size="small" onClick={() => selectReceipt(r)}>详情</Button>
          {r.status === 'draft' && (
            <>
              <Button type="link" size="small" icon={<ScanOutlined />} onClick={() => { selectReceipt(r).then(() => startScan(r.id)) }}>扫码</Button>
              <Popconfirm title={`确定删除收料单 ${r.receipt_no}？`} onConfirm={() => handleDelete(r.id)}>
                <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
              </Popconfirm>
            </>
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
          {selectedRowKeys.length > 0 && (
            <Popconfirm
              title={`确定批量删除 ${selectedRowKeys.length} 张入库单？`}
              onConfirm={handleBatchDelete}
            >
              <Button danger icon={<DeleteOutlined />}>批量删除 ({selectedRowKeys.length})</Button>
            </Popconfirm>
          )}
          <Button icon={<HistoryOutlined />} onClick={() => setReprintModal(true)}>标签重打</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModal(true)}>新建收料单</Button>
        </Space>
      </div>

      <Table rowSelection={rowSelection} columns={columns} dataSource={receipts} rowKey="id" loading={loading} pagination={{ pageSize: 20 }} />

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
                { title: '卷盘号', dataIndex: 'reel_code', key: 'reel_code', width: 180,
                  render: (v: string, r: any) => v || `REEL#${r.reel_id}`,
                },
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
                  <Popconfirm title="锁定该收料单？锁定后将无法继续扫码入库，不可修改" onConfirm={handleConfirm}>
                    <Button type="primary" icon={<CheckCircleOutlined />}>完成并锁单</Button>
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
                              <span>{item.reel_code || `Reel#${item.reel_id}`} - {item.material_code || item.material_name || '-'}</span>
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
        title={`扫码入库 - ${currentReceipt?.receipt_no || ''}`}
        open={showScanModal}
        onCancel={() => {
          setShowScanModal(false)
          setPreviewData(null)
          setScanBarcode('')
          setManualEntryMode(false)
          setManualMaterialCode('')
          setManualMaterialName('')
          setManualSpec('')
          setManualQty(1)
          setManualBatch('')
          setManualDateCode('')
          setManualSupplierCode('')
        }}
        destroyOnClose
        width={720}
        footer={
          previewData ? (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
              <Space>
                <Checkbox
                  checked={printLabel}
                  onChange={e => setPrintLabel(e.target.checked)}
                  disabled={scanning}
                >
                  打印标签
                </Checkbox>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={handleRescan}
                  disabled={scanning}
                >
                  重扫
                </Button>
              </Space>
              <Space>
                <Button onClick={() => setShowScanModal(false)} disabled={scanning}>
                  关闭
                </Button>
                <Button
                  type="primary"
                  icon={<ScanOutlined />}
                  loading={scanning}
                  onClick={() => {
                    const bc = previewData?.barcode || ''
                    handleConfirmScan(bc)
                  }}
                  disabled={
                    (previewData?.candidates?.length > 0 && !selectedMaterialId && !isNewMaterial)
                  }
                >
                  确认入库
                </Button>
              </Space>
            </div>
          ) : (
            <Space style={{ float: 'right' }}>
              <Button onClick={() => setShowScanModal(false)}>关闭</Button>
            </Space>
          )
        }
      >
        {/* ── 扫码 / 手工录入切换区 ── */}
        <div style={{
          padding: '12px 16px',
          background: !manualEntryMode ? (previewData ? '#f6f8fa' : '#e6f7ff') : '#fff7e6',
          border: !manualEntryMode ? (previewData ? '1px solid #d9d9d9' : '1px solid #91d5ff') : '1px solid #ffd591',
          borderRadius: 8,
          marginBottom: 12,
        }}>
          {/* 模式切换按钮 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: manualEntryMode ? 12 : 0 }}>
            <Button
              type={!manualEntryMode ? 'primary' : 'default'}
              icon={<ScanOutlined />}
              size="small"
              onClick={() => {
                setManualEntryMode(false)
                setPreviewData(null)
                setTimeout(() => barcodeInputRef.current?.focus(), 100)
              }}
              style={{ borderRadius: 4 }}
            >
              扫码录入
            </Button>
            <Button
              type={manualEntryMode ? 'primary' : 'default'}
              icon={<FormOutlined />}
              size="small"
              onClick={() => {
                setManualEntryMode(true)
                setPreviewData(null)
                setScanBarcode('')
              }}
              style={{ borderRadius: 4 }}
            >
              手工录入
            </Button>
            {!previewData && !manualEntryMode && !scanning && (
              <Tag color={barcodeFocused ? 'processing' : 'error'} style={{ margin: 0, fontSize: 13, marginLeft: 'auto' }}>
                {barcodeFocused ? '等待扫描...' : '等待扫描'}
              </Tag>
            )}
          </div>

          {/* 扫码输入（仅扫码模式） */}
          {!manualEntryMode && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ flex: 1 }}>
                <Input.Search
                  key={showScanModal && !manualEntryMode ? 'barcode-input-active' : 'barcode-input-hidden'}
                  ref={barcodeInputRef}
                  placeholder="扫描供应商条码..."
                  enterButton={<ScanOutlined />}
                  loading={scanning}
                  value={scanBarcode}
                  onChange={e => setScanBarcode(e.target.value)}
                  onSearch={val => {
                    setScanBarcode(val)
                    handleBarcodeScan(val)
                  }}
                  onFocus={() => setBarcodeFocused(true)}
                  onBlur={() => setBarcodeFocused(false)}
                  autoFocus
                  size="large"
                />
              </div>
            </div>
          )}

          {/* 手工录入表单（仅手工模式） */}
          {manualEntryMode && (
            <Row gutter={[12, 8]}>
              <Col span={12}>
                <Form.Item label="物料编码" style={{ marginBottom: 0 }}>
                  <Input
                    value={manualMaterialCode}
                    onChange={e => setManualMaterialCode(e.target.value)}
                    placeholder="必填：输入物料编码"
                    size="middle"
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label="物料名称" style={{ marginBottom: 0 }}>
                  <Input
                    value={manualMaterialName}
                    onChange={e => setManualMaterialName(e.target.value)}
                    placeholder="输入物料名称"
                    size="middle"
                  />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="规格" style={{ marginBottom: 0 }}>
                  <Input
                    value={manualSpec}
                    onChange={e => setManualSpec(e.target.value)}
                    placeholder="如：0805"
                    size="middle"
                  />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="数量" style={{ marginBottom: 0 }}>
                  <InputNumber
                    min={0.01}
                    value={manualQty}
                    onChange={v => setManualQty(v || 1)}
                    style={{ width: '100%' }}
                    size="middle"
                  />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="供应商代码" style={{ marginBottom: 0 }}>
                  <Input
                    value={manualSupplierCode}
                    onChange={e => setManualSupplierCode(e.target.value)}
                    placeholder="选填"
                    size="middle"
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label="批次号" style={{ marginBottom: 0 }}>
                  <Input
                    value={manualBatch}
                    onChange={e => setManualBatch(e.target.value)}
                    placeholder="选填"
                    size="middle"
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label="生产周期" style={{ marginBottom: 0 }}>
                  <Input
                    value={manualDateCode}
                    onChange={e => setManualDateCode(e.target.value)}
                    placeholder="如：2401"
                    size="middle"
                  />
                </Form.Item>
              </Col>
              <Col span={24} style={{ textAlign: 'right', marginTop: 8 }}>
                <Button
                  type="primary"
                  icon={<FormOutlined />}
                  loading={scanning}
                  onClick={handleManualEntry}
                  disabled={!manualMaterialCode.trim()}
                >
                  确认手工入库
                </Button>
              </Col>
            </Row>
          )}
        </div>

        {/* ── 已扫码列表 ── */}
        {scannedItems.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <Text strong style={{ fontSize: 15 }}>已扫码入库 ({scannedItems.length})</Text>
            <Table
              dataSource={scannedItems}
              rowKey="id"
              size="small"
              pagination={false}
              style={{ marginTop: 8 }}
              columns={[
                { title: '物料编码', dataIndex: 'material_code', width: 130 },
                { title: '物料名称', dataIndex: 'material_name', width: 140, ellipsis: true },
                { title: '条码', dataIndex: 'barcode', ellipsis: true },
                { title: '数量', dataIndex: 'qty', width: 70 },
                { title: '卷盘号', dataIndex: 'reel_code', width: 180,
                  render: (v: string, r: any) => v || `REEL#${r.reel_id}`,
                },
              ]}
            />
          </div>
        )}

        {/* ── 解析结果预览 ── */}
        {previewData && (
          <Card size="small" style={{ marginTop: 0 }}>
            {/* ── 顶部条码、状态、置信度 ── */}
            <Descriptions column={3} size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="条码" span={1}>
                <Text code style={{ fontSize: 14 }}>{previewData.barcode}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="匹配状态" span={1}>
                <Space>
                  <Tag color={previewData.status === 'ok' ? 'green' : 'orange'} style={{ fontSize: 13, padding: '0 10px' }}>
                    {previewData.status === 'ok' ? '✅ 自动匹配' :
                     previewData.status === 'new_material' ? '🆕 新料号' : '⚠️ 待确认'}
                  </Tag>
                  {/* ── 置信度标签 — 显眼展示 ── */}
                  {previewData.confidence > 0 && (
                    <Tag
                      color={previewData.confidence >= 0.8 ? 'green' : previewData.confidence >= 0.5 ? 'orange' : 'red'}
                      style={{ fontSize: 13, padding: '0 10px', fontWeight: 600 }}
                    >
                      匹配度 {(previewData.confidence * 100).toFixed(0)}%
                    </Tag>
                  )}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="供应商代码" span={1}>
                {previewData.supplier_code ? (
                  <Text style={{ fontSize: 14 }}>{previewData.supplier_code}</Text>
                ) : (
                  <Text type="secondary" style={{ fontSize: 13 }}>--</Text>
                )}
              </Descriptions.Item>
            </Descriptions>

            {/* ── 物料核心信息 — 统一 3 列网格，整齐对齐 ── */}
            <Row gutter={[16, 12]}>
              <Col span={8}>
                <Form.Item label="物料编码" style={{ marginBottom: 0 }}>
                  <Input
                    value={editMaterialCode}
                    onChange={e => {
                      setEditMaterialCode(e.target.value)
                      if (e.target.value !== previewData.material_code) {
                        setSelectedMaterialId(null)
                        setIsNewMaterial(false)
                      }
                    }}
                    placeholder={previewData.material_code}
                    size="middle"
                  />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="物料名称" style={{ marginBottom: 0 }}>
                  <Input
                    value={editMaterialName}
                    onChange={e => {
                      setEditMaterialName(e.target.value)
                      if (e.target.value !== previewData.material_name) {
                        setSelectedMaterialId(null)
                        setIsNewMaterial(false)
                      }
                    }}
                    placeholder={previewData.material_name}
                    size="middle"
                  />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="规格" style={{ marginBottom: 0 }}>
                  <Input
                    value={editSpec || previewData.spec || ''}
                    onChange={e => setEditSpec(e.target.value)}
                    placeholder={previewData.spec || '输入规格'}
                    size="middle"
                  />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="数量" style={{ marginBottom: 0 }}>
                  <InputNumber
                    min={0.01}
                    value={editQty}
                    onChange={v => setEditQty(v || 1)}
                    style={{ width: '100%' }}
                    size="middle"
                  />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="批次号" style={{ marginBottom: 0 }}>
                  <Input
                    value={editBatch}
                    onChange={e => setEditBatch(e.target.value)}
                    placeholder="从条码解析"
                    size="middle"
                  />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="生产周期" style={{ marginBottom: 0 }}>
                  <Input
                    value={editDateCode}
                    onChange={e => setEditDateCode(e.target.value)}
                    placeholder="如：2401"
                    size="middle"
                  />
                </Form.Item>
              </Col>
            </Row>

            {/* ── 修改提示 ── */}
            {editMaterialCode && editMaterialCode !== previewData.material_code && (
              <div style={{ marginTop: 10, fontSize: 13, color: '#52c41a', textAlign: 'right' }}>
                🔁 已修改物料编码 — 确认后系统将自动学习该条码映射
              </div>
            )}

            {/* ── 候选物料选择（低置信度时出现） ── */}
            {previewData.candidates && previewData.candidates.length > 0 && previewData.status !== 'new_material' && (
              <div style={{ marginTop: 16, padding: 12, borderRadius: 6, border: '1px solid #faad14', background: '#fffbe6' }}>
                <Text strong style={{ color: '#d48806' }}>⚠ 匹配候选项 — 请选择：</Text>
                <Radio.Group
                  onChange={e => {
                    if (e.target.value === -1) {
                      setIsNewMaterial(true)
                      setSelectedMaterialId(null)
                    } else {
                      setIsNewMaterial(false)
                      setSelectedMaterialId(e.target.value)
                      const selected = previewData.candidates.find((c: any) => c.material_id === e.target.value)
                      if (selected) {
                        setEditMaterialCode(selected.code)
                        setEditMaterialName(selected.name)
                      }
                    }
                  }}
                  value={isNewMaterial ? -1 : selectedMaterialId}
                >
                  <Space direction="vertical" style={{ width: '100%', marginTop: 8 }}>
                    {previewData.candidates?.map((c: any) => (
                      <Radio key={c.material_id} value={c.material_id}>
                        <Space>
                          <Text strong>{c.code}</Text>
                          <Text type="secondary">{c.name}</Text>
                          {c.spec && <Text type="secondary">规格: {c.spec}</Text>}
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

                {/* 新建料号时的编码/名称输入 */}
                {isNewMaterial && (
                  <Row gutter={16} style={{ marginTop: 8 }}>
                    <Col span={12}>
                      <Form.Item label="新料号" style={{ marginBottom: 0 }}>
                        <Input value={newCode} onChange={e => setNewCode(e.target.value)} placeholder="输入新料号编码" size="middle" />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item label="物料名称" style={{ marginBottom: 0 }}>
                        <Input value={newName} onChange={e => setNewName(e.target.value)} placeholder="输入新物料名称" size="middle" />
                      </Form.Item>
                    </Col>
                  </Row>
                )}
              </div>
            )}

            {/* ── 新建料号独立模式 ── */}
            {previewData.status === 'new_material' && (
              <div style={{ marginTop: 16, padding: 12, borderRadius: 6, border: '1px solid #1890ff', background: '#e6f7ff' }}>
                <Text strong style={{ color: '#1890ff' }}>🆕 新建料号</Text>
                <Row gutter={16} style={{ marginTop: 8 }}>
                  <Col span={12}>
                    <Form.Item label="料号编码" style={{ marginBottom: 0 }}>
                      <Input value={newCode} onChange={e => setNewCode(e.target.value)} placeholder={previewData.material_code} size="middle" />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item label="物料名称" style={{ marginBottom: 0 }}>
                      <Input value={newName} onChange={e => setNewName(e.target.value)} placeholder="输入新物料名称" size="middle" />
                    </Form.Item>
                  </Col>
                </Row>
              </div>
            )}
          </Card>
        )}
      </Modal>
    </div>
  )
}
