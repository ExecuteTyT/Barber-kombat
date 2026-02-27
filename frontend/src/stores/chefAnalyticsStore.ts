import { create } from 'zustand'

import api from '../api/client'
import type { BranchAnalytics } from '../types'

interface ChefAnalyticsState {
  analytics: BranchAnalytics | null
  loading: boolean
  error: string | null

  fetchAnalytics: (branchId: string) => Promise<void>
  reset: () => void
}

export const useChefAnalyticsStore = create<ChefAnalyticsState>((set) => ({
  analytics: null,
  loading: false,
  error: null,

  fetchAnalytics: async (branchId) => {
    set({ loading: true, error: null })
    try {
      const { data } = await api.get<BranchAnalytics>(`/reports/branch-analytics/${branchId}`)
      set({ analytics: data, loading: false })
    } catch {
      set({ error: 'Не удалось загрузить аналитику', loading: false })
    }
  },

  reset: () => set({ analytics: null, loading: false, error: null }),
}))
