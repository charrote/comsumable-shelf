import { Card, Button, Typography, Space, Tag, Steps, Alert, QRCode, Divider, Collapse } from 'antd'
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

const APP_VERSION = '3.0.0'
const BUILD_NUMBER = 'release-20260627'
const APK_PATH = '/apk/app-release.apk'

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
                下载 APK
              </Button>
              <Alert
                message="正式发布版本"
                description="首次使用请设置正确的生产服务器地址"
                type="success"
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
        {/* v3.0.0 — 默认展开 */}
        <Divider orientation="left" plain>
          v3.0.0 (2026-06-27)
        </Divider>
        <ul style={{ paddingLeft: 20, lineHeight: 2 }}>
          <li>全版本号升级至 3.0.0：统一 PDA 端首页/设置页/登录页版本号显示</li>
          <li>智能料架更换底层硬件通信协议改为 HTTP REST API（JSON/UTF-8） 控灯</li>
          <li>重构入料上架、料盘下架、新灯控联动逻辑；增加料架回调；增加灯控调试与灯控管理</li>
          <li>出库策略管理移至 Web 管理端：移动端不再允许修改出库策略，由后台统一控制</li>
          <li>登录页新增版本号显示：登录页底部显示当前版本信息</li>
          <li>修复出库策略不生效：FIFO 计算时正确传入用户在设置页选择的策略参数</li>
        </ul>

        {/* 历史版本 — 折叠 */}
        <Collapse
          ghost
          size="small"
          items={[
            {
              key: 'v2.1',
              label: 'v2.1 (2026-06-24)',
              children: (
                <ul style={{ paddingLeft: 20, lineHeight: 2, marginBottom: 0 }}>
                  <li>Release 重新构建：包含最新源码，优化 R8 混淆与资源压缩，APK 体积 29MB</li>
                  <li>库存盘号修复：WEB 库存管理页库存盘号列显示正确的 Reel 编码格式（REEL-YYYYMMDD-XXXX）</li>
                  <li>前端缓存优化：Vite 构建产物启用内容哈希文件名，解决浏览器缓存不更新的问题</li>
                  <li>后端 API 增强：库存列表接口增加 reel_code 字段返回</li>
                </ul>
              ),
            },
            {
              key: 'v2.0',
              label: 'v2.0 (2026-06-24)',
              children: (
                <ul style={{ paddingLeft: 20, lineHeight: 2, marginBottom: 0 }}>
                  <li>底部 Tab 导航重构：首页/收料入库/料盘上架/扫码出库/库存跟踪，设置移至右上角齿轮入口</li>
                  <li>操作员统一配置：设置页全局设置操作员，所有业务页面自动读取无需重复输入</li>
                  <li>摄像头扫码：调用设备摄像头扫描条码，支持多种条码格式（Code128/QR/Data Matrix/EAN等）</li>
                  <li>动态服务器地址：登录页/设置页可运行时配置 API 地址，支持多环境切换</li>
                  <li>Release 构建优化：APK 体积从 177MB 缩减至 24MB（ABI 过滤 + R8 混淆 + 资源压缩）</li>
                  <li>正式服务器地址：默认连接生产环境 http://101.34.63.68:8080/api</li>
                  <li>收料单增加采购单号；收料详情增加取消功能；扫码流程优化</li>
                  <li>BOM 导入优化：增加产品编码/产品名称录入，列表关联显示</li>
                  <li>库存管理优化：增加客户列/客户筛选/状态筛选/Excel导出</li>
                  <li>仪表盘优化：移除快速操作区，摘要卡片简化，版本号 2.0</li>
                </ul>
              ),
            },
            {
              key: 'v1.1',
              label: 'v1.1.0 (2026-06-18)',
              children: (
                <ul style={{ paddingLeft: 20, lineHeight: 2, marginBottom: 0 }}>
                  <li>服务端 IP 自动注入：Debug 包自动连本地/远程，Release 包连生产地址，无需手动配置</li>
                  <li>系统名称动态化：APP_NAME 从后端配置文件读取，PDA 首页 + Web 后台统一显示"智能物料管理系统"</li>
                  <li>硬件模拟模式：新增 HARDWARE_SIMULATION 环境变量，无硬件时自动跳过 LED/打印机/料架传感器</li>
                  <li>新增 /api/system/info 接口：前端动态获取系统名称、版本号等信息</li>
                  <li>入库上架自动分配储位：扫码后自动匹配空储位，减少人工操作</li>
                  <li>FIFO 出库策略优化：支持 tail_first 策略，优先取出后入库的物料</li>
                  <li>LED 亮灯指令持久化 + 后台 Worker 自动处理状态流转</li>
                </ul>
              ),
            },
            {
              key: 'v1.0',
              label: 'v1.0.0 (2026-06-17)',
              children: (
                <ul style={{ paddingLeft: 20, lineHeight: 2, marginBottom: 0 }}>
                  <li>扫码入库：支持条码扫描、入库单创建、重复条码检测</li>
                  <li>扫码出库：支持出库单加载、LED 亮灯指引、拣货确认</li>
                  <li>补料上架：支持补料单创建、扫描上架、储位分配</li>
                  <li>库存跟踪：实时查看在库库存和流转记录</li>
                  <li>用户认证：登录/登出、Token 持久化</li>
                </ul>
              ),
            },
          ]}
        />
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
