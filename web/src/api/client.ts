import axios from 'axios'
import { useAuthStore } from '../store/authStore'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  // FastAPI 需要重复 key 的数组序列化方式: ?customer_ids=1&customer_ids=2
  // 而非 Axios 默认的: ?customer_ids[]=1&customer_ids[]=2
  paramsSerializer: (params: Record<string, any>) => {
    const searchParams = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (Array.isArray(value)) {
        for (const item of value) {
          if (item !== undefined && item !== null) {
            searchParams.append(key, String(item))
          }
        }
      } else if (value !== undefined && value !== null) {
        searchParams.append(key, String(value))
      }
    }
    return searchParams.toString()
  },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // 只在非登录接口返回 401 时跳转登录页（登录接口 401 表示用户名或密码错误）
      const isLoginRequest = error.config?.url?.includes('/auth/login')
      if (!isLoginRequest) {
        useAuthStore.getState().logout()
      }
    }
    return Promise.reject(error)
  }
)

export default api
