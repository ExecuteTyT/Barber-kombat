import { create } from 'zustand'

import api from '../api/client'
import type { TodayRatingResponse, BarberStatsResponse, RatingEntry } from '../types'

interface KombatState {
  todayRating: TodayRatingResponse | null
  barberStats: BarberStatsResponse | null
  isLoading: boolean
  error: string | null

  fetchTodayRating: (branchId: string) => Promise<void>
  fetchBarberStats: (barberId: string, month?: string) => Promise<void>
  applyRatingUpdate: (ratings: RatingEntry[]) => void
  reset: () => void
}

export const useKombatStore = create<KombatState>((set, get) => ({
  todayRating: null,
  barberStats: null,
  isLoading: false,
  error: null,

  fetchTodayRating: async (branchId: string) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.get<TodayRatingResponse>(`/kombat/today/${branchId}`)
      set({ todayRating: data, isLoading: false })
    } catch {
      set({ error: 'Не удалось загрузить рейтинг', isLoading: false })
    }
  },

  fetchBarberStats: async (barberId: string, month?: string) => {
    set({ isLoading: true, error: null })
    try {
      const params = month ? { month } : {}
      const { data } = await api.get<BarberStatsResponse>(`/kombat/barber/${barberId}/stats`, {
        params,
      })
      set({ barberStats: data, isLoading: false })
    } catch {
      set({ error: 'Не удалось загрузить статистику', isLoading: false })
    }
  },

  applyRatingUpdate: (ratings: RatingEntry[]) => {
    const current = get().todayRating
    if (!current) return
    set({ todayRating: { ...current, ratings } })
  },

  reset: () => {
    set({ todayRating: null, barberStats: null, isLoading: false, error: null })
  },
}))
