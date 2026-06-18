import api from '../api/client'

let _appName = '智能物料管理系统'

export async function loadAppConfig(): Promise<void> {
  try {
    const res = await api.get('/system/info')
    _appName = res.data?.app_name || _appName
    document.title = _appName
  } catch {
    // Keep default
  }
}

export function getAppName(): string {
  return _appName
}
