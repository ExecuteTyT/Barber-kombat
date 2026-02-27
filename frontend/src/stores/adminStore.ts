import { create } from 'zustand'

import api from '../api/client'
import type {
  AdminMetricsResponse,
  AdminTasksResponse,
  AdminHistoryResponse,
} from '../types'

interface AdminState {
  metrics: AdminMetricsResponse | null
  tasks: AdminTasksResponse | null
  history: AdminHistoryResponse | null
  loading: boolean
  error: string | null

  fetchMetrics: (branchId: string) => Promise<void>
  fetchTasks: (branchId: string) => Promise<void>
  confirmRecords: (branchId: string, recordIds: string[]) => Promise<void>
  fetchHistory: (branchId: string, month?: string) => Promise<void>
  reset: () => void
}

export const useAdminStore = create<AdminState>((set, get) => ({
  metrics: null,
  tasks: null,
  history: null,
  loading: false,
  error: null,

  fetchMetrics: async (branchId) => {
    set({ loading: true, error: null })
    try {
      const { data } = await api.get<AdminMetricsResponse>(`/admin/metrics/${branchId}`)
      set({ metrics: data, loading: false })
    } catch {
      set({ error: 'Не удалось загрузить показатели', loading: false })
    }
  },

  fetchTasks: async (branchId) => {
    set({ loading: true, error: null })
    try {
      const { data } = await api.get<AdminTasksResponse>(`/admin/tasks/${branchId}`)
      set({ tasks: data, loading: false })
    } catch {
      set({ error: 'Не удалось загрузить задачи', loading: false })
    }
  },

  confirmRecords: async (branchId, recordIds) => {
    try {
      await api.post(`/admin/tasks/${branchId}/confirm`, { record_ids: recordIds })
      // Refresh tasks after confirming
      const { tasks } = get()
      if (tasks) {
        set({
          tasks: {
            ...tasks,
            unconfirmed_records: tasks.unconfirmed_records.filter(
              (r) => !recordIds.includes(r.record_id),
            ),
          },
        })
      }
    } catch {
      set({ error: 'Не удалось подтвердить записи' })
    }
  },

  fetchHistory: async (branchId, month) => {
    set({ loading: true, error: null })
    try {
      const params = month ? { month } : {}
      const { data } = await api.get<AdminHistoryResponse>(`/admin/history/${branchId}`, { params })
      set({ history: data, loading: false })
    } catch {
      set({ error: 'Не удалось загрузить историю', loading: false })
    }
  },

  reset: () => set({ metrics: null, tasks: null, history: null, loading: false, error: null }),
}))
