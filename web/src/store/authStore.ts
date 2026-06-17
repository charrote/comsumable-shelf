import { create } from 'zustand'
import api from '../api/client'

interface User {
  username: string
  role: string
  customer_id?: number
  customer_name?: string
}

interface AuthState {
  token: string | null
  user: User | null
  setAuth: (token: string, user: User) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  (set) => ({
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
