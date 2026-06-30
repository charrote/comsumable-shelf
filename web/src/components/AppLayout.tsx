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
  HistoryOutlined,
} from '@ant-design/icons'
import { useState, useMemo } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { getAppName } from '../store/configStore'

const { Header, Sider, Content } = Layout

interface MenuItem {
  key: string
  icon?: React.ReactNode
  label: string
  children?: MenuItem[]
  permission?: string
}

export function AppLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const [passwordModalVisible, setPasswordModalVisible] = useState(false)
  const [passwordInput, setPasswordInput] = useState('')
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout, hasPermission } = useAuthStore()

  const getTodayPassword = () => {
    const today = new Date()
    const yyyy = today.getFullYear()
    const mm = String(today.getMonth() + 1).padStart(2, '0')
    const dd = String(today.getDate()).padStart(2, '0')
    return `${yyyy}${mm}${dd}`
  }

  const allMenuItems: MenuItem[] = [
    { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘', permission: 'dashboard:read' },
    { key: '/material', icon: <BoxPlotOutlined />, label: '物料主数据', permission: 'material:read' },
    { key: '/shelf', icon: <DatabaseOutlined />, label: '料架管理', permission: 'shelf:read' },
    { key: '/inventory', icon: <ContainerOutlined />, label: '库存管理', permission: 'inventory:read' },
    { key: '/receipt', icon: <ReadOutlined />, label: '入库收料', permission: 'receipt:read' },
    { key: '/issue', icon: <SendOutlined />, label: '发料管理', permission: 'issue:read' },
    { key: '/xr', icon: <DesktopOutlined />, label: '点料机管理', permission: 'xr:read' },
    { key: '/bom', icon: <FileExcelOutlined />, label: 'BOM管理', permission: 'bom:read' },
    { key: '/report', icon: <BarChartOutlined />, label: '报表统计', permission: 'report:read' },
    { key: '/operation-history', icon: <HistoryOutlined />, label: '作业履历', permission: 'operation-history:read' },
    {
      key: 'admin',
      icon: <SettingOutlined />,
      label: '系统管理',
      children: [
        { key: '/settings', label: '系统设置', permission: 'settings:read' },
        { key: '/barcode-definitions', label: '条码定义', permission: 'barcode:read' },
        { key: '/users', label: '用户管理', permission: 'user:read' },
        { key: '/roles', label: '角色管理', permission: 'role:read' },
        { key: '/customers', label: '客户管理', permission: 'customer:read' },
        { key: '/suppliers', label: '供应商管理', permission: 'supplier:read' },
        { key: '/app-download', icon: <DownloadOutlined />, label: 'PDA下载', permission: 'app-download:read' },
        { key: '/app-version', icon: <DownloadOutlined />, label: 'APP版本更新', permission: 'app-version:read' },
        { key: '/backup', icon: <CloudUploadOutlined />, label: '数据备份', permission: 'backup:read' },
        { key: '/light-debug', icon: <BugOutlined />, label: '灯控调试', permission: 'light-debug:read' },
      ],
    },
  ]

  // Filter menu items based on permissions
  const menuItems = useMemo(() => {
    return allMenuItems
      .map((item) => {
        if (item.children) {
          const filteredChildren = item.children.filter((child) => {
            if (!child.permission) return true
            return hasPermission(child.permission)
          })
          if (filteredChildren.length === 0) return null
          return { ...item, children: filteredChildren }
        }
        if (item.permission && !hasPermission(item.permission)) return null
        return item
      })
      .filter(Boolean) as any
  }, [user?.permissions])

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

  // Find selected key - if current path starts with a menu key, select it
  const selectedKey = location.pathname

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
          selectedKeys={[selectedKey]}
          defaultOpenKeys={['admin']}
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
                {user?.role && (
                  <span style={{ fontSize: 12, color: '#999' }}>
                    ({user.role === 'admin' ? '管理员' : user.role === 'supervisor' ? '主管' : user.role === 'operator' ? '操作员' : user.role})
                  </span>
                )}
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
