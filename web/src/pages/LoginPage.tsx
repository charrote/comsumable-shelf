import { Form, Input, Button, Card, Typography, Space, Alert } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { login } from '../store/authStore'
import { getAppName } from '../store/configStore'
import { useState } from 'react'

const { Title, Text } = Typography

export function LoginPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const appName = getAppName()

  const onFinish = async (values: any) => {
    setLoading(true)
    setError('')
    try {
      await login(values.username, values.password)
      navigate('/dashboard')
    } catch (err: any) {
      setError(err.response?.data?.detail || '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      }}
    >
      <Card
        style={{
          width: 380,
          borderRadius: 12,
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
        }}
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div style={{ textAlign: 'center' }}>
            <Title level={3} style={{ margin: 0 }}>
              {appName}
            </Title>
            <Text type="secondary">Smart Consumable Shelf</Text>
          </div>
          {error && <Alert message={error} type="error" showIcon />}
          <Form layout="vertical" onFinish={onFinish}>
            <Form.Item
              name="username"
              rules={[{ required: true, message: '请输入用户名' }]}
            >
              <Input prefix={<UserOutlined />} placeholder="用户名" size="large" />
            </Form.Item>
            <Form.Item
              name="password"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password prefix={<LockOutlined />} placeholder="密码" size="large" />
            </Form.Item>
            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                size="large"
                block
                style={{ borderRadius: 6 }}
              >
                登录
              </Button>
            </Form.Item>
          </Form>
        </Space>
      </Card>
    </div>
  )
}
