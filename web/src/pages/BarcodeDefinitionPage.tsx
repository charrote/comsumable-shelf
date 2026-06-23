import { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Button, Modal, Input, Select, Space, Tag, Spin,
  message, Popconfirm, Typography, Divider, Alert, Descriptions,
} from 'antd'
import {
  PlusOutlined, EditOutlined, DeleteOutlined,
  ExperimentOutlined,
} from '@ant-design/icons'
import {
  getBarcodeDefinitionsApi, createBarcodeDefinitionApi,
  updateBarcodeDefinitionApi, deleteBarcodeDefinitionApi,
  previewBarcodeSplitApi, testBarcodeDefinitionApi,
} from '../api'

const { Title, Text } = Typography

// ── Types ──
interface FieldMapping {
  field: string
  label: string
  source: string
}

interface SegmentDef {
  segment_index: number
  segment_sample?: string
  field_mapping: string
  field_label: string
}

interface DefinitionRecord {
  id: number
  name: string
  delimiter: string
  sample_barcode: string
  is_active: number
  segments: SegmentDef[]
  created_at?: string
  updated_at?: string
}

interface PreviewSegment {
  segment_index: number
  value: string
}

const FIELD_MAPPING_OPTIONS: { field: string; label: string; group: string }[] = [
  // 物料基础数据
  { field: 'material_code', label: '物料编码', group: '物料基础数据' },
  { field: 'material_name', label: '物料名称', group: '物料基础数据' },
  { field: 'spec', label: '规格型号', group: '物料基础数据' },
  { field: 'unit', label: '单位', group: '物料基础数据' },
  { field: 'qty_per_pallet', label: '每盘数量', group: '物料基础数据' },
  // 收料主字段
  { field: 'quantity', label: '数量', group: '收料主字段' },
  { field: 'batch_no', label: '批次号', group: '收料主字段' },
  { field: 'date_code', label: '生产日期/周期代码', group: '收料主字段' },
  { field: 'customer_material_code', label: '客户物料编码', group: '收料主字段' },
]

