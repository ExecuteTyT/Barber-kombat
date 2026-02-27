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
  fetchBranchPvr: (branchId: string) => Promise<void>
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
      const { data } = await api.get<BarberPVRResponse>(
        `/pvr/barber/${barberId}`,
      )
      set({ barberPvr: data, isLoading: false })
    } catch {
      set({ error: 'Не удалось загрузить ПВР', isLoading: false })
    }
  },

  fetchBranchPvr: async (branchId: string) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.get<BranchPVRResponse>(
        `/pvr/${branchId}/current`,
      )
      set({ branchPvr: data, isLoading: false })
    } catch {
      set({ error: 'Не удалось загрузить ПВР филиала', isLoading: false })
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
