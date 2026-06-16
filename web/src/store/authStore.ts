import { create } from 'zustand'
import { persist } from 'zustand/middleware'
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
  persist(
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
    { name: 'auth-storage' },
  ),
)

export async function login(username: string, password: string) {
  const response = await api.post('/auth/login', { username, password })
  const { access_token } = response.data
  const me = await api.get('/auth/me')
  useAuthStore.getState().setAuth(access_token, me.data)
  return me.data
}
