import { create } from 'zustand'

import api from '../api/client'
import type {
  DailyRevenueReport,
  DayToDayReport,
  ClientsReport,
  AlarumResponse,
  RatingWeightsConfig,
  PVRThresholdsConfig,
  PVRThreshold,
  PVRPreviewResponse,
  BranchConfig,
  BranchListResponse,
  UserConfig,
  UserListResponse,
  NotificationConfig,
  NotificationConfigListResponse,
  PlanNetworkResponse,
} from '../types'

// --- Dashboard ---

interface DashboardState {
  revenue: DailyRevenueReport | null
  alarumTotal: number
  isLoading: boolean
  error: string | null
}

// --- Reports ---

interface ReportsState {
  dayToDay: DayToDayReport | null
  clients: ClientsReport | null
  revenueByDate: DailyRevenueReport | null
  revenueByDateLoading: boolean
  reportsLoading: boolean
  reportsError: string | null
}

// --- Settings ---

interface SettingsState {
  ratingWeights: RatingWeightsConfig | null
  pvrThresholds: PVRThresholdsConfig | null
  branches: BranchConfig[]
  users: UserConfig[]
  notifications: NotificationConfig[]
  plans: PlanNetworkResponse | null
  settingsLoading: boolean
  settingsError: string | null
  settingsSaving: boolean
}

type OwnerState = DashboardState &
  ReportsState &
  SettingsState & {
    // Dashboard actions
    fetchDashboard: () => Promise<void>
    fetchAlarum: () => Promise<void>

    // Reports actions
    fetchDayToDay: (branchId?: string, date?: string) => Promise<void>
    fetchClients: (date?: string) => Promise<void>
    fetchRevenueByDate: (date: string) => Promise<void>

    // Settings actions
    fetchRatingWeights: () => Promise<void>
    saveRatingWeights: (data: RatingWeightsConfig) => Promise<boolean>
    fetchPvrThresholds: () => Promise<void>
    savePvrThresholds: (data: PVRThresholdsConfig) => Promise<boolean>
    previewPvr: (
      branchId: string,
      thresholds: PVRThreshold[],
      minVisits: number,
      month?: string,
    ) => Promise<PVRPreviewResponse | null>
    fetchBranches: () => Promise<void>
    createBranch: (data: { name: string; address?: string; yclients_company_id?: number; telegram_group_id?: number }) => Promise<boolean>
    saveBranch: (id: string, data: Partial<BranchConfig>) => Promise<boolean>
    fetchUsers: (branchId?: string) => Promise<void>
    saveUser: (id: string, data: Partial<UserConfig>) => Promise<boolean>
    fetchNotifications: () => Promise<void>
    createNotification: (data: { branch_id?: string; notification_type: string; telegram_chat_id: number; is_enabled?: boolean; schedule_time?: string }) => Promise<boolean>
    updateNotification: (id: string, data: { telegram_chat_id?: number; is_enabled?: boolean; schedule_time?: string | null }) => Promise<boolean>
    deleteNotification: (id: string) => Promise<boolean>
    fetchPlans: (month?: string) => Promise<void>
    savePlan: (branchId: string, month: string, targetAmount: number) => Promise<boolean>
  }

