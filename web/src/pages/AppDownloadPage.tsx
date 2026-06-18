import { Card, Button, Typography, Space, Tag, Steps, Alert, QRCode, Divider } from 'antd'
import {
  DownloadOutlined,
  AndroidOutlined,
  ScanOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  SmileOutlined,
} from '@ant-design/icons'
import { getAppName } from '../store/configStore'

const { Title, Text, Paragraph } = Typography

const APP_VERSION = '1.1.0'
const BUILD_NUMBER = 'debug-20260618'
const APK_PATH = '/apk/app-debug.apk'
const APK_SIZE = '20 MB'

export function AppDownloadPage() {
  const appName = getAppName()
  const downloadUrl = `${window.location.origin}${APK_PATH}`

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      {/* 头部区域 */}
      <div style={{ textAlign: 'center', marginBottom: 32 }}>
        <div
          style={{
            width: 80,
            height: 80,
            borderRadius: 20,
            background: 'linear-gradient(135deg, #1677ff 0%, #0958d9 100%)',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: 16,
            boxShadow: '0 4px 12px rgba(22,119,255,0.3)',
          }}
        >
          <AndroidOutlined style={{ fontSize: 40, color: '#fff' }} />
        </div>
        <Title level={3} style={{ marginBottom: 4 }}>
          {appName} PDA
        </Title>
        <Text type="secondary" style={{ fontSize: 16 }}>
          SMT 车间物料管理 — 移动端
        </Text>
        <div style={{ marginTop: 8 }}>
          <Tag color="blue" style={{ fontSize: 13, padding: '2px 12px' }}>
            v{APP_VERSION}
          </Tag>
          <Tag style={{ fontSize: 13, padding: '2px 12px' }}>{BUILD_NUMBER}</Tag>
        </div>
      </div>

      {/* 下载卡片 */}
      <Card
        style={{
          marginBottom: 24,
          borderRadius: 12,
          border: '1px solid #e8e8e8',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 32,
            flexWrap: 'wrap',
            justifyContent: 'center',
          }}
        >
          {/* 左侧：下载信息 */}
          <div style={{ flex: 1, minWidth: 250 }}>
            <Title level={4} style={{ marginTop: 0 }}>
              <DownloadOutlined /> 下载安装包
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 16 }}>
              适用于 Android 8.0 (API 26) 及以上版本的 PDA 设备
            </Paragraph>
            <Space direction="vertical" style={{ width: '100%' }} size={12}>
              <Button
                type="primary"
                size="large"
                icon={<DownloadOutlined />}
                href={APK_PATH}
                download
                block
                style={{ height: 48, fontSize: 16, borderRadius: 8 }}
              >
                下载 APK ({APK_SIZE})
              </Button>
              <Alert
                message="测试版本说明"
                description="此版本为 Debug 构建，用于功能验证和集成测试。请勿用于生产环境。"
                type="info"
                showIcon
                style={{ borderRadius: 8 }}
              />
            </Space>
          </div>

          {/* 右侧：二维码 */}
          <div
            style={{
              textAlign: 'center',
              padding: '8px 16px',
              background: '#fafafa',
              borderRadius: 12,
            }}
          >
            <QRCode
              value={downloadUrl}
              size={140}
              icon="https://cdn.jsdelivr.net/npm/@ant-design/icons-svg@4.4.0/inline-svg/outlined/android.svg"
              style={{ marginBottom: 8 }}
            />
            <div>
              <ScanOutlined style={{ marginRight: 4 }} />
              <Text type="secondary" style={{ fontSize: 12 }}>
                扫码下载
              </Text>
            </div>
          </div>
        </div>
      </Card>

      {/* 安装说明 */}
      <Card
        title={
          <Space>
            <InfoCircleOutlined />
            <span>安装说明</span>
          </Space>
        }
        style={{ marginBottom: 24, borderRadius: 12 }}
      >
        <Steps
          direction="vertical"
          size="small"
          current={-1}
          items={[
            {
              title: '下载 APK',
              description: '点击上方按钮下载安装包，或用手机扫描二维码。',
              icon: <DownloadOutlined />,
            },
            {
              title: '允许未知来源安装',
              description:
                '前往「设置 → 安全」中开启「允许安装未知来源应用」。企业 PDA 通常已默认开启。',
              icon: <CheckCircleOutlined />,
            },
            {
              title: '打开 APK 文件安装',
              description:
                '在文件管理器中找到下载的 app-debug.apk，点击安装即可。',
              icon: <AndroidOutlined />,
            },
            {
              title: '登录使用',
              description:
                `打开 App，输入服务器地址和账号密码即可连接${appName}。`,
              icon: <SmileOutlined />,
            },
          ]}
        />
      </Card>

      {/* 版本历史 */}
      <Card
        title={
          <Space>
            <InfoCircleOutlined />
            <span>更新日志</span>
          </Space>
        }
        style={{ borderRadius: 12 }}
      >
        <Divider orientation="left" plain>
          v1.1.0 (2026-06-18)
        </Divider>
        <ul style={{ paddingLeft: 20, lineHeight: 2 }}>
          <li>服务端 IP 自动注入：Debug 包自动连本地/远程，Release 包连生产地址，无需手动配置</li>
          <li>系统名称动态化：APP_NAME 从后端配置文件读取，PDA 首页 + Web 后台统一显示"智能物料管理系统"</li>
          <li>硬件模拟模式：新增 HARDWARE_SIMULATION 环境变量，无硬件时自动跳过 LED/打印机/料架传感器</li>
          <li>新增 /api/system/info 接口：前端动态获取系统名称、版本号等信息</li>
          <li>入库上架自动分配储位：扫码后自动匹配空储位，减少人工操作</li>
          <li>FIFO 出库策略优化：支持 tail_first 策略，优先取出后入库的物料</li>
          <li>LED 亮灯指令持久化 + 后台 Worker 自动处理状态流转</li>
        </ul>
        <Divider orientation="left" plain>
          v1.0.0 (2026-06-17)
        </Divider>
        <ul style={{ paddingLeft: 20, lineHeight: 2 }}>
          <li>扫码入库：支持条码扫描、入库单创建、重复条码检测</li>
          <li>扫码出库：支持出库单加载、LED 亮灯指引、拣货确认</li>
          <li>补料上架：支持补料单创建、扫描上架、储位分配</li>
          <li>库存跟踪：实时查看在库库存和流转记录</li>
          <li>用户认证：登录/登出、Token 持久化</li>
        </ul>
      </Card>

      {/* 底部 */}
      <div style={{ textAlign: 'center', marginTop: 24, paddingBottom: 16 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {appName} · PDA 移动端 · Build {BUILD_NUMBER}
        </Text>
      </div>
    </div>
  )
}
