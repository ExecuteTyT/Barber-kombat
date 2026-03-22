import { create } from 'zustand'

import api from '../api/client'
import type {
  BarberPVRResponse,
  BranchPVRResponse,
  PVRThreshold,
  ThresholdsResponse,
} from '../types'

interface PVRState {
  barberPvr: BarberPVRResponse | null
  branchPvr: BranchPVRResponse | null
  thresholds: PVRThreshold[]
  isLoading: boolean
  error: string | null

  fetchBarberPvr: (barberId: string) => Promise<void>
  fetchBranchPvr: (branchId: string, month?: string) => Promise<void>
  fetchThresholds: () => Promise<void>
  reset: () => void
}

export const usePvrStore = create<PVRState>((set) => ({
  barberPvr: null,
  branchPvr: null,
  thresholds: [],
  isLoading: false,
  error: null,

  fetchBarberPvr: async (barberId: string) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.get<BarberPVRResponse>(`/pvr/barber/${barberId}`)
      set({ barberPvr: data, isLoading: false })
    } catch {
      set({ error: 'Не удалось загрузить данные по премиям', isLoading: false })
    }
  },

  fetchBranchPvr: async (branchId: string, month?: string) => {
    set({ isLoading: true, error: null })
    try {
      const params = month ? { month } : undefined
      const { data } = await api.get<BranchPVRResponse>(`/pvr/${branchId}/current`, { params })
      set({ branchPvr: data, isLoading: false })
    } catch {
      set({ error: 'Не удалось загрузить данные по премиям филиала', isLoading: false })
    }
  },

  fetchThresholds: async () => {
    try {
      const { data } = await api.get<ThresholdsResponse>('/pvr/thresholds')
      set({ thresholds: data.thresholds })
    } catch {
      // Non-critical: thresholds list is optional for display
    }
  },

  reset: () => {
    set({
      barberPvr: null,
      branchPvr: null,
      thresholds: [],
      isLoading: false,
      error: null,
    })
  },
}))
