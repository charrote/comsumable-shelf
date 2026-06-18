import ReactDOM from 'react-dom/client'
import { ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { ErrorBoundary } from './components/ErrorBoundary'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'

dayjs.locale('zh-cn')

function bootstrap() {
  const loadingEl = document.getElementById('root-loading')
  if (loadingEl) loadingEl.remove()

  const root = document.getElementById('root')
  if (!root) return

  // Load system config (e.g., app_name) from backend — async, doesn't block render
  import('./store/configStore').then(({ loadAppConfig }) => loadAppConfig())

  ReactDOM.createRoot(root).render(
    <ErrorBoundary>
      <ConfigProvider
        locale={zhCN}
        theme={{
          algorithm: theme.defaultAlgorithm,
          token: {
            colorPrimary: '#1890ff',
            borderRadius: 6,
          },
        }}
      >
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ConfigProvider>
    </ErrorBoundary>,
  )
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', bootstrap)
} else {
  bootstrap()
}