export const useOwnerStore = create<OwnerState>((set) => ({
  // Dashboard
  revenue: null,
  alarumTotal: 0,
  isLoading: false,
  error: null,

  // Reports
  dayToDay: null,
  clients: null,
  revenueByDate: null,
  revenueByDateLoading: false,
  reportsLoading: false,
  reportsError: null,

  // Settings
  ratingWeights: null,
  pvrThresholds: null,
  branches: [],
  users: [],
  notifications: [],
  plans: null,
  settingsLoading: false,
  settingsError: null,
  settingsSaving: false,

  // --- Dashboard actions ---

  fetchDashboard: async () => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.get<DailyRevenueReport>('/reports/revenue')
      set({ revenue: data, isLoading: false })
    } catch {
      set({ error: 'Не удалось загрузить дашборд', isLoading: false })
    }
  },

  fetchAlarum: async () => {
    try {
      const { data } = await api.get<AlarumResponse>('/reviews/alarum/feed')
      set({ alarumTotal: data.total })
    } catch {
      // Non-critical
    }
  },

  // --- Reports actions ---

  fetchDayToDay: async (branchId?: string, date?: string) => {
    set({ reportsLoading: true, reportsError: null })
    try {
      const params: Record<string, string> = {}
      if (branchId) params.branch_id = branchId
      if (date) params.date = date
      const { data } = await api.get<DayToDayReport>('/reports/day-to-day', { params })
      set({ dayToDay: data, reportsLoading: false })
    } catch {
      set({ reportsError: 'Не удалось загрузить отчёт', reportsLoading: false })
    }
  },

  fetchClients: async (date?: string) => {
    set({ reportsLoading: true, reportsError: null })
    try {
      const params: Record<string, string> = {}
      if (date) params.date = date
      const { data } = await api.get<ClientsReport>('/reports/clients', { params })
      set({ clients: data, reportsLoading: false })
    } catch {
      set({ reportsError: 'Не удалось загрузить отчёт', reportsLoading: false })
    }
  },

  fetchRevenueByDate: async (date: string) => {
    set({ revenueByDateLoading: true, reportsError: null })
    try {
      const { data } = await api.get<DailyRevenueReport>('/reports/revenue', {
        params: { target_date: date },
      })
      set({ revenueByDate: data, revenueByDateLoading: false })
    } catch {
      set({
        reportsError: 'Не удалось загрузить отчёт за выбранную дату',
        revenueByDateLoading: false,
      })
    }
  },

  // --- Settings actions ---

  fetchRatingWeights: async () => {
    set({ settingsLoading: true })
    try {
      const { data } = await api.get<RatingWeightsConfig>('/config/rating-weights')
      set({ ratingWeights: data, settingsLoading: false })
    } catch {
      set({ settingsError: 'Не удалось загрузить настройки', settingsLoading: false })
    }
  },

  saveRatingWeights: async (payload: RatingWeightsConfig): Promise<boolean> => {
    set({ settingsSaving: true })
    try {
      const { data } = await api.put<RatingWeightsConfig>('/config/rating-weights', payload)
      set({ ratingWeights: data, settingsSaving: false })
      return true
    } catch {
      set({ settingsSaving: false })
      return false
    }
  },

  fetchPvrThresholds: async () => {
    set({ settingsLoading: true })
    try {
      const { data } = await api.get<PVRThresholdsConfig>('/config/pvr-thresholds')
      set({ pvrThresholds: data, settingsLoading: false })
    } catch {
      set({ settingsError: 'Не удалось загрузить пороги', settingsLoading: false })
    }
  },

  savePvrThresholds: async (payload: PVRThresholdsConfig): Promise<boolean> => {
    set({ settingsSaving: true })
    try {
      const { data } = await api.put<PVRThresholdsConfig>('/config/pvr-thresholds', payload)
      set({ pvrThresholds: data, settingsSaving: false })
      return true
    } catch {
      set({ settingsSaving: false })
      return false
    }
  },

  previewPvr: async (
    branchId: string,
    thresholds: PVRThreshold[],
    minVisits: number,
    month?: string,
  ): Promise<PVRPreviewResponse | null> => {
    try {
      const { data } = await api.post<PVRPreviewResponse>('/pvr/preview', {
        branch_id: branchId,
        thresholds,
        min_visits_per_month: minVisits,
        month,
      })
      return data
    } catch {
      return null
    }
  },

  fetchBranches: async () => {
    set({ settingsLoading: true })
    try {
      const { data } = await api.get<BranchListResponse>('/config/branches')
      set({ branches: data.branches, settingsLoading: false })
    } catch {
      set({ settingsError: 'Не удалось загрузить филиалы', settingsLoading: false })
    }
  },

  createBranch: async (payload): Promise<boolean> => {
    set({ settingsSaving: true })
    try {
      await api.post('/config/branches', payload)
      const { data } = await api.get<BranchListResponse>('/config/branches')
      set({ branches: data.branches, settingsSaving: false })
      return true
    } catch {
      set({ settingsSaving: false })
      return false
    }
  },

  saveBranch: async (id: string, payload: Partial<BranchConfig>): Promise<boolean> => {
    set({ settingsSaving: true })
    try {
      await api.put(`/config/branches/${id}`, payload)
      // Refresh the full list
      const { data } = await api.get<BranchListResponse>('/config/branches')
      set({ branches: data.branches, settingsSaving: false })
      return true
    } catch {
      set({ settingsSaving: false })
      return false
    }
  },

  fetchUsers: async (branchId?: string) => {
    set({ settingsLoading: true })
    try {
      const params: Record<string, string> = {}
      if (branchId) params.branch_id = branchId
      const { data } = await api.get<UserListResponse>('/config/users', { params })
      set({ users: data.users, settingsLoading: false })
    } catch {
      set({ settingsError: 'Не удалось загрузить сотрудников', settingsLoading: false })
    }
  },

  saveUser: async (id: string, payload: Partial<UserConfig>): Promise<boolean> => {
    set({ settingsSaving: true })
    try {
      await api.put(`/config/users/${id}`, payload)
      const { data } = await api.get<UserListResponse>('/config/users')
      set({ users: data.users, settingsSaving: false })
      return true
    } catch {
      set({ settingsSaving: false })
      return false
    }
  },

  fetchNotifications: async () => {
    set({ settingsLoading: true })
    try {
      const { data } = await api.get<NotificationConfigListResponse>('/config/notifications')
      set({ notifications: data.notifications, settingsLoading: false })
    } catch {
      set({ settingsError: 'Не удалось загрузить уведомления', settingsLoading: false })
    }
  },

  createNotification: async (payload): Promise<boolean> => {
    set({ settingsSaving: true })
    try {
      await api.post('/config/notifications', payload)
      const { data } = await api.get<NotificationConfigListResponse>('/config/notifications')
      set({ notifications: data.notifications, settingsSaving: false })
      return true
    } catch {
      set({ settingsSaving: false })
      return false
    }
  },

  updateNotification: async (id, payload): Promise<boolean> => {
    set({ settingsSaving: true })
    try {
      await api.put(`/config/notifications/${id}`, payload)
      const { data } = await api.get<NotificationConfigListResponse>('/config/notifications')
      set({ notifications: data.notifications, settingsSaving: false })
      return true
    } catch {
      set({ settingsSaving: false })
      return false
    }
  },

  deleteNotification: async (id): Promise<boolean> => {
    set({ settingsSaving: true })
    try {
      await api.delete(`/config/notifications/${id}`)
      const { data } = await api.get<NotificationConfigListResponse>('/config/notifications')
      set({ notifications: data.notifications, settingsSaving: false })
      return true
    } catch {
      set({ settingsSaving: false })
      return false
    }
  },

  fetchPlans: async (month?: string) => {
    set({ settingsLoading: true })
    try {
      const params: Record<string, string> = {}
      if (month) params.month = month
      const { data } = await api.get<PlanNetworkResponse>('/plans/network/all', { params })
      set({ plans: data, settingsLoading: false })
    } catch {
      set({ settingsError: 'Не удалось загрузить планы', settingsLoading: false })
    }
  },

  savePlan: async (branchId: string, month: string, targetAmount: number): Promise<boolean> => {
    set({ settingsSaving: true })
    try {
      await api.put(`/plans/${branchId}`, { month, target_amount: targetAmount })
      // Refresh plans
      const { data } = await api.get<PlanNetworkResponse>('/plans/network/all')
      set({ plans: data, settingsSaving: false })
      return true
    } catch {
      set({ settingsSaving: false })
      return false
    }
  },
}))
