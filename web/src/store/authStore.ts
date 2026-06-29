import { create } from 'zustand'
import api from '../api/client'

export interface User {
  id: number
  username: string
  role: string
  role_id?: number
  customer_id?: number
  customer_name?: string
  permissions?: string[]
}

interface AuthState {
  token: string | null
  user: User | null
  setAuth: (token: string, user: User) => void
  logout: () => void
  hasPermission: (code: string) => boolean
  hasAnyPermission: (codes: string[]) => boolean
}

export const useAuthStore = create<AuthState>()(
  (set, get) => ({
    token: localStorage.getItem('token'),
    user: null,
    setAuth: (token, user) => {
      localStorage.setItem('token', token)
      set({ token, user })
    },
    logout: () => {
      localStorage.removeItem('token')
      set({ token: null, user: null })
      window.location.href = '/login'
    },
    hasPermission: (code: string) => {
      const { user } = get()
      if (!user) return false
      // Admin always has all permissions
      if (user.role === 'admin') return true
      return user.permissions?.includes(code) ?? false
    },
    hasAnyPermission: (codes: string[]) => {
      const { user } = get()
      if (!user) return false
      if (user.role === 'admin') return true
      return codes.some(code => user.permissions?.includes(code))
    },
  }),
)

export async function login(username: string, password: string) {
  const response = await api.post('/auth/login', { username, password })
  const { access_token } = response.data
  useAuthStore.getState().setAuth(access_token, null as any)
  const me = await api.get('/auth/me', {
    headers: { Authorization: `Bearer ${access_token}` },
  })
  useAuthStore.getState().setAuth(access_token, me.data)
  return me.data
}

// Helper to check permission in components
export function usePermission(code: string): boolean {
  return useAuthStore.getState().hasPermission(code)
}

export function useAnyPermission(codes: string[]): boolean {
  return useAuthStore.getState().hasAnyPermission(codes)
}
