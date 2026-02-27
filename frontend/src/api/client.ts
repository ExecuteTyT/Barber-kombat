import axios from 'axios'

import type { MeResponse, TokenResponse } from '../types'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      localStorage.removeItem('access_token')
    }
    return Promise.reject(error)
  },
)

export interface DevUser {
  telegram_id: number
  name: string
  role: string
  branch_id: string | null
}

export const authApi = {
  login: async (initData: string): Promise<TokenResponse> => {
    const { data } = await api.post<TokenResponse>('/auth/telegram', { init_data: initData })
    return data
  },
  devLogin: async (telegramId: number): Promise<TokenResponse> => {
    const { data } = await api.post<TokenResponse>('/auth/dev-login', { telegram_id: telegramId })
    return data
  },
  devUsers: async (): Promise<DevUser[]> => {
    const { data } = await api.get<{ users: DevUser[] }>('/auth/dev-users')
    return data.users
  },
  me: async (): Promise<MeResponse> => {
    const { data } = await api.get<MeResponse>('/auth/me')
    return data
  },
}

export default api
