import { useState, useEffect } from 'react'
import { Card, Table, Button, Modal, Input, Space, Spin, message } from 'antd'
import { getSettingsApi, updateSettingApi } from '../api'

export function SystemSettingsPage() {
  const [settings, setSettings] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingKey, setEditingKey] = useState('')
  const [editingDescription, setEditingDescription] = useState('')
  const [editValue, setEditValue] = useState('')
  const [saving, setSaving] = useState(false)

  const loadSettings = async () => {
    setLoading(true)
    try {
      const res = await getSettingsApi()
      const data = res.data
      setSettings(Array.isArray(data) ? data : data.settings || [])
    } catch (err: any) {
      message.error(err.response?.data?.detail || '加载设置失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSettings()
  }, [])

  const handleEdit = (record: any) => {
    setEditingKey(record.key)
    setEditingDescription(record.description || '')
    setEditValue(record.value)
    setModalOpen(true)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateSettingApi(editingKey, editValue, editingDescription)
      message.success('修改成功')
      setModalOpen(false)
      await loadSettings()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '修改失败')
    } finally {
      setSaving(false)
    }
  }

  const columns = [
    { title: '设置项', dataIndex: 'key', key: 'key', width: 200 },
    { title: '描述', dataIndex: 'description', key: 'description' },
    { title: '值', dataIndex: 'value', key: 'value', width: 120 },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: any, record: any) => (
        <Button type="link" size="small" onClick={() => handleEdit(record)}>
          修改
        </Button>
      ),
    },
  ]

  return (
    <div>
      <h2>系统设置</h2>
      <Spin spinning={loading}>
        <Card>
          <Table
            columns={columns}
            dataSource={settings}
            pagination={false}
            rowKey="key"
          />
        </Card>
      </Spin>
      <Modal
        title="修改设置"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSave}
        confirmLoading={saving}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <strong>设置项：</strong>{editingKey}
          </div>
          <div>
            <strong>描述：</strong>{editingDescription}
          </div>
          <div>
            <strong>值：</strong>
            <Input
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              style={{ marginTop: 4 }}
            />
          </div>
        </Space>
      </Modal>
    </div>
  )
}
