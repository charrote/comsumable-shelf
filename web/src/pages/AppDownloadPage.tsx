import { useEffect, useState, useCallback } from 'react'
import { Card, Button, Typography, Space, Tag, Steps, Alert, QRCode, Divider, Collapse, Spin, message } from 'antd'
import {
  DownloadOutlined,
  AndroidOutlined,
  ScanOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  SmileOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { getAppName } from '../store/configStore'

const { Title, Text, Paragraph } = Typography

/** latest-apk.json 的响应结构 */
interface ApkManifest {
  version: string
  buildNumber: string
  apkPath: string
  updatedAt: string
}

/** 解析后的版本日志条目 */
interface ChangelogVersion {
  title: string       // e.g. "v3.0.0 (2026-06-27)"
  version: string     // e.g. "3.0.0"
  date: string        // e.g. "2026-06-27"
  items: string[]     // list items
}

/** 默认回退值（当 latest-apk.json 不存在时使用） */
const FALLBACK: ApkManifest = {
  version: '3.0.0',
  buildNumber: 'release-20260627',
  apkPath: '/apk/smes-pda.3.0.0.apk',
  updatedAt: '',
}

const MANIFEST_URL = '/apk/latest-apk.json'

/** 解析 CHANGELOG.md 内容为结构化版本列表 */
function parseChangelog(markdown: string): ChangelogVersion[] {
  // 按 --- 分割各版本区块
  const sections = markdown.split(/\n---\n/)
  const versions: ChangelogVersion[] = []

  for (const section of sections) {
    const lines = section.trim().split('\n')
    // 找标题行: ## v1.2.3 (2026-01-01)
    const titleLine = lines.find(l => /^##\s+v/.test(l))
    if (!titleLine) continue

    const title = titleLine.replace(/^##\s+/, '').trim()
    // 解析版本号和日期
    const match = title.match(/^v?([\d.]+)\s*\(([^)]+)\)/)
    if (!match) continue

    const version = match[1]
    const date = match[2]

    // 提取列表项（以 - 或 * 开头）
    const items = lines
      .filter(l => /^\s*[-*]\s/.test(l))
      .map(l => l.replace(/^\s*[-*]\s/, '').trim())

    if (version) {
      versions.push({ title, version, date, items })
    }
  }

  return versions
}

export function AppDownloadPage() {
  const appName = getAppName()

  const [manifest, setManifest] = useState<ApkManifest>(FALLBACK)
  const [loading, setLoading] = useState(true)
  const [changelogVersions, setChangelogVersions] = useState<ChangelogVersion[]>([])
  const [changelogLoading, setChangelogLoading] = useState(true)

  /** 从服务器获取 latest-apk.json */
  const fetchLatestManifest = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch(MANIFEST_URL, { cache: 'no-store' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: ApkManifest = await res.json()
      if (data?.version && data?.apkPath) {
        setManifest(data)
      } else {
        throw new Error('清单数据不完整')
      }
    } catch {
      setManifest(FALLBACK)
    } finally {
      setLoading(false)
    }
  }, [])

  /** 从 API 获取 CHANGELOG.md 内容并解析 */
  const fetchChangelog = useCallback(async () => {
    setChangelogLoading(true)
    try {
      const res = await fetch('/api/app/changelog', { cache: 'no-store' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const parsed = parseChangelog(data.content || '')
      setChangelogVersions(parsed)
    } catch {
      // 静默失败，不展示更新日志
      setChangelogVersions([])
    } finally {
      setChangelogLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchLatestManifest()
    fetchChangelog()
  }, [fetchLatestManifest, fetchChangelog])

  const { version, buildNumber, apkPath } = manifest
  const downloadUrl = `${window.location.origin}${apkPath}`

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
        <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
          <Spin spinning={loading} size="small" />
          <Tag color="blue" style={{ fontSize: 13, padding: '2px 12px' }}>
            v{version}
          </Tag>
          <Tag style={{ fontSize: 13, padding: '2px 12px' }}>{buildNumber}</Tag>
          <Button
            type="text"
            size="small"
            icon={<ReloadOutlined />}
            loading={loading}
            onClick={fetchLatestManifest}
            title="重新检测最新版本"
          />
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
                href={apkPath}
                download={`smes-pda.${version}.apk`}
                block
                disabled={loading}
                style={{ height: 48, fontSize: 16, borderRadius: 8 }}
              >
                {loading ? '检测中...' : `下载 APK v${version}`}
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
                '在文件管理器中找到下载的 smes-pda.apk，点击安装即可。',
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

      {/* 版本历史 — 从 CHANGELOG.md 动态渲染 */}
      <Card
        title={
          <Space>
            <InfoCircleOutlined />
            <span>更新日志</span>
          </Space>
        }
        style={{ borderRadius: 12 }}
      >
        <Spin spinning={changelogLoading}>
          {changelogVersions.length > 0 ? (
            <>
              {/* 最新版本 — 默认展开 */}
              <Divider orientation="left" plain>
                {changelogVersions[0].title}
              </Divider>
              <ul style={{ paddingLeft: 20, lineHeight: 2 }}>
                {changelogVersions[0].items.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>

              {/* 历史版本 — 折叠 */}
              {changelogVersions.length > 1 && (
                <Collapse
                  ghost
                  size="small"
                  items={changelogVersions.slice(1).map((v) => ({
                    key: v.version,
                    label: v.title,
                    children: (
                      <ul style={{ paddingLeft: 20, lineHeight: 2, marginBottom: 0 }}>
                        {v.items.map((item, i) => (
                          <li key={i}>{item}</li>
                        ))}
                      </ul>
                    ),
                  }))}
                />
              )}
            </>
          ) : (
            !changelogLoading && (
              <Text type="secondary">暂无更新日志</Text>
            )
          )}
        </Spin>
      </Card>

      {/* 底部 */}
      <div style={{ textAlign: 'center', marginTop: 24, paddingBottom: 16 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {appName} · PDA 移动端 · Build {buildNumber}
        </Text>
      </div>
    </div>
  )
}
