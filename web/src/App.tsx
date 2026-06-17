import { Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from './components/AppLayout'
import { LoginPage } from './pages/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { MaterialManagementPage } from './pages/MaterialManagementPage'
import { ShelfManagementPage } from './pages/ShelfManagementPage'
import { InventoryPage } from './pages/InventoryPage'
import { ReceiptPage } from './pages/ReceiptPage'
import { IssueOrderPage } from './pages/IssueOrderPage'
import { XrManagePage } from './pages/XrManagePage'
import { BOMPage } from './pages/BOMPage'
import { CustomerPage } from './pages/CustomerPage'
import { ReportPage } from './pages/ReportPage'
import { SystemSettingsPage } from './pages/SystemSettingsPage'
import { UserManagementPage } from './pages/UserManagementPage'
import { AppDownloadPage } from './pages/AppDownloadPage'
import { useAuthStore } from './store/authStore'

export default function App() {
  const { token } = useAuthStore()

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          token ? (
            <AppLayout>
              <Routes>
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<DashboardPage />} />
                <Route path="material" element={<MaterialManagementPage />} />
                <Route path="shelf" element={<ShelfManagementPage />} />
                <Route path="inventory" element={<InventoryPage />} />
                <Route path="receipt" element={<ReceiptPage />} />
                <Route path="issue" element={<IssueOrderPage />} />
                <Route path="xr" element={<XrManagePage />} />
                <Route path="bom" element={<BOMPage />} />
                <Route path="customers" element={<CustomerPage />} />
                <Route path="report" element={<ReportPage />} />
                <Route path="settings" element={<SystemSettingsPage />} />
                <Route path="users" element={<UserManagementPage />} />
                <Route path="app-download" element={<AppDownloadPage />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </AppLayout>
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
    </Routes>
  )
}
