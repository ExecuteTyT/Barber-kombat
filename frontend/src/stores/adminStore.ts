import { create } from 'zustand'

import api from '../api/client'
import type {
  AdminMetricsResponse,
  AdminTasksResponse,
  AdminHistoryResponse,
  BranchAdminKpi,
  CallListResponse,
  NetworkAdminKpiResponse,
} from '../types'

interface AdminState {
  metrics: AdminMetricsResponse | null
  tasks: AdminTasksResponse | null
  history: AdminHistoryResponse | null
  calls: CallListResponse | null
  branchKpi: BranchAdminKpi | null
  networkKpi: NetworkAdminKpiResponse | null
  loading: boolean
  error: string | null

  fetchMetrics: (branchId: string) => Promise<void>
  fetchTasks: (branchId: string) => Promise<void>
  confirmRecords: (branchId: string, recordIds: string[]) => Promise<void>
  fetchHistory: (branchId: string, month?: string) => Promise<void>
  fetchCalls: (branchId: string) => Promise<void>
  markCall: (branchId: string, yclientsRecordId: number, result?: string) => Promise<void>
  fetchBranchKpi: (branchId: string) => Promise<void>
  fetchNetworkKpi: () => Promise<void>
  reset: () => void
}

export const useAdminStore = create<AdminState>((set, get) => ({
  metrics: null,
  tasks: null,
  history: null,
  calls: null,
  branchKpi: null,
  networkKpi: null,
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

  fetchCalls: async (branchId) => {
    set({ loading: true, error: null })
    try {
      const { data } = await api.get<CallListResponse>(`/admin/calls/${branchId}`)
      set({ calls: data, loading: false })
    } catch {
      set({ error: 'Не удалось загрузить список звонков', loading: false })
    }
  },

  markCall: async (branchId, yclientsRecordId, result = 'confirmed') => {
    try {
      await api.post(`/admin/calls/${branchId}/mark`, {
        yclients_record_id: yclientsRecordId,
        result,
      })
      const { calls } = get()
      if (calls) {
        const to_call = calls.to_call.map((t) =>
          t.yclients_record_id === yclientsRecordId ? { ...t, called: true, result } : t,
        )
        const called_count = to_call.filter((t) => t.called).length
        const call_progress = to_call.length
          ? Math.round((called_count / to_call.length) * 100)
          : 100
        set({ calls: { ...calls, to_call, called_count, call_progress } })
      }
    } catch {
      set({ error: 'Не удалось отметить звонок' })
    }
  },

  fetchBranchKpi: async (branchId) => {
    set({ loading: true, error: null })
    try {
      const { data } = await api.get<BranchAdminKpi>(`/admin/kpi/${branchId}`)
      set({ branchKpi: data, loading: false })
    } catch {
      set({ error: 'Не удалось загрузить KPI', loading: false })
    }
  },

  fetchNetworkKpi: async () => {
    set({ loading: true, error: null })
    try {
      const { data } = await api.get<NetworkAdminKpiResponse>('/admin/kpi/network/all')
      set({ networkKpi: data, loading: false })
    } catch {
      set({ error: 'Не удалось загрузить KPI сети', loading: false })
    }
  },

  reset: () =>
    set({
      metrics: null,
      tasks: null,
      history: null,
      calls: null,
      branchKpi: null,
      networkKpi: null,
      loading: false,
      error: null,
    }),
}))
