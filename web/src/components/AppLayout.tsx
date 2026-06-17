import { Layout, Menu, Typography, Avatar, Dropdown, Space } from 'antd'
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
} from '@ant-design/icons'
import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'

const { Header, Sider, Content } = Layout
const { Title } = Typography

const menuItems = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/material', icon: <BoxPlotOutlined />, label: '物料主数据' },
  { key: '/shelf', icon: <DatabaseOutlined />, label: '料架管理' },
  { key: '/inventory', icon: <ContainerOutlined />, label: '库存管理' },
  { key: '/receipt', icon: <ReadOutlined />, label: '入库管理' },
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
      { key: '/users', label: '用户管理' },
      { key: '/customers', label: '客户管理' },
      { key: '/app-download', icon: <DownloadOutlined />, label: 'PDA下载' },
    ],
  },
]

export function AppLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()

  const handleMenuClick = (key: string) => {
    navigate(key)
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
          智能物料架管理系统
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
    </Layout>
  )
}
