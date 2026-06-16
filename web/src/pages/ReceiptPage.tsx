import { useState } from 'react'
import { Card, Form, Input, Button, Table, message, Space, Tag, Steps } from 'antd'
import { PlayCircleOutlined, CheckCircleOutlined } from '@ant-design/icons'

export function ReceiptPage() {
  const [form] = Form.useForm()
  const [scanResult, setScanResult] = useState<any>(null)
  const [step, setStep] = useState(0)

  const handleScan = (values: any) => {
    // Simulate barcode scan result
    setScanResult({
      status: 'ok',
      action: 'first_in',
      barcode: values.barcode,
      material: '4500067189',
      qty: 50,
      message: '首次入库, 数量 50 盘',
    })
    message.success('入库成功')
  }

  return (
    <div>
      <h2>入库管理</h2>
      <Steps current={step} style={{ marginBottom: 24 }}>
        <Steps.Step title="创建入库单" description="" />
        <Steps.Step title="扫码入库" description="" />
        <Steps.Step title="确认完成" description="" />
      </Steps>

      <Card title="创建入库单" style={{ marginBottom: 16 }}>
        <Form layout="vertical" onFinish={handleScan}>
          <Form.Item name="operator" label="操作员" rules={[{ required: true }]}>
            <Input placeholder="输入操作员姓名" />
          </Form.Item>
          <Form.Item name="barcode" label="扫描条码" rules={[{ required: true }]}>
            <Input
              placeholder="扫码枪扫描或手动输入"
              addonAfter={<Button type="primary" htmlType="submit">确认</Button>}
              onPressEnter={(e: any) => form.submit()}
            />
          </Form.Item>
        </Form>
      </Card>

      {scanResult && (
        <Card
          title="扫描结果"
          extra={
            <Tag
              color={scanResult.status === 'ok' ? 'green' : 'red'}
              icon={scanResult.status === 'ok' ? <CheckCircleOutlined /> : null}
            >
              {scanResult.status}
            </Tag>
          }
        >
          <p>物料: {scanResult.material}</p>
          <p>数量: {scanResult.qty}</p>
          <p>结果: {scanResult.message}</p>
        </Card>
      )}
    </div>
  )
}
