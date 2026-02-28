import { useEffect, useCallback, type ReactNode } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useRawInitData } from '@telegram-apps/sdk-react'

import { useAuthStore } from './stores/authStore'
import type { UserRole } from './types'
import { useDeepLink } from './hooks/useDeepLink'
import { useTelegramTheme } from './hooks/useTelegramTheme'
import DevToolbar from './components/DevToolbar'
import DevLoginScreen from './screens/DevLoginScreen'
import LoginScreen from './screens/LoginScreen'
import BarberLayout from './screens/barber/BarberLayout'
import KombatScreen from './screens/barber/KombatScreen'
import ProgressScreen from './screens/barber/ProgressScreen'
import HistoryScreen from './screens/barber/HistoryScreen'
import ChefLayout from './screens/chef/ChefLayout'
import BranchScreen from './screens/chef/BranchScreen'
import ChefAnalyticsScreen from './screens/chef/ChefAnalyticsScreen'
import ChefKombatScreen from './screens/chef/ChefKombatScreen'
import ChefPVRScreen from './screens/chef/ChefPVRScreen'
import OwnerLayout from './screens/owner/OwnerLayout'
import DashboardScreen from './screens/owner/DashboardScreen'
import ReportsScreen from './screens/owner/ReportsScreen'
import CompetitionsScreen from './screens/owner/CompetitionsScreen'
import SettingsScreen from './screens/owner/SettingsScreen'
import AdminLayout from './screens/admin/AdminLayout'
import MetricsScreen from './screens/admin/MetricsScreen'
import TasksScreen from './screens/admin/TasksScreen'
import AdminHistoryScreen from './screens/admin/AdminHistoryScreen'

const DEFAULT_ROUTES: Record<string, string> = {
  barber: '/barber/kombat',
  chef: '/chef/kombat',
  owner: '/owner/dashboard',
  admin: '/admin/metrics',
  manager: '/chef/kombat',
}

/** Which roles are allowed to access each route section */
const SECTION_ROLES: Record<string, UserRole[]> = {
  barber: ['barber'],
  chef: ['chef', 'manager'],
  owner: ['owner'],
  admin: ['admin'],
}

function RoleGuard({ section, children }: { section: string; children: ReactNode }) {
  const role = useAuthStore((s) => s.user?.role)
  const allowed = SECTION_ROLES[section]
  if (!role || !allowed?.includes(role)) {
    const target = DEFAULT_ROUTES[role ?? 'barber'] ?? '/barber/kombat'
    return <Navigate to={target} replace />
  }
  return <>{children}</>
}

function useInitDataSafe(): string | undefined {
  try {
    return useRawInitData()
  } catch {
    // Outside Telegram — no init data available
    return undefined
  }
}

function App() {
  useTelegramTheme()

  const { user, token, isLoading, error, login, hydrate } = useAuthStore()

  // Deep link: parse startapp param and navigate after auth
  useDeepLink(user?.role)

  const initDataRaw = useInitDataSafe()

  useEffect(() => {
    hydrate()
  }, [hydrate])

  const handleLogin = useCallback(() => {
    if (initDataRaw) {
      login(initDataRaw)
    }
  }, [initDataRaw, login])

  // After hydrate, if we have a token but no user yet — still loading
  useEffect(() => {
    if (!isLoading && !user && token === null && initDataRaw) {
      login(initDataRaw)
    }
  }, [isLoading, user, token, initDataRaw, login])

  if (isLoading) {
    return <LoginScreen />
  }

  if (error) {
    // In dev mode (outside Telegram), show dev login on error
    if (!initDataRaw) {
      return <DevLoginScreen />
    }
    return <LoginScreen error={error} onRetry={handleLogin} />
  }

  if (!user) {
    // Outside Telegram and no saved token — show dev login selector
    if (!initDataRaw) {
      return <DevLoginScreen />
    }
    return <LoginScreen />
  }

  const defaultRoute = DEFAULT_ROUTES[user.role] ?? '/barber/kombat'
  const isDevMode = !initDataRaw

  return (
    <>
      {isDevMode && <DevToolbar />}
      <div className={isDevMode ? 'pt-8' : ''}>
        <Routes>
          <Route
            path="/barber"
            element={
              <RoleGuard section="barber">
                <BarberLayout />
              </RoleGuard>
            }
          >
            <Route path="kombat" element={<KombatScreen />} />
            <Route path="progress" element={<ProgressScreen />} />
            <Route path="history" element={<HistoryScreen />} />
            <Route index element={<Navigate to="kombat" replace />} />
          </Route>

          <Route
            path="/chef"
            element={
              <RoleGuard section="chef">
                <ChefLayout />
              </RoleGuard>
            }
          >
            <Route path="kombat" element={<ChefKombatScreen />} />
            <Route path="branch" element={<BranchScreen />} />
            <Route path="pvr" element={<ChefPVRScreen />} />
            <Route path="analytics" element={<ChefAnalyticsScreen />} />
            <Route index element={<Navigate to="kombat" replace />} />
          </Route>

          <Route
            path="/owner"
            element={
              <RoleGuard section="owner">
                <OwnerLayout />
              </RoleGuard>
            }
          >
            <Route path="dashboard" element={<DashboardScreen />} />
            <Route path="branch/:branchId" element={<BranchScreen />} />
            <Route path="reports" element={<ReportsScreen />} />
            <Route path="competitions" element={<CompetitionsScreen />} />
            <Route path="settings" element={<SettingsScreen />} />
            <Route index element={<Navigate to="dashboard" replace />} />
          </Route>

          <Route
            path="/admin"
            element={
              <RoleGuard section="admin">
                <AdminLayout />
              </RoleGuard>
            }
          >
            <Route path="metrics" element={<MetricsScreen />} />
            <Route path="tasks" element={<TasksScreen />} />
            <Route path="history" element={<AdminHistoryScreen />} />
            <Route index element={<Navigate to="metrics" replace />} />
          </Route>

          <Route path="*" element={<Navigate to={defaultRoute} replace />} />
        </Routes>
      </div>
    </>
  )
}

export default App
