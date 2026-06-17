import { useState } from 'react'
import { Card, Form, Input, Button, Space, Tag, Steps, Spin, message, Modal, List, Typography, Radio } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined, QuestionCircleOutlined, PlusCircleOutlined, PrinterOutlined } from '@ant-design/icons'
import { createReceiptApi, scanReceiptApi, confirmReceiptApi, reprintLabelApi } from '../api'

const { Text, Title } = Typography

interface MaterialCandidate {
  material_id: number
  code: string
  name: string
  confidence: number
  extracted_code: string
}

interface ScanResult {
  status: string               // ok | duplicate | pending_review | error
  action: string               // first_in | duplicate | pending_review | new_material
  reelId?: number | null
  assigned_slot?: number | null
  material_code: string
  material_name: string
  quantity: number
  message: string
  duplicate_flag: boolean
  warning?: string | null
  barcode: string
  // Pending review fields
  candidates?: MaterialCandidate[]
  customer_material_code?: string
  material_id?: number | null
  confidence?: number
  // Label printing
  label_printed?: boolean
}

/** Status tag color & label map */
const STATUS_META: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
  ok:             { color: 'green',  label: '成功',     icon: <CheckCircleOutlined /> },
  duplicate:      { color: 'red',    label: '重复',     icon: <CloseCircleOutlined /> },
  pending_review: { color: 'orange', label: '待确认',   icon: <QuestionCircleOutlined /> },
  error:          { color: 'red',    label: '失败',     icon: <CloseCircleOutlined /> },
}

