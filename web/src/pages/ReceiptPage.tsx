import { useState } from 'react'
import { Card, Form, Input, Button, Space, Tag, Steps, Spin, message } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import { createReceiptApi, scanReceiptApi, confirmReceiptApi } from '../api'

interface ScanResult {
  status: string
  action: string
  inventory_pallet_id?: number | null
  assigned_slot?: number | null
  material_code: string
  quantity: number
  message: string
  duplicate_flag: boolean
  warning?: string | null
  barcode: string
}

export function ReceiptPage() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState(0)
  const [receiptId, setReceiptId] = useState<number | null>(null)
  const [scanResult, setScanResult] = useState<ScanResult | null>(null)
  const [scanHistory, setScanHistory] = useState<ScanResult[]>([])

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
        inventory_pallet_id: response.inventory_pallet_id ?? null,
        assigned_slot: response.assigned_slot ?? null,
        material_code: response.material_code ?? response.material ?? '',
        quantity: response.quantity ?? 0,
        message: response.message || '',
        duplicate_flag: response.duplicate_flag || false,
        warning: response.warning ?? null,
        barcode: values.barcode,
      }
      setScanResult(result)
      setScanHistory((prev) => [...prev, result])
      message.success(result.message || '扫码成功')
      form.resetFields(['barcode'])
    } catch (err: any) {
      const detail = err.response?.data?.detail || '扫码失败'
      message.error(detail)
      setScanResult({
        status: 'error',
        action: 'error',
        inventory_pallet_id: null,
        assigned_slot: null,
        material_code: '',
        quantity: 0,
        message: detail,
        duplicate_flag: false,
        warning: null,
        barcode: values.barcode,
      })
    } finally {
      setLoading(false)
    }
  }

  const handleNextScan = () => {
    setScanResult(null)
    form.resetFields(['barcode'])
    setTimeout(() => form.getFieldInstance('barcode')?.focus(), 0)
  }

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

  return (
    <Spin spinning={loading}>
      <div>
        <h2>入库管理</h2>
        <Steps current={step} style={{ marginBottom: 24 }}>
          <Steps.Step title="创建入库单" />
          <Steps.Step title="扫码入库" />
          <Steps.Step title="确认完成" />
        </Steps>

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

            {scanResult && (
              <Card
                title="扫描结果"
                style={{ marginBottom: 16 }}
                extra={
                  <Tag
                    color={scanResult.status === 'ok' ? 'green' : 'red'}
                    icon={
                      scanResult.status === 'ok' ? <CheckCircleOutlined /> : <CloseCircleOutlined />
                    }
                  >
                    {scanResult.status === 'ok' ? '成功' : scanResult.status === 'duplicate' ? '重复' : '失败'}
                  </Tag>
                }
              >
                <p>
                  <strong>条码：</strong>
                  {scanResult.barcode}
                </p>
                <p>
                  <strong>结果：</strong>
                  {scanResult.message}
                </p>
                {scanResult.warning && (
                  <p style={{ color: '#faad14' }}>
                    <strong>警告：</strong>
                    {scanResult.warning}
                  </p>
                )}
                {scanResult.inventory_pallet_id && (
                  <p>
                    <strong>库存盘 ID：</strong>
                    <Tag color="blue">{scanResult.inventory_pallet_id}</Tag>
                  </p>
                )}
                {scanResult.assigned_slot && (
                  <p>
                    <strong>分配储位：</strong>
                    <Tag color="green">{scanResult.assigned_slot}</Tag>
                  </p>
                )}
              </Card>
            )}

            {scanHistory.length > 0 && (
              <Card title="扫码记录" size="small" style={{ marginBottom: 16 }}>
                {scanHistory.map((item, idx) => (
                  <p key={idx}>
                    <Tag color={item.status === 'ok' ? 'green' : 'red'}>
                      {item.status === 'ok' ? `#${item.inventory_pallet_id}` : item.status}
                    </Tag>
                    {item.barcode} — {item.message}
                  </p>
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

        {step === 2 && (
          <Card title="入库完成">
            <p>
              入库单号：<strong>{receiptId}</strong>
            </p>
            <p>
              扫码总数：<strong>{scanHistory.length}</strong>
            </p>
            <p>
              成功：
              <strong>{scanHistory.filter((s) => s.status === 'ok').length}</strong>
              {' / '}失败：
              <strong>{scanHistory.filter((s) => s.status !== 'ok').length}</strong>
            </p>
            <Button type="primary" onClick={handleBackToCreate}>
              新建入库单
            </Button>
          </Card>
        )}
      </div>
    </Spin>
  )
}
