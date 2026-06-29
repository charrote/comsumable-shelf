import { Layout, Menu, Typography, Avatar, Dropdown, Space, Modal, Input, message } from 'antd'
import {
  DashboardOutlined,
  BoxPlotOutlined,
  DatabaseOutlined,
  ContainerOutlined,
  ReadOutlined,
  SendOutlined,
  DesktopOutlined,
  FileExcelOutlined,
  BarChartOutlined,
  SettingOutlined,
  UserOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  LogoutOutlined,
  DownloadOutlined,
  CloudUploadOutlined,
  BugOutlined,
} from '@ant-design/icons'
import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { getAppName } from '../store/configStore'

const { Header, Sider, Content } = Layout
const { Title } = Typography

const menuItems = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/material', icon: <BoxPlotOutlined />, label: '物料主数据' },
  { key: '/shelf', icon: <DatabaseOutlined />, label: '料架管理' },
  { key: '/inventory', icon: <ContainerOutlined />, label: '库存管理' },
  { key: '/receipt', icon: <ReadOutlined />, label: '入库收料' },
  { key: '/issue', icon: <SendOutlined />, label: '发料管理' },
  { key: '/xr', icon: <DesktopOutlined />, label: '点料机管理' },
  { key: '/bom', icon: <FileExcelOutlined />, label: 'BOM管理' },
  { key: '/report', icon: <BarChartOutlined />, label: '报表统计' },
  {
    key: 'admin',
    icon: <SettingOutlined />,
    label: '系统管理',
    children: [
      { key: '/settings', label: '系统设置' },
      { key: '/barcode-definitions', label: '条码定义' },
      { key: '/users', label: '用户管理' },
      { key: '/customers', label: '客户管理' },
      { key: '/suppliers', label: '供应商管理' },
      { key: '/app-download', icon: <DownloadOutlined />, label: 'PDA下载' },
      { key: '/app-version', icon: <DownloadOutlined />, label: 'APP版本更新' },
      { key: '/backup', icon: <CloudUploadOutlined />, label: '数据备份' },
      { key: '/light-debug', icon: <BugOutlined />, label: '灯控调试' },
    ],
  },
]

export function AppLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const [passwordModalVisible, setPasswordModalVisible] = useState(false)
  const [passwordInput, setPasswordInput] = useState('')
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()

  const getTodayPassword = () => {
    const today = new Date()
    const yyyy = today.getFullYear()
    const mm = String(today.getMonth() + 1).padStart(2, '0')
    const dd = String(today.getDate()).padStart(2, '0')
    return `${yyyy}${mm}${dd}`
  }

  const handleMenuClick = (key: string) => {
    if (key === '/app-version') {
      setPasswordInput('')
      setPasswordModalVisible(true)
    } else {
      navigate(key)
    }
  }

  const handlePasswordSubmit = () => {
    if (passwordInput === getTodayPassword()) {
      setPasswordModalVisible(false)
      setPasswordInput('')
      navigate('/app-version')
    } else {
      message.error('口令错误，请重试')
      setPasswordInput('')
    }
  }

  const handlePasswordCancel = () => {
    setPasswordModalVisible(false)
    setPasswordInput('')
  }

  const userMenuItems = [
    { key: 'profile', icon: <UserOutlined />, label: '个人中心' },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录' },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={(value) => setCollapsed(value)}
        theme="dark"
        width={220}
      >
        <div
          style={{
            padding: '16px',
            textAlign: 'center',
            color: '#fff',
            fontSize: collapsed ? 14 : 16,
            fontWeight: 'bold',
            overflow: 'hidden',
            whiteSpace: 'nowrap',
            textOverflow: 'ellipsis',
          }}
        >
          {getAppName()}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => handleMenuClick(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            padding: '0 24px',
            background: '#fff',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Space>
            {collapsed ? (
              <MenuUnfoldOutlined onClick={() => setCollapsed(false)} style={{ fontSize: 18 }} />
            ) : (
              <MenuFoldOutlined onClick={() => setCollapsed(true)} style={{ fontSize: 18 }} />
            )}
          </Space>
          <Space>
            <Dropdown menu={{ items: userMenuItems, onClick: ({ key }) => key === 'logout' && logout() }}>
              <Space style={{ cursor: 'pointer' }}>
                <Avatar icon={<UserOutlined />} />
                <span>{user?.username || '管理员'}</span>
              </Space>
            </Dropdown>
          </Space>
        </Header>
        <Content
          style={{
            margin: '24px 16px',
            padding: 24,
            background: '#fff',
            borderRadius: 8,
          }}
        >
          {children}
        </Content>
        <div style={{ textAlign: 'center', padding: '12px 0', color: '#999', fontSize: 12 }}>
          Copyright &copy; 2026 hwazun.cloud All Rights Reserved.
        </div>
      </Layout>

      <Modal
        title="请输入口令"
        open={passwordModalVisible}
        onCancel={handlePasswordCancel}
        onOk={handlePasswordSubmit}
        okText="确认"
        cancelText="取消"
      >
        <Input.Password
          placeholder="请输入当日口令"
          value={passwordInput}
          onChange={(e) => setPasswordInput(e.target.value)}
          onPressEnter={handlePasswordSubmit}
          autoFocus
          style={{ marginTop: 16 }}
        />
      </Modal>
    </Layout>
  )
}