export function ReceiptPage() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState(0)
  const [receiptId, setReceiptId] = useState<number | null>(null)
  const [scanResult, setScanResult] = useState<ScanResult | null>(null)
  const [scanHistory, setScanHistory] = useState<ScanResult[]>([])

  // ── Review modal state ──
  const [reviewVisible, setReviewVisible] = useState(false)
  const [pendingBarcode, setPendingBarcode] = useState('')
  const [pendingCandidates, setPendingCandidates] = useState<MaterialCandidate[]>([])
  const [pendingCustomerCode, setPendingCustomerCode] = useState('')
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null)
  const [newMaterialCode, setNewMaterialCode] = useState('')
  const [newMaterialName, setNewMaterialName] = useState('')
  const [reviewMode, setReviewMode] = useState<'select' | 'new'>('select') // 'select' | 'new'

  // ── Create receipt ──
  const handleCreate = async (values: { operator: string }) => {
    setLoading(true)
    try {
      const res = await createReceiptApi({ type: 'incoming', operator: values.operator })
      const id = res.data?.id ?? res.data?.receipt_id
      setReceiptId(id)
      message.success('入库单创建成功')
      setStep(1)
      form.resetFields()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '创建入库单失败')
    } finally {
      setLoading(false)
    }
  }

  // ── Scan barcode ──
  const handleScan = async (values: { barcode: string }) => {
    if (!receiptId) return
    setLoading(true)
    setScanResult(null)
    try {
      const res = await scanReceiptApi(receiptId, {
        barcode: values.barcode,
        operator: form.getFieldValue('operator') || '',
      })
      const response = res.data
      const result: ScanResult = {
        status: response.status,
        action: response.action,
        reelId: response.reelId ?? null,
        assigned_slot: response.assigned_slot ?? null,
        material_code: response.material_code ?? '',
        material_name: response.material_name ?? '',
        quantity: response.quantity ?? 0,
        message: response.message || '',
        duplicate_flag: response.duplicate_flag || false,
        warning: response.warning ?? null,
        barcode: values.barcode,
        candidates: response.candidates || [],
        customer_material_code: response.customer_material_code || '',
        material_id: response.material_id ?? null,
        confidence: response.confidence ?? 0,
        label_printed: response.label_printed ?? false,
      }
      setScanResult(result)
      form.resetFields(['barcode'])

      if (response.status === 'ok') {
        // Auto-proceed → add to history
        setScanHistory((prev) => [...prev, result])
        message.success(result.message || '入库成功')
      } else if (response.status === 'duplicate') {
        message.warning(result.message)
      } else if (response.status === 'pending_review') {
        // Open review modal
        setPendingBarcode(values.barcode)
        setPendingCandidates(result.candidates || [])
        setPendingCustomerCode(result.customer_material_code || values.barcode)
        setSelectedMaterialId(null)
        setNewMaterialCode(result.customer_material_code || values.barcode)
        setNewMaterialName(result.customer_material_code || values.barcode)
        setReviewMode('select')
        setReviewVisible(true)
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail || '扫码失败'
      message.error(detail)
      setScanResult({
        status: 'error', action: 'error',
        reelId: null, assigned_slot: null,
        material_code: '', material_name: '', quantity: 0,
        message: detail, duplicate_flag: false, warning: null,
        barcode: values.barcode,
      })
    } finally {
      setLoading(false)
    }
  }

  // ── Confirm human review: send second-pass scan ──
  const handleConfirmReview = async () => {
    if (!receiptId) return
    setLoading(true)
    setReviewVisible(false)
    try {
      const params: any = {
        barcode: pendingBarcode,
        operator: form.getFieldValue('operator') || '',
      }
      if (reviewMode === 'select' && selectedMaterialId) {
        params.manual_material_id = selectedMaterialId
      } else if (reviewMode === 'new') {
        params.is_new_material = true
        params.new_material_code = newMaterialCode
        params.new_material_name = newMaterialName
      } else {
        message.error('请选择物料或确认新料')
        setLoading(false)
        return
      }

      const res = await scanReceiptApi(receiptId, params)
      const response = res.data
      const result: ScanResult = {
        status: response.status,
        action: response.action,
        reelId: response.reelId ?? null,
        assigned_slot: response.assigned_slot ?? null,
        material_code: response.material_code ?? '',
        material_name: response.material_name ?? '',
        quantity: response.quantity ?? 0,
        message: response.message || '',
        duplicate_flag: response.duplicate_flag || false,
        warning: response.warning ?? null,
        barcode: pendingBarcode,
        material_id: response.material_id ?? null,
        confidence: response.confidence ?? 1.0,
        label_printed: response.label_printed ?? false,
      }
      setScanResult(result)
      setScanHistory((prev) => [...prev, result])
      message.success(result.message || '入库成功')
    } catch (err: any) {
      message.error(err.response?.data?.detail || '确认失败')
    } finally {
      setLoading(false)
    }
  }

  // ── Next scan ──
  const handleNextScan = () => {
    setScanResult(null)
    form.resetFields(['barcode'])
    setTimeout(() => form.getFieldInstance('barcode')?.focus(), 0)
  }

  // ── Confirm receipt ──
  const handleConfirm = async () => {
    if (!receiptId) return
    setLoading(true)
    try {
      await confirmReceiptApi(receiptId)
      setStep(2)
      message.success('入库确认完成')
    } catch (err: any) {
      message.error(err.response?.data?.detail || '入库确认失败')
    } finally {
      setLoading(false)
    }
  }

  const handleBackToCreate = () => {
    setStep(0)
    setReceiptId(null)
    setScanResult(null)
    setScanHistory([])
    form.resetFields()
  }

  // ── Render ──
  const meta = STATUS_META[scanResult?.status || ''] ?? STATUS_META.error

  return (
    <Spin spinning={loading}>
      <div>
        <h2>入库管理</h2>
        <Steps current={step} style={{ marginBottom: 24 }}>
          <Steps.Step title="创建入库单" />
          <Steps.Step title="扫码入库" />
          <Steps.Step title="确认完成" />
        </Steps>

        {/* ── Step 0: Create ── */}
        {step === 0 && (
          <Card title="创建入库单" style={{ marginBottom: 16 }}>
            <Form layout="vertical" form={form} onFinish={handleCreate}>
              <Form.Item name="operator" label="操作员" rules={[{ required: true, message: '请输入操作员姓名' }]}>
                <Input placeholder="输入操作员姓名" />
              </Form.Item>
              <Form.Item>
                <Button type="primary" htmlType="submit" loading={loading}>
                  创建入库单
                </Button>
              </Form.Item>
            </Form>
          </Card>
        )}

        {/* ── Step 1: Scan ── */}
        {step === 1 && (
          <>
            <Card title="扫码入库" style={{ marginBottom: 16 }}>
              <Form layout="vertical" form={form} onFinish={handleScan}>
                <Form.Item name="barcode" label="扫描条码" rules={[{ required: true, message: '请扫描或输入条码' }]}>
                  <Input
                    placeholder="扫码枪扫描或手动输入"
                    addonAfter={
                      <Button type="primary" htmlType="submit" loading={loading}>
                        确认
                      </Button>
                    }
                    onPressEnter={() => form.submit()}
                  />
                </Form.Item>
              </Form>
            </Card>

            {/* ── Scan result card ── */}
            {scanResult && (
              <Card
                title="扫描结果"
                style={{ marginBottom: 16 }}
                extra={
                  <Tag color={meta.color} icon={meta.icon}>
                    {meta.label}
                  </Tag>
                }
              >
                <p><strong>条码：</strong>{scanResult.barcode}</p>
                <p><strong>结果：</strong>{scanResult.message}</p>

                {scanResult.warning && (
                  <p style={{ color: '#faad14' }}><strong>警告：</strong>{scanResult.warning}</p>
                )}

                {scanResult.material_code && (
                  <p><strong>物料编码：</strong><Text code>{scanResult.material_code}</Text></p>
                )}
                {scanResult.material_name && (
                  <p><strong>物料名称：</strong>{scanResult.material_name}</p>
                )}
                {scanResult.confidence !== undefined && scanResult.confidence > 0 && (
                  <p><strong>匹配置信度：</strong>{(scanResult.confidence * 100).toFixed(0)}%</p>
                )}
                {scanResult.reelId && (
                  <p><strong>库存盘 ID：</strong><Tag color="blue">{scanResult.reelId}</Tag></p>
                )}
                {scanResult.assigned_slot && (
                  <p><strong>分配储位：</strong><Tag color="green">{scanResult.assigned_slot}</Tag></p>
                )}
                {scanResult.quantity > 0 && (
                  <p><strong>数量：</strong>{scanResult.quantity} 盘</p>
                )}
                {scanResult.status === 'ok' && scanResult.label_printed !== undefined && (
                  <p>
                    <strong>标签打印：</strong>
                    {scanResult.label_printed ? (
                      <Tag color="green" icon={<PrinterOutlined />}>已打印</Tag>
                    ) : (
                      <Tag color="default" icon={<PrinterOutlined />}>未打印</Tag>
                    )}
                    {scanResult.reelId && !scanResult.label_printed && (
                      <Button
                        size="small"
                        icon={<PrinterOutlined />}
                        onClick={async () => {
                          try {
                            await reprintLabelApi(receiptId!, {
                              receipt_reel_id: scanResult.reelId!,
                            })
                            message.success('标签重打请求已发送')
                          } catch (e: any) {
                            message.error(e.response?.data?.detail || '重打失败')
                          }
                        }}
                      >
                        重打
                      </Button>
                    )}
                  </p>
                )}
                {scanResult.candidates && scanResult.candidates.length > 0 && (
                  <p style={{ color: '#faad14' }}>
                    <QuestionCircleOutlined /> 系统无法确定物料，请在弹窗中选择
                  </p>
                )}
              </Card>
            )}

            {/* ── Scan history ── */}
            {scanHistory.length > 0 && (
              <Card title="扫码记录" size="small" style={{ marginBottom: 16 }}>
                {scanHistory.map((item, idx) => (
                  <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0', borderBottom: idx < scanHistory.length - 1 ? '1px solid #f0f0f0' : 'none' }}>
                    <div>
                      <Tag color={item.status === 'ok' ? 'green' : item.status === 'pending_review' ? 'orange' : 'red'}>
                        {item.status === 'ok' ? `#${item.reelId}` : item.status === 'pending_review' ? '已确认' : item.status}
                      </Tag>
                      {item.barcode}
                      {item.material_code ? ` → ${item.material_code}` : ''}
                      {item.message ? ` — ${item.message}` : ''}
                      {item.label_printed !== undefined && (
                        item.label_printed ? <Tag color="green" icon={<PrinterOutlined />} style={{ marginLeft: 8 }}>已打印</Tag>
                          : <Tag color="default" icon={<PrinterOutlined />} style={{ marginLeft: 8 }}>未打印</Tag>
                      )}
                    </div>
                    {item.status === 'ok' && item.reelId && !item.label_printed && (
                      <Button
                        size="small"
                        type="link"
                        icon={<PrinterOutlined />}
                        onClick={async () => {
                          try {
                            await reprintLabelApi(receiptId!, {
                              receipt_reel_id: item.reelId!,
                            })
                            message.success('标签重打请求已发送')
                          } catch (e: any) {
                            message.error(e.response?.data?.detail || '重打失败')
                          }
                        }}
                      >
                        重打标签
                      </Button>
                    )}
                  </div>
                ))}
              </Card>
            )}

            <Space>
              <Button onClick={handleNextScan} disabled={!scanResult}>
                继续扫码
              </Button>
              <Button type="primary" onClick={handleConfirm} disabled={scanHistory.length === 0}>
                完成入库
              </Button>
            </Space>
          </>
        )}

        {/* ── Step 2: Done ── */}
        {step === 2 && (
          <Card title="入库完成">
            <p>入库单号：<strong>{receiptId}</strong></p>
            <p>扫码总数：<strong>{scanHistory.length}</strong></p>
            <p>
              成功：
              <strong style={{ color: 'green' }}>{scanHistory.filter((s) => s.status === 'ok').length}</strong>
              {' / '}待确认：
              <strong style={{ color: 'orange' }}>{scanHistory.filter((s) => s.status === 'pending_review').length}</strong>
              {' / '}失败：
              <strong style={{ color: 'red' }}>{scanHistory.filter((s) => s.status === 'error' || s.status === 'duplicate').length}</strong>
            </p>
            <Button type="primary" onClick={handleBackToCreate}>
              新建入库单
            </Button>
          </Card>
        )}

        {/* ══════════════════════════════════════════════════════════
            Review Modal — material selection / new material confirm
           ══════════════════════════════════════════════════════════ */}
        <Modal
          title={
            <Space>
              <QuestionCircleOutlined style={{ color: '#faad14' }} />
              物料确认
            </Space>
          }
          open={reviewVisible}
          onOk={handleConfirmReview}
          onCancel={() => setReviewVisible(false)}
          okText="确认入库"
          okButtonProps={{
            disabled: reviewMode === 'select' && !selectedMaterialId,
          }}
          width={520}
        >
          <p style={{ marginBottom: 16 }}>
            <Text strong>客户条码：</Text>
            <Text code>{pendingBarcode}</Text>
          </p>
          <p style={{ marginBottom: 16 }}>
            <Text strong>识别物料编码：</Text>
            <Text code>{pendingCustomerCode}</Text>
          </p>

          {/* ── Tabs: Select existing / New material ── */}
          <Radio.Group
            value={reviewMode}
            onChange={(e) => setReviewMode(e.target.value)}
            style={{ marginBottom: 16, width: '100%' }}
          >
            <Radio.Button value="select" style={{ width: '50%', textAlign: 'center' }}>
              选择已有物料
            </Radio.Button>
            <Radio.Button value="new" style={{ width: '50%', textAlign: 'center' }}>
              确认为新物料
            </Radio.Button>
          </Radio.Group>

          {reviewMode === 'select' && (
            <>
              {pendingCandidates.length === 0 ? (
                <Text type="secondary">暂无匹配的候选物料</Text>
              ) : (
                <List
                  size="small"
                  bordered
                  dataSource={pendingCandidates}
                  renderItem={(item) => (
                    <List.Item
                      onClick={() => setSelectedMaterialId(item.material_id)}
                      style={{
                        cursor: 'pointer',
                        background: selectedMaterialId === item.material_id ? '#e6f4ff' : undefined,
                      }}
                      actions={[
                        selectedMaterialId === item.material_id ? (
                          <Tag color="blue">已选</Tag>
                        ) : (
                          <Button size="small" type="link">选择</Button>
                        ),
                      ]}
                    >
                      <List.Item.Meta
                        title={<Text code>{item.code}</Text>}
                        description={
                          <Space>
                            <Text>{item.name}</Text>
                            <Tag color="default">{(item.confidence * 100).toFixed(0)}%</Tag>
                          </Space>
                        }
                      />
                    </List.Item>
                  )}
                />
              )}
            </>
          )}

          {reviewMode === 'new' && (
            <Space direction="vertical" style={{ width: '100%' }}>
              <p>
                <Text type="secondary">系统将使用以下信息自动创建新物料：</Text>
              </p>
              <Form layout="vertical">
                <Form.Item label="新物料编码">
                  <Input
                    value={newMaterialCode}
                    onChange={(e) => setNewMaterialCode(e.target.value)}
                    placeholder="输入物料编码"
                  />
                </Form.Item>
                <Form.Item label="新物料名称（可选）">
                  <Input
                    value={newMaterialName}
                    onChange={(e) => setNewMaterialName(e.target.value)}
                    placeholder="输入物料名称，留空则使用编码"
                  />
                </Form.Item>
              </Form>
            </Space>
          )}
        </Modal>
      </div>
    </Spin>
  )
}
