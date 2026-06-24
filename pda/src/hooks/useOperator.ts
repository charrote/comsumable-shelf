import { useState, useEffect, useCallback } from 'react'
import AsyncStorage from '@react-native-async-storage/async-storage'
import { useAuthStore } from '../store/authStore'

const OPERATOR_KEY = 'pda_operator_name'

/**
 * useOperator — 全局操作员设置 Hook
 *
 * 行为：
 * 1. 优先返回用户在设置页保存的操作员姓名（AsyncStorage 持久化）
 * 2. 如果未设置，回退到当前登录用户的 username
 * 3. 提供 setOperator 方法，调用后立即持久化并全局生效
 *
 * 所有需要操作员信息的业务页面统一使用此 Hook，
 * 确保「设置页统一配置，各页面自动读取」。
 */
export function useOperator() {
  const user = useAuthStore((s) => s.user)
  const [operator, setOperatorState] = useState<string>('')
  const [isLoaded, setIsLoaded] = useState(false)

  // 启动时从 AsyncStorage 加载
  useEffect(() => {
    ;(async () => {
      try {
        const stored = await AsyncStorage.getItem(OPERATOR_KEY)
        if (stored) {
          setOperatorState(stored)
        } else if (user?.username) {
          setOperatorState(user.username)
        }
      } catch {
        if (user?.username) setOperatorState(user.username)
      } finally {
        setIsLoaded(true)
      }
    })()
  }, [user?.username])

  // 设置操作员（持久化到 AsyncStorage）
  const setOperator = useCallback(async (name: string) => {
    setOperatorState(name)
    try {
      await AsyncStorage.setItem(OPERATOR_KEY, name)
    } catch {
      // 静默失败
    }
  }, [])

  return { operator, setOperator, isLoaded }
}

/**
 * 获取操作员的异步工具函数（用于非 Hook 场景）
 */
export async function getOperatorFromStorage(): Promise<string> {
  try {
    return (await AsyncStorage.getItem(OPERATOR_KEY)) || ''
  } catch {
    return ''
  }
}

export { OPERATOR_KEY }
