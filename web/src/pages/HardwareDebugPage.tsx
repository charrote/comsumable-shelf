import { Result, Button } from 'antd'
import { useNavigate } from 'react-router-dom'

/**
 * 硬件调试页面 — 已弃用。
 *
 * 旧版 Modbus 控制板调试功能已随智能料架 HTTP API 改造移除。
 * 料架硬件测试（LED 灯测试）请使用「料架管理」页面的「灯测试」功能。
 */
export function HardwareDebugPage() {
  const navigate = useNavigate()

  return (
    <Result
      status="info"
      title="硬件调试功能已移除"
      subTitle="旧版 Modbus 主控板调试已随智能料架 HTTP API 改造移除。料架硬件测试请使用「料架管理」页面的灯测试功能。"
      extra={
        <Button type="primary" onClick={() => navigate('/shelf')}>
          前往料架管理
        </Button>
      }
    />
  )
}
