import api from './client'

export async function login(username: string, password: string) {
  const response = await api.post('/auth/login', { username, password })
  return response.data
}

export async function getUserInfo() {
  const response = await api.get('/auth/me')
  return response.data
}
