import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import AsyncStorage from '@react-native-async-storage/async-storage'
import { loginApi, getMeApi } from '../api'
import type { UserResponse } from '../types/api'

interface AuthState {
  token: string | null
  user: UserResponse | null
  isLoading: boolean
  error: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  clearError: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isLoading: false,
      error: null,

      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null })
        try {
          const tokenRes = await loginApi({ username, password })
          await AsyncStorage.setItem('token', tokenRes.access_token)
          const user = await getMeApi()
          set({
            token: tokenRes.access_token,
            user,
            isLoading: false,
            error: null,
          })
        } catch (e: any) {
          const msg = e?.response?.data?.detail || e?.message || '登录失败'
          set({ isLoading: false, error: msg })
          throw new Error(msg)
        }
      },

      logout: async () => {
        await AsyncStorage.removeItem('token')
        set({ token: null, user: null, error: null })
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'pda-auth-storage',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({ token: state.token, user: state.user }),
    }
  )
)
