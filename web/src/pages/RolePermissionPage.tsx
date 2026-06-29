import { useState, useEffect } from 'react'
import { Modal, Tree, Button, Spin, message, Checkbox, Space, Tag, Divider } from 'antd'
import { getPermissionsGroupedApi, getRoleApi, updateRolePermissionsApi } from '../api'

interface RolePermissionPageProps {
  role: any
  open: boolean
  onClose: () => void
}

export function RolePermissionPage({ role, open, onClose }: RolePermissionPageProps) {
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [permGroups, setPermGroups] = useState<any[]>([])
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [expandedModules, setExpandedModules] = useState<string[]>([])

  const loadData = async () => {
    if (!open) return
    setLoading(true)
    try {
      const [groupRes, roleRes] = await Promise.all([
        getPermissionsGroupedApi(),
        getRoleApi(role.id),
      ])
      setPermGroups(Array.isArray(groupRes.data) ? groupRes.data : [])

      // Get currently assigned permission IDs
      const roleData = roleRes.data
      if (roleData.permission_ids) {
        setSelectedIds(roleData.permission_ids)
      }

      // Auto-expand all modules
      const groups = Array.isArray(groupRes.data) ? groupRes.data : []
      setExpandedModules(groups.map((g: any) => g.module))
    } catch (err: any) {
      message.error('加载权限数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [open, role.id])

  const togglePermission = (permId: number) => {
    setSelectedIds((prev) =>
      prev.includes(permId)
        ? prev.filter((id) => id !== permId)
        : [...prev, permId]
    )
  }

  const toggleModule = (module: string, permIds: number[]) => {
    const allSelected = permIds.every((id) => selectedIds.includes(id))
    if (allSelected) {
      setSelectedIds((prev) => prev.filter((id) => !permIds.includes(id)))
    } else {
      setSelectedIds((prev) => {
        const newIds = [...prev]
        for (const id of permIds) {
          if (!newIds.includes(id)) {
            newIds.push(id)
          }
        }
        return newIds
      })
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateRolePermissionsApi(role.id, selectedIds)
      message.success('角色权限已更新')
      onClose()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const moduleLabelMap: Record<string, string> = {
    dashboard: '仪表盘',
    material: '物料管理',
    shelf: '料架管理',
    inventory: '库存管理',
    receipt: '入库管理',
    issue: '发料管理',
    xr: '点料机管理',
    bom: 'BOM管理',
    report: '报表统计',
    settings: '系统设置',
    barcode: '条码定义',
    user: '用户管理',
    customer: '客户管理',
    supplier: '供应商管理',
    'app-download': 'PDA下载',
    'app-version': 'APP版本',
    backup: '数据备份',
    'light-debug': '灯控调试',
    role: '角色管理',
    permission: '权限查看',
  }

  return (
    <Modal
      title={`权限配置 - ${role.name} (${role.code})`}
      open={open}
      onCancel={onClose}
      footer={null}
      width={700}
    >
      <Spin spinning={loading}>
        <div style={{ maxHeight: 500, overflow: 'auto' }}>
          <div style={{ marginBottom: 12, color: '#666' }}>
            已选择 <Tag color="blue">{selectedIds.length}</Tag> 个权限
          </div>
          {permGroups.map((group: any) => {
            const permIds = group.permissions.map((p: any) => p.id)
            const allSelected = permIds.every((id: number) => selectedIds.includes(id))
            const someSelected = permIds.some((id: number) => selectedIds.includes(id))

            return (
              <div
                key={group.module}
                style={{
                  marginBottom: 12,
                  padding: 12,
                  border: '1px solid #f0f0f0',
                  borderRadius: 6,
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    marginBottom: 8,
                    cursor: 'pointer',
                  }}
                >
                  <Checkbox
                    checked={allSelected}
                    indeterminate={!allSelected && someSelected}
                    onChange={() => toggleModule(group.module, permIds)}
                  />
                  <strong style={{ marginLeft: 8, fontSize: 14 }}>
                    {moduleLabelMap[group.module] || group.module}
                  </strong>
                  <Tag style={{ marginLeft: 8 }}>{group.module}</Tag>
                </div>
                <div style={{ paddingLeft: 28 }}>
                  {group.permissions.map((perm: any) => (
                    <Checkbox
                      key={perm.id}
                      checked={selectedIds.includes(perm.id)}
                      onChange={() => togglePermission(perm.id)}
                      style={{ marginRight: 16, marginBottom: 6 }}
                    >
                      {perm.name}
                      <span style={{ color: '#999', fontSize: 12, marginLeft: 4 }}>
                        ({perm.code})
                      </span>
                    </Checkbox>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
        <div style={{ marginTop: 16, textAlign: 'right' }}>
          <Space>
            <Button onClick={onClose}>取消</Button>
            <Button type="primary" loading={saving} onClick={handleSave}>
              保存权限
            </Button>
          </Space>
        </div>
      </Spin>
    </Modal>
  )
}