export function BarcodeDefinitionPage() {
  // ── State ──
  const [definitions, setDefinitions] = useState<DefinitionRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)

  // Form fields
  const [formName, setFormName] = useState('')
  const [formDelimiter, setFormDelimiter] = useState('')
  const [formSampleBarcode, setFormSampleBarcode] = useState('')
  const [formSegments, setFormSegments] = useState<SegmentDef[]>([])
  const [previewSegments, setPreviewSegments] = useState<PreviewSegment[]>([])

  // Test modal
  const [testModalOpen, setTestModalOpen] = useState(false)
  const [testingDefId, setTestingDefId] = useState<number | null>(null)
  const [testBarcode, setTestBarcode] = useState('')
  const [testResult, setTestResult] = useState<any>(null)
  const [testLoading, setTestLoading] = useState(false)

  // ── Load data ──
  const loadDefinitions = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getBarcodeDefinitionsApi()
      setDefinitions(Array.isArray(res.data) ? res.data : [])
    } catch (err: any) {
      message.error(err.response?.data?.detail || '加载条码定义失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDefinitions()
  }, [loadDefinitions])

  // ── Preview split ──
  const handlePreview = useCallback(async () => {
    if (!formSampleBarcode || !formDelimiter) {
      setPreviewSegments([])
      return
    }
    try {
      const res = await previewBarcodeSplitApi(formSampleBarcode, formDelimiter)
      const data = res.data
      setPreviewSegments(data.segments || [])

      // Auto-generate segments from preview
      if (data.segments && data.segments.length > 0) {
        const newSegments: SegmentDef[] = data.segments.map((seg: PreviewSegment) => {
          const existing = formSegments.find(s => s.segment_index === seg.segment_index)
          return existing || {
            segment_index: seg.segment_index,
            segment_sample: seg.value,
            field_mapping: '',
            field_label: '',
          }
        })
        setFormSegments(newSegments)
      }
    } catch (err: any) {
      // Don't show error during typing, just clear preview
      setPreviewSegments([])
    }
  }, [formSampleBarcode, formDelimiter])

  // Auto preview when sample or delimiter changes
  useEffect(() => {
    handlePreview()
  }, [formSampleBarcode, formDelimiter, handlePreview])

  // ── Open create modal ──
  const handleAdd = () => {
    setEditingId(null)
    setFormName('')
    setFormDelimiter('')
    setFormSampleBarcode('')
    setFormSegments([])
    setPreviewSegments([])
    setModalOpen(true)
  }

  // ── Open edit modal ──
  const handleEdit = async (record: DefinitionRecord) => {
    setEditingId(record.id)
    setFormName(record.name)
    setFormDelimiter(record.delimiter)
    setFormSampleBarcode(record.sample_barcode)
    setFormSegments([...record.segments])
    // Trigger preview
    try {
      const res = await previewBarcodeSplitApi(record.sample_barcode, record.delimiter)
      setPreviewSegments(res.data.segments || [])
    } catch {
      setPreviewSegments([])
    }
    setModalOpen(true)
  }

  // ── Update segment field mapping ──
  const handleSegmentMappingChange = (index: number, field: string) => {
    if (!field) {
      // 选择"不映射"
      setFormSegments(prev =>
        prev.map(s =>
          s.segment_index === index
            ? { ...s, field_mapping: '', field_label: '' }
            : s
        )
      )
      return
    }
    const option = FIELD_MAPPING_OPTIONS.find(o => o.field === field)
    setFormSegments(prev =>
      prev.map(s =>
        s.segment_index === index
          ? { ...s, field_mapping: field, field_label: option?.label || field }
          : s
      )
    )
  }

  // ── Save ──
  const handleSave = async () => {
    // Validate
    if (!formName.trim()) {
      message.error('请输入条码定义名称')
      return
    }
    if (!formDelimiter.trim()) {
      message.error('请输入分隔符')
      return
    }
    if (!formSampleBarcode.trim()) {
      message.error('请输入样例条码')
      return
    }

    setSaving(true)
    try {
      const payload = {
        name: formName.trim(),
        delimiter: formDelimiter.trim(),
        sample_barcode: formSampleBarcode.trim(),
        segments: formSegments.map(s => ({
          segment_index: s.segment_index,
          segment_sample: s.segment_sample || '',
          field_mapping: s.field_mapping,
          field_label: s.field_label,
        })),
      }

      if (editingId) {
        await updateBarcodeDefinitionApi(editingId, payload)
        message.success('条码定义已更新')
      } else {
        await createBarcodeDefinitionApi(payload)
        message.success('条码定义已创建')
      }
      setModalOpen(false)
      await loadDefinitions()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  // ── Delete ──
  const handleDelete = async (id: number) => {
    try {
      await deleteBarcodeDefinitionApi(id)
      message.success('条码定义已删除')
      await loadDefinitions()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '删除失败')
    }
  }

  // ── Test barcode ──
  const handleTest = async () => {
    if (!testingDefId || !testBarcode.trim()) {
      message.error('请输入待测试的条码')
      return
    }
    setTestLoading(true)
    setTestResult(null)
    try {
      const res = await testBarcodeDefinitionApi(testingDefId, testBarcode.trim())
      setTestResult(res.data)
    } catch (err: any) {
      message.error(err.response?.data?.detail || '测试失败')
    } finally {
      setTestLoading(false)
    }
  }

  const openTestModal = (record: DefinitionRecord) => {
    setTestingDefId(record.id)
    setTestBarcode('')
    setTestResult(null)
    setTestModalOpen(true)
  }

  // ── Columns ──
  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
    },
    {
      title: '分隔符',
      dataIndex: 'delimiter',
      key: 'delimiter',
      width: 100,
      render: (val: string) => <Tag color="blue">{val}</Tag>,
    },
    {
      title: '样例条码',
      dataIndex: 'sample_barcode',
      key: 'sample_barcode',
      ellipsis: true,
    },
    {
      title: '段数',
      key: 'seg_count',
      width: 80,
      render: (_: any, record: DefinitionRecord) => record.segments?.length || 0,
    },
    {
      title: '映射',
      key: 'mappings',
      ellipsis: true,
      render: (_: any, record: DefinitionRecord) => (
        <Space size={4} wrap>
          {(record.segments || []).map((seg: SegmentDef) => (
            seg.field_mapping ? (
              <Tag key={seg.segment_index} color="green">
                [{seg.segment_index}]{seg.field_label}
              </Tag>
            ) : (
              <Tag key={seg.segment_index} color="default">
                [{seg.segment_index}]忽略
              </Tag>
            )
          ))}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (val: number) =>
        val === 1 ? <Tag color="success">启用</Tag> : <Tag color="default">禁用</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: DefinitionRecord) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<ExperimentOutlined />}
            onClick={() => openTestModal(record)}
          >
            测试
          </Button>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除该条码定义？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>条码定义管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          新建条码定义
        </Button>
      </div>

      <Alert
        message="什么是条码定义？"
        description="对于固定分隔符格式的供应商条码（如 Y.C.C104KFFPS6030#20260303#4000#XC20260123020），
        可定义分段规则：第一段 → 物料编码，第二段 → 生产日期，第三段 → 数量，第四段 → 批次号。
        系统在收料扫码时会优先按条码定义进行解析，快速识别物料并自动填入对应字段。"
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      <Card>
        <Spin spinning={loading}>
          <Table
            columns={columns}
            dataSource={definitions}
            rowKey="id"
            pagination={false}
          />
        </Spin>
      </Card>

      {/* ── Create/Edit Modal ── */}
      <Modal
        title={editingId ? '编辑条码定义' : '新建条码定义'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSave}
        confirmLoading={saving}
        width={800}
        okText="保存"
        cancelText="取消"
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {/* Name */}
          <div>
            <Text strong>定义名称</Text>
            <Input
              value={formName}
              onChange={e => setFormName(e.target.value)}
              placeholder="例如：标准供应商条码（#分隔）"
              style={{ marginTop: 4 }}
            />
          </div>

          {/* Sample Barcode + Delimiter */}
          <div style={{ display: 'flex', gap: 16 }}>
            <div style={{ flex: 1 }}>
              <Text strong>样例条码</Text>
              <Input
                value={formSampleBarcode}
                onChange={e => setFormSampleBarcode(e.target.value)}
                placeholder="扫描或输入样例条码"
                style={{ marginTop: 4 }}
              />
            </div>
            <div style={{ width: 120 }}>
              <Text strong>分隔符</Text>
              <Input
                value={formDelimiter}
                onChange={e => setFormDelimiter(e.target.value)}
                placeholder="#"
                maxLength={5}
                style={{ marginTop: 4, textAlign: 'center' }}
              />
            </div>
          </div>

          {/* Preview */}
          {previewSegments.length > 0 && (
            <>
              <Divider style={{ margin: '8px 0' }} />
              <Text strong>拆分预览：</Text>
              <div style={{
                background: '#f5f5f5',
                padding: 12,
                borderRadius: 6,
                display: 'flex',
                gap: 8,
                flexWrap: 'wrap',
              }}>
                {previewSegments.map((seg, idx) => (
                  <Tag key={idx} color="processing" style={{ fontSize: 14, padding: '2px 12px' }}>
                    <Text strong>[{seg.segment_index}]</Text> {seg.value}
                  </Tag>
                ))}
              </div>
            </>
          )}

          {/* Segment Mapping */}
          {formSegments.length > 0 && (
            <>
              <Divider style={{ margin: '8px 0' }} />
              <Text strong>段字段映射（请为每段选择对应的字段）：</Text>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
                {formSegments.map((seg, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      padding: '8px 12px',
                      background: '#fafafa',
                      borderRadius: 6,
                      border: '1px solid #f0f0f0',
                    }}
                  >
                    <Tag color="blue" style={{ minWidth: 60, textAlign: 'center' }}>
                      第 {seg.segment_index + 1} 段
                    </Tag>
                    <Text code style={{ minWidth: 120 }}>{seg.segment_sample || previewSegments[idx]?.value || ''}</Text>
                    <Select
                      style={{ flex: 1 }}
                      value={seg.field_mapping || undefined}
                      onChange={val => handleSegmentMappingChange(seg.segment_index, val)}
                      placeholder="选择映射字段（留空=忽略）"
                      allowClear
                      onClear={() => handleSegmentMappingChange(seg.segment_index, '')}
                      options={[
                        {
                          label: '━ 不映射 ━',
                          options: [
                            { label: '不映射（忽略该段）', value: '' },
                          ],
                        },
                        {
                          label: '物料基础数据',
                          options: FIELD_MAPPING_OPTIONS
                            .filter(o => o.group === '物料基础数据')
                            .map(o => ({ label: `${o.label} (${o.field})`, value: o.field })),
                        },
                        {
                          label: '收料主字段',
                          options: FIELD_MAPPING_OPTIONS
                            .filter(o => o.group === '收料主字段')
                            .map(o => ({ label: `${o.label} (${o.field})`, value: o.field })),
                        },
                      ]}
                    />
                  </div>
                ))}
              </div>
              {!formSegments.some(s => s.field_mapping === 'material_code') && (
                <Text type="warning" style={{ fontSize: 12 }}>
                  ⚠ 建议至少有一段映射到「物料编码」，否则系统无法自动识别物料
                </Text>
              )}
            </>
          )}
        </Space>
      </Modal>

      {/* ── Test Modal ── */}
      <Modal
        title="条码定义测试"
        open={testModalOpen}
        onCancel={() => setTestModalOpen(false)}
        footer={null}
        width={600}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Text strong>待测试条码</Text>
            <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
              <Input
                value={testBarcode}
                onChange={e => setTestBarcode(e.target.value)}
                placeholder="输入或扫描实际条码"
                onPressEnter={handleTest}
              />
              <Button
                type="primary"
                icon={<ExperimentOutlined />}
                onClick={handleTest}
                loading={testLoading}
              >
                测试
              </Button>
            </div>
          </div>

          {testResult && (
            <>
              <Divider style={{ margin: '8px 0' }} />
              <Descriptions
                column={1}
                bordered
                size="small"
                title={
                  testResult.matched
                    ? <Text type="success">✅ 匹配成功</Text>
                    : <Text type="warning">❌ 匹配失败</Text>
                }
              >
                <Descriptions.Item label="条码定义">{testResult.definition_name}</Descriptions.Item>
                <Descriptions.Item label="分隔符">
                  <Tag color="blue">{testResult.delimiter}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="结果说明">{testResult.message}</Descriptions.Item>
              </Descriptions>

              {testResult.matched && testResult.segments && (
                <div style={{ marginTop: 8 }}>
                  <Text strong>解析结果：</Text>
                  <Table
                    dataSource={testResult.segments}
                    columns={[
                      { title: '段', dataIndex: 'segment_index', key: 'idx', width: 60, render: (v: number) => `第${v + 1}段` },
                      { title: '解析值', dataIndex: 'value', key: 'value' },
                      { title: '映射字段', dataIndex: 'field_label', key: 'field' },
                    ]}
                    rowKey="segment_index"
                    pagination={false}
                    size="small"
                  />
                </div>
              )}
            </>
          )}
        </Space>
      </Modal>
    </div>
  )
}
