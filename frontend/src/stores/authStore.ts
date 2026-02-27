import { create } from 'zustand'

import { authApi } from '../api/client'
import type { User } from '../types'

interface AuthState {
  user: User | null
  token: string | null
  isLoading: boolean
  error: string | null
  login: (initData: string) => Promise<void>
  devLogin: (telegramId: number) => Promise<void>
  fetchMe: () => Promise<void>
  logout: () => void
  hydrate: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: localStorage.getItem('access_token'),
  isLoading: false,
  error: null,

  login: async (initData: string) => {
    set({ isLoading: true, error: null })
    try {
      const response = await authApi.login(initData)
      localStorage.setItem('access_token', response.access_token)
      set({
        token: response.access_token,
        user: response.user,
        isLoading: false,
      })
    } catch {
      set({ isLoading: false, error: 'Ошибка авторизации' })
    }
  },

  devLogin: async (telegramId: number) => {
    set({ isLoading: true, error: null })
    try {
      const response = await authApi.devLogin(telegramId)
      localStorage.setItem('access_token', response.access_token)
      set({
        token: response.access_token,
        user: response.user,
        isLoading: false,
      })
    } catch {
      set({ isLoading: false, error: 'Ошибка входа (dev)' })
    }
  },

  fetchMe: async () => {
    try {
      const me = await authApi.me()
      set({
        user: {
          id: me.id,
          name: me.name,
          role: me.role,
          branch_id: me.branch_id,
          organization_id: me.organization_id,
        },
      })
    } catch {
      get().logout()
    }
  },

  logout: () => {
    localStorage.removeItem('access_token')
    set({ user: null, token: null, error: null })
  },

  hydrate: async () => {
    const token = localStorage.getItem('access_token')
    if (token) {
      set({ token, isLoading: true })
      try {
        await get().fetchMe()
      } finally {
        set({ isLoading: false })
      }
    }
  },
}))
