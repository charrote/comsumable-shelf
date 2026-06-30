import { useState, useEffect, useRef } from 'react'
import {
  Card, Table, Button, Modal, Space, Spin, Tag, Tooltip,
  message, Popconfirm, Typography, Alert, Descriptions,
} from 'antd'
import {
  CloudUploadOutlined, DownloadOutlined,
  DeleteOutlined, ReloadOutlined, ExclamationCircleOutlined,
  CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined,
  ScanOutlined,
} from '@ant-design/icons'
import {
  getBackupsApi, createBackupApi,
  restoreBackupApi, deleteBackupApi,
  rescanBackupsApi,
} from '../api'
import dayjs from 'dayjs'

const { Text } = Typography

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const k = 1024
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + units[i]
}

const statusConfig: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  running: { color: 'processing', icon: <ClockCircleOutlined />, label: '备份中' },
  completed: { color: 'success', icon: <CheckCircleOutlined />, label: '已完成' },
  failed: { color: 'error', icon: <CloseCircleOutlined />, label: '失败' },
}

export function BackupManagePage() {
  const [backups, setBackups] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [restoring, setRestoring] = useState<number | null>(null)
  const [scanning, setScanning] = useState(false)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadBackups = async () => {
    setLoading(true)
    try {
      const res = await getBackupsApi()
      setBackups(res.data || [])
    } catch (err: any) {
      message.error(err.response?.data?.detail || '加载备份列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadBackups()
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
      }
    }
  }, [])

  // Poll for running backups
  const hasRunning = backups.some((b) => b.status === 'running')
  useEffect(() => {
    if (hasRunning) {
      pollingRef.current = setInterval(() => {
        loadBackups()
      }, 3000)
    } else {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
        pollingRef.current = null
      }
    }
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
      }
    }
  }, [hasRunning])

  const handleCreateBackup = async () => {
    setCreating(true)
    try {
      const res = await createBackupApi()
      message.success(res.data?.message || '备份任务已启动')
      await loadBackups()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '创建备份失败')
    } finally {
      setCreating(false)
    }
  }

  const handleRescan = async () => {
    setScanning(true)
    try {
      const res = await rescanBackupsApi()
      const found = res.data?.length || 0
      if (found > 0) {
        message.success(`扫描完成，发现 ${found} 个备份文件`)
      } else {
        message.info('未发现新的备份文件')
      }
      await loadBackups()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '扫描备份失败')
    } finally {
      setScanning(false)
    }
  }

  const handleRestore = (backupId: number) => {
    Modal.confirm({
      title: '确认恢复数据库',
      icon: <ExclamationCircleOutlined />,
      content: (
        <div>
          <Alert
            type="warning"
            showIcon
            message="此操作将覆盖当前数据库的所有数据！"
            description="恢复操作不可逆，建议先创建一次新的备份。恢复后系统将使用备份中的数据，请确保操作前已通知所有用户停止使用系统。"
            style={{ marginBottom: 12 }}
          />
          <Text type="danger">
            确认要继续吗？此操作需要管理员权限。
          </Text>
        </div>
      ),
      okText: '确认恢复',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        setRestoring(backupId)
        try {
          const res = await restoreBackupApi(backupId)
          if (res.data?.status === 'completed') {
            message.success(res.data?.message || '数据库恢复成功')
          } else {
            message.error(res.data?.message || '数据库恢复失败')
          }
          await loadBackups()
        } catch (err: any) {
          message.error(err.response?.data?.detail || '恢复操作失败')
        } finally {
          setRestoring(null)
        }
      },
    })
  }

  const handleDelete = async (backupId: number) => {
    try {
      const res = await deleteBackupApi(backupId)
      message.success(res.data?.message || '备份已删除')
      await loadBackups()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '删除备份失败')
    }
  }

  const columns = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
      ellipsis: true,
      render: (text: string, record: any) => (
        <Space>
          <DownloadOutlined />
          <span>{text}</span>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const cfg = statusConfig[status] || { color: 'default', icon: null, label: status }
        return (
          <Tag color={cfg.color} icon={cfg.icon}>
            {cfg.label}
          </Tag>
        )
      },
    },
    {
      title: '文件大小',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 110,
      render: (size: number) => formatFileSize(size),
    },
    {
      title: '数据库版本',
      dataIndex: 'db_version',
      key: 'db_version',
      width: 100,
    },
    {
      title: '操作人',
      dataIndex: 'operator',
      key: 'operator',
      width: 100,
    },
    {
      title: '备份时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (val: string) => val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: any, record: any) => (
        <Space>
          <Tooltip title="从此备份恢复数据库">
            <Button
              type="link"
              size="small"
              danger
              icon={<ReloadOutlined />}
              loading={restoring === record.id}
              disabled={record.status !== 'completed' || restoring !== null}
              onClick={() => handleRestore(record.id)}
            >
              恢复
            </Button>
          </Tooltip>
          <Popconfirm
            title="确认删除此备份？"
            description="备份文件将被永久删除。"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
              disabled={record.status === 'running'}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const expandable = {
    expandedRowRender: (record: any) => (
      <Descriptions size="small" column={2} style={{ margin: 0 }}>
        <Descriptions.Item label="文件路径">{record.filepath}</Descriptions.Item>
        <Descriptions.Item label="文件大小">{formatFileSize(record.file_size)}</Descriptions.Item>
        <Descriptions.Item label="数据库版本">{record.db_version || '-'}</Descriptions.Item>
        <Descriptions.Item label="操作人">{record.operator || '-'}</Descriptions.Item>
        <Descriptions.Item label="备份时间">
          {record.created_at ? dayjs(record.created_at).format('YYYY-MM-DD HH:mm:ss') : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="状态">{record.status}</Descriptions.Item>
        {record.error_message && (
          <Descriptions.Item label="错误信息" span={2}>
            <Text type="danger">{record.error_message}</Text>
          </Descriptions.Item>
        )}
      </Descriptions>
    ),
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>数据备份</h2>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadBackups} loading={loading}>
            刷新
          </Button>
          <Button
            icon={<ScanOutlined />}
            onClick={handleRescan}
            loading={scanning}
          >
            扫描备份
          </Button>
          <Button
            type="primary"
            icon={<CloudUploadOutlined />}
            onClick={handleCreateBackup}
            loading={creating}
          >
            创建备份
          </Button>
        </Space>
      </div>

      {hasRunning && (
        <Alert
          type="info"
          showIcon
          icon={<ClockCircleOutlined spin />}
          message="有备份任务正在执行，完成后将自动刷新列表"
          style={{ marginBottom: 16 }}
        />
      )}

      <Card>
        <Spin spinning={loading}>
          <Table
            columns={columns}
            dataSource={backups}
            rowKey="id"
            expandable={expandable}
            pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条记录` }}
            locale={{ emptyText: '暂无备份记录，点击"创建备份"开始' }}
          />
        </Spin>
      </Card>
    </div>
  )
}
